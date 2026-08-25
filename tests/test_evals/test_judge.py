"""Tests for evals/judge.py."""
from __future__ import annotations

import pytest

from evals.judge import JudgeScore, build_judge_prompt, judge_response


def test_build_judge_prompt_includes_all_sections():
    prompt = build_judge_prompt(
        question="What is X?", context="X is Y [doc1].", response="X is Y.",
        rubric_notes="Check for grounding.",
    )
    assert "What is X?" in prompt
    assert "X is Y [doc1]." in prompt
    assert "X is Y." in prompt
    assert "Check for grounding." in prompt


def test_build_judge_prompt_handles_empty_rubric_notes():
    prompt = build_judge_prompt(question="q", context="c", response="r")
    assert "(none)" in prompt


def test_judge_score_overall_averages_five_criteria():
    score = JudgeScore(
        faithfulness=10, citation_correctness=8, hallucination=10,
        date_awareness=6, tone=6, rationale="ok",
    )
    assert score.overall == pytest.approx(8.0)


def test_judge_score_bounds_enforced():
    with pytest.raises(ValueError):
        JudgeScore(
            faithfulness=11, citation_correctness=5, hallucination=5,
            date_awareness=5, tone=5, rationale="x",
        )


class _DisabledClient:
    enabled = False


async def test_judge_response_raises_when_client_disabled():
    with pytest.raises(RuntimeError):
        await judge_response(
            _DisabledClient(), question="q", context="c", response="r",
        )
