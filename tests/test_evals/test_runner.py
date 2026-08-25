"""Tests for evals/runner.py — deterministic checks, run_category orchestration,
and baseline/regression diffing.
"""
from __future__ import annotations

import pytest

import evals.runner as runner_module
from evals.judge import JudgeScore
from evals.runner import (
    ExampleResult,
    check_deterministic,
    check_regression,
    load_baseline,
    run_category,
    save_baseline,
    summarize,
)
from evals.schema import GoldenExample


def _example(**overrides) -> GoldenExample:
    base = dict(
        id="ex1", category="analyst_qa",
        inputs={"question": "q", "context": "c"},
        must_include=[], must_not_include=[], max_tokens=None,
    )
    base.update(overrides)
    return GoldenExample(**base)


# --------------------------------------------------------------------------- #
# check_deterministic (pure)
# --------------------------------------------------------------------------- #
def test_check_deterministic_all_pass():
    ex = _example(must_include=["roe"], must_not_include=["cannot determine"])
    result = check_deterministic(ex, "The ROE was 18%.")
    assert result.passed is True
    assert result.missing_required == []
    assert result.forbidden_found == []


def test_check_deterministic_missing_required():
    ex = _example(must_include=["roe", "18%"])
    result = check_deterministic(ex, "Some unrelated answer.")
    assert result.passed is False
    assert set(result.missing_required) == {"roe", "18%"}


def test_check_deterministic_forbidden_found():
    ex = _example(must_not_include=["i don't know"])
    result = check_deterministic(ex, "I don't know the answer.")
    assert result.passed is False
    assert result.forbidden_found == ["i don't know"]


def test_check_deterministic_over_max_tokens():
    ex = _example(max_tokens=5)  # ~20 chars
    result = check_deterministic(ex, "x" * 100)
    assert result.passed is False
    assert result.over_max_tokens is True


def test_check_deterministic_is_case_insensitive():
    ex = _example(must_include=["ROE"])
    assert check_deterministic(ex, "the roe was strong").passed is True


# --------------------------------------------------------------------------- #
# run_category (orchestration)
# --------------------------------------------------------------------------- #
class FakeJudgeClient:
    def __init__(self, score: JudgeScore, *, enabled: bool = True):
        self._score = score
        self.enabled = enabled

    async def complete_structured(self, **kwargs):
        return self._score


GOOD_SCORE = JudgeScore(
    faithfulness=9, citation_correctness=9, hallucination=10,
    date_awareness=10, tone=8, rationale="solid",
)
BAD_SCORE = JudgeScore(
    faithfulness=2, citation_correctness=1, hallucination=1,
    date_awareness=5, tone=5, rationale="fabricated facts",
)


async def test_run_category_deterministic_only_no_judge_client(monkeypatch):
    def fake_load(category):
        return [_example(id="a", must_include=["ok"])]
    monkeypatch.setattr(runner_module, "load_golden_examples", fake_load)

    async def target(inputs):
        return "this is ok"

    results = await run_category("analyst_qa", target)
    assert len(results) == 1
    assert results[0].judge_score is None
    assert results[0].passed is True


async def test_run_category_with_passing_judge(monkeypatch):
    def fake_load(category):
        return [_example(id="a")]
    monkeypatch.setattr(runner_module, "load_golden_examples", fake_load)

    async def target(inputs):
        return "a fine response"

    results = await run_category("analyst_qa", target, judge_client=FakeJudgeClient(GOOD_SCORE))
    assert results[0].judge_score.overall == pytest.approx(9.2)
    assert results[0].passed is True


async def test_run_category_with_failing_judge(monkeypatch):
    def fake_load(category):
        return [_example(id="a")]
    monkeypatch.setattr(runner_module, "load_golden_examples", fake_load)

    async def target(inputs):
        return "a bad response"

    results = await run_category("analyst_qa", target, judge_client=FakeJudgeClient(BAD_SCORE))
    assert results[0].judge_score.overall < 6.0
    assert results[0].passed is False


async def test_run_category_skips_judge_when_disabled(monkeypatch):
    def fake_load(category):
        return [_example(id="a")]
    monkeypatch.setattr(runner_module, "load_golden_examples", fake_load)

    async def target(inputs):
        return "response"

    results = await run_category(
        "analyst_qa", target, judge_client=FakeJudgeClient(GOOD_SCORE, enabled=False)
    )
    assert results[0].judge_score is None


# --------------------------------------------------------------------------- #
# summarize (pure)
# --------------------------------------------------------------------------- #
def _result(passed_det=True, judge_overall=None):
    from evals.runner import DeterministicResult
    det = DeterministicResult(passed=passed_det)
    judge = None
    if judge_overall is not None:
        judge = JudgeScore(
            faithfulness=int(judge_overall), citation_correctness=int(judge_overall),
            hallucination=int(judge_overall), date_awareness=int(judge_overall),
            tone=int(judge_overall), rationale="x",
        )
    return ExampleResult(example_id="e", response_text="r", deterministic=det, judge_score=judge)


def test_summarize_counts_and_average():
    results = [_result(True, 9), _result(False, 3), _result(True, None)]
    summary = summarize(results)
    assert summary["total"] == 3
    assert summary["passed"] == 2  # third passes (det ok, no judge score to fail it)
    assert summary["failed"] == 1
    assert summary["avg_judge_overall"] == pytest.approx(6.0)


def test_summarize_no_judge_scores_gives_none():
    results = [_result(True, None), _result(True, None)]
    summary = summarize(results)
    assert summary["avg_judge_overall"] is None


# --------------------------------------------------------------------------- #
# baseline / regression
# --------------------------------------------------------------------------- #
def test_save_and_load_baseline_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(runner_module, "BASELINE_DIR", tmp_path)
    summary = {"total": 5, "passed": 5, "failed": 0, "avg_judge_overall": 8.5}
    save_baseline("analyst_qa", summary)
    loaded = load_baseline("analyst_qa")
    assert loaded == summary


def test_load_baseline_missing_returns_none(tmp_path, monkeypatch):
    monkeypatch.setattr(runner_module, "BASELINE_DIR", tmp_path)
    assert load_baseline("no_such_category") is None


def test_check_regression_no_baseline_is_not_a_regression(tmp_path, monkeypatch):
    monkeypatch.setattr(runner_module, "BASELINE_DIR", tmp_path)
    regressed, msg = check_regression("analyst_qa", {"avg_judge_overall": 7.0})
    assert regressed is False
    assert "no baseline" in msg


def test_check_regression_within_tolerance(tmp_path, monkeypatch):
    monkeypatch.setattr(runner_module, "BASELINE_DIR", tmp_path)
    save_baseline("analyst_qa", {"avg_judge_overall": 8.0})
    regressed, msg = check_regression("analyst_qa", {"avg_judge_overall": 7.7})
    assert regressed is False


def test_check_regression_drop_exceeds_threshold(tmp_path, monkeypatch):
    monkeypatch.setattr(runner_module, "BASELINE_DIR", tmp_path)
    save_baseline("analyst_qa", {"avg_judge_overall": 8.0})
    regressed, msg = check_regression("analyst_qa", {"avg_judge_overall": 7.0}, max_drop=0.5)
    assert regressed is True
    assert "dropped" in msg
