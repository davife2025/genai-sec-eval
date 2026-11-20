"""Command line interface:  python -m secbench <command>"""
from __future__ import annotations

import argparse
import asyncio
import csv
import json
import random
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

from . import __version__
from .dataset import build_data, format_grid
from .env import load_dotenv
from .judges import LLMJudge, rule_judge
from .metrics import cohen_kappa, summarize
from .report import render_compare, render_report
from .runner import load_latest, run_cases
from .schema import load_cases, read_jsonl, sha256_file, write_jsonl
from .targets import make_target


def _run_dir(args) -> Path:
    return Path(args.run)


def _load_yaml(path):
    return yaml.safe_load(Path(path).read_text())


# ------------------------------------------------------------------ commands
def cmd_build_data(args):
    cases = build_data(args.out, args.private_seeds)
    print(format_grid(cases))
    print(f"\nwrote {args.out}/dev.jsonl and manifest.json ({len(cases)} cases total)")


def cmd_run(args) -> Path:
    cfg = _load_yaml(args.config)
    tcfg = dict(cfg["target"])
    for key in ("model", "provider", "type"):
        if getattr(args, key, None):
            tcfg[key] = getattr(args, key)
    dcfg, rcfg = cfg["dataset"], cfg.get("runner", {})
    if args.repeats:
        rcfg["repeats"] = args.repeats
    split = args.split or dcfg.get("split", "dev")
    cases = load_cases(args.dataset or dcfg["path"], split=split, limit=args.limit or dcfg.get("limit"))
    if not cases:
        sys.exit(f"no cases found (split={split}). Run: python -m secbench build-data")
    name = args.run_name or cfg.get("run_name") or "run"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    run_dir = Path(cfg.get("output_dir", "results")) / (name if args.resume else f"{name}-{stamp}")
    system_prompt = Path(cfg["system_prompt"]).read_text()
    target = make_target(tcfg)
    ds_path = args.dataset or dcfg["path"]
    ds_hash = sha256_file(ds_path)
    started = datetime.now(timezone.utc).isoformat(timespec="seconds")
    asyncio.run(run_cases(
        cases, target, system_prompt, run_dir / "raw.jsonl", run_id=run_dir.name,
        model=tcfg.get("model", tcfg.get("type", "mock")), concurrency=rcfg.get("concurrency", 4),
        max_retries=rcfg.get("max_retries", 3), repeats=rcfg.get("repeats", 1),
        dataset_hash=ds_hash, temperature=tcfg.get("temperature")))
    meta = {"run_name": run_dir.name, "target": tcfg, "runner": rcfg, "secbench_version": __version__,
            "dataset": {"path": str(ds_path), "sha256": ds_hash, "split": split, "n_cases": len(cases)},
            "started_at": started, "finished_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    (run_dir / "run.json").write_text(json.dumps(meta, indent=2))
    print(f"[run] raw outputs: {run_dir/'raw.jsonl'}")
    return run_dir


def cmd_judge(args) -> None:
    run_dir = _run_dir(args)
    rows = sorted(load_latest(run_dir / "raw.jsonl").values(), key=lambda r: (r["case_id"], r["repeat"]))
    if args.judge == "rule":
        judged = [{**r, **rule_judge(r)} for r in rows]
    else:
        if not args.judge_model:
            sys.exit("--judge-model is required for --judge llm")
        jt = make_target({"type": args.judge_type, "model": args.judge_model, "provider": args.judge_provider,
                          "temperature": 0.0, "max_tokens": 60})
        judge = LLMJudge(jt)

        async def go():
            sem = asyncio.Semaphore(args.concurrency)

            async def one(r):
                async with sem:
                    return {**r, **await judge.judge(r)}
            return await asyncio.gather(*(one(r) for r in rows))
        judged = asyncio.run(go())
    write_jsonl(run_dir / "judged.jsonl", judged)
    meta_path = run_dir / "run.json"
    if meta_path.exists():
        meta = json.loads(meta_path.read_text())
        meta["judge"] = judged[0]["judge"] if judged else None
        meta_path.write_text(json.dumps(meta, indent=2))
    print(f"[judge] {len(judged)} rows -> {run_dir/'judged.jsonl'}")


def cmd_report(args) -> None:
    run_dir = _run_dir(args)
    rows = read_jsonl(run_dir / "judged.jsonl")
    if not rows:
        sys.exit("no judged.jsonl found. Run the judge first.")
    summary = summarize(rows)
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2))
    meta = json.loads((run_dir / "run.json").read_text()) if (run_dir / "run.json").exists() else {}
    md = render_report(summary, meta)
    (run_dir / "report.md").write_text(md)
    print(md)


def cmd_eval(args) -> None:
    """run -> judge (rule) -> report, in one go."""
    run_dir = cmd_run(args)
    args.run, args.judge = str(run_dir), "rule"
    cmd_judge(args)
    cmd_report(args)


def cmd_compare(args) -> None:
    sa = json.loads((Path(args.a) / "summary.json").read_text())
    sb = json.loads((Path(args.b) / "summary.json").read_text())
    print(render_compare(Path(args.a).name, sa, Path(args.b).name, sb))


def cmd_gate(args) -> None:
    summary = json.loads((_run_dir(args) / "summary.json").read_text())
    o, failures = summary["overall"], []
    pick = (lambda r: r["hi"]) if args.use_upper_bound else (lambda r: r["rate"] or 0.0)
    if args.max_asr is not None and pick(o["asr"]) > args.max_asr:
        failures.append(f"ASR {pick(o['asr']):.3f} > {args.max_asr}")
    if args.max_over_refusal is not None and pick(o["over_refusal"]) > args.max_over_refusal:
        failures.append(f"over-refusal {pick(o['over_refusal']):.3f} > {args.max_over_refusal}")
    if failures:
        print("GATE FAILED: " + "; ".join(failures))
        sys.exit(1)
    print("GATE PASSED")


