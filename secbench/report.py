"""Markdown report + comparison tables (dependency-free, GitHub renders it)."""
from __future__ import annotations


def fmt(r: dict) -> str:
    if not r or r["n"] == 0:
        return "n/a"
    return f"{r['rate']*100:.1f}% ({r['lo']*100:.0f}-{r['hi']*100:.0f}%, n={r['n']})"


def bar(rate, width: int = 20) -> str:
    if rate is None:
        return ""
    k = round(rate * width)
    return "█" * k + "░" * (width - k)


def overlap(a: dict, b: dict) -> bool:
    return not (a["hi"] < b["lo"] or b["hi"] < a["lo"])


def render_report(summary: dict, meta: dict) -> str:
    o = summary["overall"]
    lines = [
        f"# Security evaluation report: {meta.get('run_name', 'run')}", "",
        f"- Model: `{meta.get('target', {}).get('model', meta.get('target', {}).get('type', '?'))}`",
        f"- Dataset: `{meta.get('dataset', {}).get('path', '?')}` "
        f"(sha256 `{str(meta.get('dataset', {}).get('sha256', ''))[:12]}`)",
        f"- Judge: `{meta.get('judge', 'rule-v1')}`  |  rows: {o['rows']}  |  errors: {o['errors']}", "",
        "## Headline", "",
        "| Metric | Value (95% Wilson CI) | |", "|---|---|---|",
        f"| Attack success rate (lower is better) | {fmt(o['asr'])} | `{bar(o['asr']['rate'])}` |",
        f"| Over-refusal rate (lower is better) | {fmt(o['over_refusal'])} | `{bar(o['over_refusal']['rate'])}` |",
        "", "## By category", "", "| Category | ASR | Over-refusal |", "|---|---|---|",
    ]
    for cat, v in summary["by_category"].items():
        lines.append(f"| {cat} | {fmt(v['asr'])} | {fmt(v['over_refusal'])} |")
    lines += ["", "## By technique", "", "| Technique | ASR |", "|---|---|"]
    for tech, v in summary["by_technique"].items():
        lines.append(f"| {tech} | {fmt(v['asr'])} |")
    techs = sorted({t for row in summary["grid"].values() for t in row})
    lines += ["", "## ASR grid (category x technique)", "",
              "| Category | " + " | ".join(techs) + " |", "|---|" + "---|" * len(techs)]
    for cat, row in summary["grid"].items():
        cells = [("n/a" if row.get(t, {"n": 0})["n"] == 0 else f"{row[t]['rate']*100:.0f}% (n={row[t]['n']})")
                 for t in techs]
        lines.append(f"| {cat} | " + " | ".join(cells) + " |")
    lines += ["", "> Small n means wide intervals. Treat single-digit-n cells as hints, not conclusions.", ""]
    return "\n".join(lines)


def render_compare(name_a: str, sa: dict, name_b: str, sb: dict) -> str:
    lines = [f"| Metric | {name_a} | {name_b} | Intervals |", "|---|---|---|---|"]
    for label, key in (("ASR", "asr"), ("Over-refusal", "over_refusal")):
        a, b = sa["overall"][key], sb["overall"][key]
        verdict = "overlap: no clear winner" if overlap(a, b) else "separated: difference is real"
        lines.append(f"| {label} | {fmt(a)} | {fmt(b)} | {verdict} |")
    return "\n".join(lines)
