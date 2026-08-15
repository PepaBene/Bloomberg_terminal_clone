"""Unit tests for scripts/run_evals.py's own orchestration logic (the CLI
entrypoint for the §6 eval harness). ``run_category``/``summarize``/
``check_regression``/``save_baseline`` are already covered by
tests/test_evals/test_runner.py -- these tests mock those at the
scripts.run_evals import seam so they exercise only what's new here: the
disabled-client skip path, the per-category pass/fail/regression exit
code, ``--update-baseline`` wiring, and ``_target``'s prompt rendering.
"""
from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

import pytest

from scripts.run_evals import _target, main
from evals.runner import DeterministicResult, ExampleResult


class _FakeClient:
    def __init__(self, *, enabled: bool, text: str | None = "the answer [DOC-A]"):
        self.enabled = enabled
        self._text = text
        self.calls: list[dict] = []

    async def complete_text(self, **kwargs):
        self.calls.append(kwargs)
        return self._text


@pytest.mark.asyncio
class TestTarget:
    async def test_renders_prompt_and_returns_text(self, monkeypatch):
        client = _FakeClient(enabled=True, text="grounded answer [DOC-A]")
        monkeypatch.setattr("scripts.run_evals.get_ai_client", lambda: client)

        result = await _target({"question": "What is X?", "context": "X is Y. [DOC-A]"})

        assert result == "grounded answer [DOC-A]"
        assert len(client.calls) == 1
        assert "What is X?" in client.calls[0]["user"]
        assert "X is Y. [DOC-A]" in client.calls[0]["user"]
        assert client.calls[0]["feature"] == "analyst_qa"

    async def test_none_response_becomes_empty_string(self, monkeypatch):
        client = _FakeClient(enabled=True, text=None)
        monkeypatch.setattr("scripts.run_evals.get_ai_client", lambda: client)

        result = await _target({"question": "q", "context": "c"})

        assert result == ""

    async def test_missing_inputs_default_to_empty_strings(self, monkeypatch):
        client = _FakeClient(enabled=True)
        monkeypatch.setattr("scripts.run_evals.get_ai_client", lambda: client)

        await _target({})  # no 'question'/'context' keys — must not raise

        assert len(client.calls) == 1


def _passing_result(example_id: str) -> ExampleResult:
    return ExampleResult(
        example_id=example_id, response_text="ok",
        deterministic=DeterministicResult(passed=True),
    )


def _failing_result(example_id: str) -> ExampleResult:
    return ExampleResult(
        example_id=example_id, response_text="bad",
        deterministic=DeterministicResult(passed=False, missing_required=["x"]),
    )


@pytest.mark.asyncio
class TestMain:
    async def test_disabled_client_skips_and_returns_zero(self, monkeypatch):
        client = _FakeClient(enabled=False)
        monkeypatch.setattr("scripts.run_evals.get_ai_client", lambda: client)
        called = False

        async def _should_not_run(*a, **kw):
            nonlocal called
            called = True

        monkeypatch.setattr("scripts.run_evals.run_category", _should_not_run)

        code = await main([])

        assert code == 0
        assert called is False

    async def test_no_categories_returns_zero(self, monkeypatch):
        client = _FakeClient(enabled=True)
        monkeypatch.setattr("scripts.run_evals.get_ai_client", lambda: client)
        monkeypatch.setattr("scripts.run_evals.list_categories", lambda: [])

        assert await main([]) == 0

    async def test_all_passing_no_regression_returns_zero(self, monkeypatch):
        client = _FakeClient(enabled=True)
        monkeypatch.setattr("scripts.run_evals.get_ai_client", lambda: client)
        monkeypatch.setattr("scripts.run_evals.list_categories", lambda: ["cat_a"])

        async def _run_category(category, target, judge_client=None):
            return [_passing_result("cat_a_001")]

        monkeypatch.setattr("scripts.run_evals.run_category", _run_category)
        monkeypatch.setattr(
            "scripts.run_evals.summarize",
            lambda results: {"total": 1, "passed": 1, "failed": 0, "avg_judge_overall": 9.0},
        )
        monkeypatch.setattr(
            "scripts.run_evals.check_regression", lambda cat, summary: (False, "within tolerance")
        )
        saved = []
        monkeypatch.setattr(
            "scripts.run_evals.save_baseline", lambda cat, summary: saved.append((cat, summary))
        )

        code = await main([])

        assert code == 0
        assert saved == []  # no --update-baseline flag => baseline untouched

    async def test_failing_example_returns_one(self, monkeypatch):
        client = _FakeClient(enabled=True)
        monkeypatch.setattr("scripts.run_evals.get_ai_client", lambda: client)
        monkeypatch.setattr("scripts.run_evals.list_categories", lambda: ["cat_a"])

        async def _run_category(category, target, judge_client=None):
            return [_failing_result("cat_a_001")]

        monkeypatch.setattr("scripts.run_evals.run_category", _run_category)
        monkeypatch.setattr(
            "scripts.run_evals.summarize",
            lambda results: {"total": 1, "passed": 0, "failed": 1, "avg_judge_overall": None},
        )
        monkeypatch.setattr(
            "scripts.run_evals.check_regression", lambda cat, summary: (False, "no baseline")
        )

        assert await main([]) == 1

    async def test_regression_returns_one_even_if_examples_pass(self, monkeypatch):
        client = _FakeClient(enabled=True)
        monkeypatch.setattr("scripts.run_evals.get_ai_client", lambda: client)
        monkeypatch.setattr("scripts.run_evals.list_categories", lambda: ["cat_a"])

        async def _run_category(category, target, judge_client=None):
            return [_passing_result("cat_a_001")]

        monkeypatch.setattr("scripts.run_evals.run_category", _run_category)
        monkeypatch.setattr(
            "scripts.run_evals.summarize",
            lambda results: {"total": 1, "passed": 1, "failed": 0, "avg_judge_overall": 3.0},
        )
        monkeypatch.setattr(
            "scripts.run_evals.check_regression",
            lambda cat, summary: (True, "avg_judge_overall dropped 4.00"),
        )

        assert await main([]) == 1

    async def test_update_baseline_flag_saves_every_category(self, monkeypatch):
        client = _FakeClient(enabled=True)
        monkeypatch.setattr("scripts.run_evals.get_ai_client", lambda: client)
        monkeypatch.setattr("scripts.run_evals.list_categories", lambda: ["cat_a", "cat_b"])

        async def _run_category(category, target, judge_client=None):
            return [_passing_result(f"{category}_001")]

        monkeypatch.setattr("scripts.run_evals.run_category", _run_category)
        monkeypatch.setattr(
            "scripts.run_evals.summarize",
            lambda results: {"total": 1, "passed": 1, "failed": 0, "avg_judge_overall": 8.0},
        )
        monkeypatch.setattr(
            "scripts.run_evals.check_regression", lambda cat, summary: (False, "no baseline")
        )
        saved = []
        monkeypatch.setattr(
            "scripts.run_evals.save_baseline", lambda cat, summary: saved.append(cat)
        )

        code = await main(["--update-baseline"])

        assert code == 0
        assert saved == ["cat_a", "cat_b"]

    async def test_empty_category_results_are_skipped_without_crashing(self, monkeypatch):
        client = _FakeClient(enabled=True)
        monkeypatch.setattr("scripts.run_evals.get_ai_client", lambda: client)
        monkeypatch.setattr("scripts.run_evals.list_categories", lambda: ["empty_cat"])

        async def _run_category(category, target, judge_client=None):
            return []

        monkeypatch.setattr("scripts.run_evals.run_category", _run_category)

        assert await main([]) == 0