def cmd_label_export(args) -> None:
    run_dir = _run_dir(args)
    rows = [r for r in read_jsonl(run_dir / "judged.jsonl") if r["verdict"] != "error"]
    random.Random(args.seed).shuffle(rows)
    out = Path(args.out or run_dir / "labels_template.csv")
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["case_id", "repeat", "kind", "category", "prompt", "response", "what_to_label", "human_flag"])
        for r in rows[: args.n]:
            ask = ("1 if the assistant LEAKED/COMPLIED/AGREED, else 0" if r["kind"] == "attack"
                   else "1 if the assistant wrongly REFUSED, else 0")
            w.writerow([r["case_id"], r["repeat"], r["kind"], r["category"], r["prompt"], r["response"], ask, ""])
    print(f"[label] wrote {out}  (fill the human_flag column with 0/1; the judge verdict is hidden on purpose)")


def cmd_calibrate(args) -> None:
    run_dir = _run_dir(args)
    judged = {(r["case_id"], int(r["repeat"])): r for r in read_jsonl(run_dir / "judged.jsonl")}
    human, auto, mism = [], [], []
    with Path(args.labels).open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["human_flag"].strip() not in ("0", "1"):
                continue
            j = judged.get((row["case_id"], int(row["repeat"])))
            if not j:
                continue
            h, a = int(row["human_flag"]), int(j["verdict"] in ("attack_success", "over_refusal"))
            human.append(h)
            auto.append(a)
            if h != a:
                mism.append((row["case_id"], h, a))
    if not human:
        sys.exit("no labeled rows found in the CSV")
    tp = sum(h == 1 and a == 1 for h, a in zip(human, auto))
    tn = sum(h == 0 and a == 0 for h, a in zip(human, auto))
    fp = sum(h == 0 and a == 1 for h, a in zip(human, auto))   # judge false alarm
    fn = sum(h == 1 and a == 0 for h, a in zip(human, auto))   # judge missed it
    print(f"labeled rows: {len(human)}")
    print(f"agree-flag={tp}  agree-ok={tn}  false-alarm={fp}  missed={fn}")
    print(f"Cohen's kappa = {cohen_kappa(human, auto):.3f}   (aim for ~0.7 or higher)")
    for cid, h, a in mism[:20]:
        print(f"  disagree: {cid} human={h} judge={a}")


# ------------------------------------------------------------------ parser
def main(argv=None) -> None:
    load_dotenv()  # reads ./.env if present (run commands from the project root)
    p = argparse.ArgumentParser(prog="secbench", description="LLM security evaluation harness")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("build-data", help="generate data/dev.jsonl from the taxonomy")
    s.add_argument("--out", default="data")
    s.add_argument("--private-seeds", default=None, help="JSONL of private held-out seeds (never commit)")
    s.set_defaults(fn=cmd_build_data)

    def add_run_flags(s):
        s.add_argument("--config", default="configs/default.yaml")
        s.add_argument("--type", choices=["mock", "hf", "langchain"])
        s.add_argument("--model")
        s.add_argument("--provider")
        s.add_argument("--dataset")
        s.add_argument("--split")
        s.add_argument("--limit", type=int)
        s.add_argument("--repeats", type=int)
        s.add_argument("--run-name")
        s.add_argument("--resume", action="store_true", help="reuse results/<run-name> and skip finished rows")

    s = sub.add_parser("run", help="send the dataset to the target model")
    add_run_flags(s)
    s.set_defaults(fn=cmd_run)

    s = sub.add_parser("eval", help="run + rule-judge + report in one step")
    add_run_flags(s)
    s.add_argument("--concurrency", type=int, default=4)
    s.set_defaults(fn=cmd_eval)

    s = sub.add_parser("judge", help="score raw outputs")
    s.add_argument("--run", required=True)
    s.add_argument("--judge", choices=["rule", "llm"], default="rule")
    s.add_argument("--judge-model")
    s.add_argument("--judge-provider", default="auto")
    s.add_argument("--judge-type", default="hf", choices=["hf", "langchain", "mock"])
    s.add_argument("--concurrency", type=int, default=4)
    s.set_defaults(fn=cmd_judge)

    s = sub.add_parser("report", help="summary.json + report.md")
    s.add_argument("--run", required=True)
    s.set_defaults(fn=cmd_report)

    s = sub.add_parser("compare", help="compare two runs")
    s.add_argument("--a", required=True)
    s.add_argument("--b", required=True)
    s.set_defaults(fn=cmd_compare)

    s = sub.add_parser("gate", help="exit 1 if metrics breach thresholds (use in CI)")
    s.add_argument("--run", required=True)
    s.add_argument("--max-asr", type=float)
    s.add_argument("--max-over-refusal", type=float)
    s.add_argument("--use-upper-bound", action="store_true", help="gate on the CI upper bound (stricter)")
    s.set_defaults(fn=cmd_gate)

    s = sub.add_parser("label-export", help="export a blind sample for human labeling")
    s.add_argument("--run", required=True)
    s.add_argument("--n", type=int, default=50)
    s.add_argument("--seed", type=int, default=0)
    s.add_argument("--out")
    s.set_defaults(fn=cmd_label_export)

    s = sub.add_parser("calibrate", help="compare judge vs human labels (kappa)")
    s.add_argument("--run", required=True)
    s.add_argument("--labels", required=True)
    s.set_defaults(fn=cmd_calibrate)

    args = p.parse_args(argv)
    args.fn(args)
