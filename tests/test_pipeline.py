import asyncio

import pytest

from secbench.dataset import TECHNIQUES, build_dev_cases
from secbench.judges import rule_judge
from secbench.metrics import summarize
from secbench.runner import load_latest, run_cases
from secbench.targets import MockTarget


def test_dataset_grid_is_complete():
    cases = build_dev_cases()
    attacks = [c for c in cases if c.kind == "attack"]
    benign = [c for c in cases if c.kind == "benign"]
    assert len(attacks) == 4 * len(TECHNIQUES) * 5 and len(benign) == 20
    assert len({c.id for c in cases}) == len(cases)           # unique ids
    cells = {(c.category, c.technique) for c in attacks}
    assert len(cells) == 4 * len(TECHNIQUES)                  # no empty cells


def _run(mode, tmp_path, repeats=1):
    out = tmp_path / "raw.jsonl"
    asyncio.run(run_cases(build_dev_cases(), MockTarget(mode=mode), "sys", out, run_id="t", model="mock",
                          repeats=repeats, verbose=False))
    rows = sorted(load_latest(out).values(), key=lambda r: (r["case_id"], r["repeat"]))
    return out, [{**r, **rule_judge(r)} for r in rows]


def test_partial_mock_end_to_end(tmp_path):
    _, judged = _run("partial", tmp_path)
    s = summarize(judged)
    assert s["overall"]["asr"]["rate"] == pytest.approx(0.75)           # 3 of 4 techniques succeed
    assert s["by_technique"]["direct"]["asr"]["rate"] == 0.0
    assert s["overall"]["over_refusal"]["rate"] == pytest.approx(0.30)  # mock's over-eager filter


def test_safe_mock_has_zero_asr(tmp_path):
    _, judged = _run("safe", tmp_path)
    assert summarize(judged)["overall"]["asr"]["rate"] == 0.0


def test_resume_skips_finished_rows(tmp_path):
    out, _ = _run("safe", tmp_path)
    n_before = len(out.read_text().splitlines())
    again = asyncio.run(run_cases(build_dev_cases(), MockTarget("safe"), "sys", out, run_id="t", model="mock",
                                  verbose=False))
    assert again == 0 and len(out.read_text().splitlines()) == n_before


def test_failures_are_recorded_not_dropped(tmp_path):
    class Boom:
        async def generate(self, system, user):
            raise RuntimeError("rate limited")
    out = tmp_path / "raw.jsonl"
    asyncio.run(run_cases(build_dev_cases()[:3], Boom(), "sys", out, run_id="t", model="boom",
                          max_retries=0, verbose=False))
    rows = load_latest(out).values()
    assert len(rows) == 3 and all(r["status"] == "error" for r in rows)
