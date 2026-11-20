import pytest

from secbench.metrics import cohen_kappa, summarize, wilson_interval


def test_wilson_matches_reference_values():
    lo, hi = wilson_interval(3, 20)
    assert lo == pytest.approx(0.0524, abs=1e-3)
    assert hi == pytest.approx(0.3604, abs=1e-3)


def test_wilson_narrows_with_more_samples():
    lo1, hi1 = wilson_interval(3, 20)
    lo2, hi2 = wilson_interval(30, 200)
    assert (hi2 - lo2) < (hi1 - lo1)


def test_wilson_edges():
    assert wilson_interval(0, 0) == (0.0, 1.0)
    lo, hi = wilson_interval(0, 10)
    assert lo == 0.0 and 0 < hi < 0.35


def test_kappa_perfect_and_chance():
    assert cohen_kappa([1, 0, 1, 0], [1, 0, 1, 0]) == 1.0
    assert cohen_kappa([1, 1, 0, 0], [1, 0, 1, 0]) == pytest.approx(0.0)


def test_summarize_excludes_errors_from_denominator():
    rows = [
        {"kind": "attack", "category": "a", "technique": "direct", "verdict": "attack_success"},
        {"kind": "attack", "category": "a", "technique": "direct", "verdict": "attack_blocked"},
        {"kind": "attack", "category": "a", "technique": "direct", "verdict": "error"},
        {"kind": "benign", "category": "a", "technique": "benign", "verdict": "benign_ok"},
    ]
    s = summarize(rows)
    assert s["overall"]["asr"]["n"] == 2 and s["overall"]["asr"]["rate"] == 0.5
    assert s["overall"]["errors"] == 1
