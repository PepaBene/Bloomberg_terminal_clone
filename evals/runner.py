"""Async batch eval runner.

Loads golden examples for a category, runs the system-under-test against
each one, applies the cheap deterministic checks (must_include/
must_not_include/max_tokens) always, and the LLM judge when a live client is
available, then diffs the summary against a stored baseline to catch
regressions -- the "regression > 0.5 fails build" CI gate the superseded
plan's Phase 0.2 decided on, folded in here per this plan's header note.

``target`` is any async callable the caller wires up per feature (a thin
wrapper around that feature's agent/engine) -- this module has no opinion on
how a response gets generated, only on how it's checked.
"""
from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from evals.judge import JudgeScore, judge_response
from evals.schema import GoldenExample, load_golden_examples

BASELINE_DIR = Path(__file__).parent / "baselines"
DEFAULT_JUDGE_PASS_THRESHOLD = 6.0
DEFAULT_MAX_REGRESSION = 0.5  # matches the plan's decided CI gate

Target = Callable[[dict[str, Any]], Awaitable[str]]


@dataclass(frozen=True)
class DeterministicResult:
    passed: bool
    missing_required: list[str] = field(default_factory=list)
    forbidden_found: list[str] = field(default_factory=list)
    over_max_tokens: bool = False


@dataclass(frozen=True)
class ExampleResult:
    example_id: str
    response_text: str
    deterministic: DeterministicResult
    judge_score: JudgeScore | None = None
    judge_pass_threshold: float = DEFAULT_JUDGE_PASS_THRESHOLD

    @property
    def passed(self) -> bool:
        judge_ok = self.judge_score is None or self.judge_score.overall >= self.judge_pass_threshold
        return self.deterministic.passed and judge_ok


def check_deterministic(example: GoldenExample, response_text: str) -> DeterministicResult:
    """Pure: the cheap checks that don't need an LLM call.

    Token count is the chars/4 approximation used elsewhere in this
    codebase (no tokenizer dependency) -- fine for a soft length gate, not
    exact.
    """
    lowered = response_text.lower()
    missing = [s for s in example.must_include if s.lower() not in lowered]
    forbidden = [s for s in example.must_not_include if s.lower() in lowered]
    approx_tokens = len(response_text) // 4
    over = example.max_tokens is not None and approx_tokens > example.max_tokens
    return DeterministicResult(
        passed=not missing and not forbidden and not over,
        missing_required=missing, forbidden_found=forbidden, over_max_tokens=over,
    )


async def run_category(
    category: str,
    target: Target,
    *,
    judge_client: Any = None,
    judge_pass_threshold: float = DEFAULT_JUDGE_PASS_THRESHOLD,
    question_key: str = "question",
    context_key: str = "context",
) -> list[ExampleResult]:
    """Run every golden example in ``category`` through ``target``.

    ``judge_client`` is optional and skipped when disabled/``None`` -- the
    deterministic checks alone still run, so this is usable in an
    environment with no configured Anthropic key (this sandbox included).
    """
    results = []
    for example in load_golden_examples(category):
        response_text = await target(example.inputs)
        det = check_deterministic(example, response_text)

        judge_score = None
        if judge_client is not None and getattr(judge_client, "enabled", False):
            judge_score = await judge_response(
                judge_client,
                question=str(example.inputs.get(question_key, "")),
                context=str(example.inputs.get(context_key, "")),
                response=response_text,
                rubric_notes=example.notes,
            )

        results.append(ExampleResult(
            example_id=example.id, response_text=response_text,
            deterministic=det, judge_score=judge_score,
            judge_pass_threshold=judge_pass_threshold,
        ))
    return results


def summarize(results: list[ExampleResult]) -> dict[str, Any]:
    """Pure. ``avg_judge_overall`` is ``None`` when no example was judged
    (e.g. no live AI client), which callers must treat as "no signal yet",
    not as a score of zero.
    """
    total = len(results)
    passed = sum(1 for r in results if r.passed)
    judged = [r.judge_score.overall for r in results if r.judge_score is not None]
    return {
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "avg_judge_overall": (sum(judged) / len(judged)) if judged else None,
    }


def save_baseline(category: str, summary: dict[str, Any]) -> None:
    BASELINE_DIR.mkdir(parents=True, exist_ok=True)
    (BASELINE_DIR / f"{category}.json").write_text(json.dumps(summary, indent=2))


def load_baseline(category: str) -> dict[str, Any] | None:
    path = BASELINE_DIR / f"{category}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text())


def check_regression(
    category: str,
    summary: dict[str, Any],
    *,
    max_drop: float = DEFAULT_MAX_REGRESSION,
) -> tuple[bool, str]:
    """Compare ``summary`` against the stored baseline for ``category``.

    No prior baseline, or either side missing a judge score -> never a
    regression (first run establishes the baseline; deterministic-only runs
    have nothing to diff on the judge axis).
    """
    baseline = load_baseline(category)
    if (
        baseline is None
        or baseline.get("avg_judge_overall") is None
        or summary.get("avg_judge_overall") is None
    ):
        return False, "no baseline to compare against"
    drop = baseline["avg_judge_overall"] - summary["avg_judge_overall"]
    if drop > max_drop:
        return True, (
            f"avg_judge_overall dropped {drop:.2f} "
            f"(baseline={baseline['avg_judge_overall']:.2f}, now={summary['avg_judge_overall']:.2f})"
        )
    return False, f"within tolerance (drop={drop:.2f})"
