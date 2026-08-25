"""CLI entrypoint for the §6 eval harness: run every golden category
(``evals/golden/<category>/*.yaml``) through the production grounded-answer
prompt, score with the LLM judge, and fail the run on a deterministic
check failure or a regression against the stored baseline.

Every golden example's ``inputs`` is a ``{question, context}`` pair
regardless of its category label (semantic_search, company_primer,
investment_thesis, morning_briefing, anomaly_narrative, analyst_qa) --
they all exercise the same capability (answer strictly from the given
context, cite sources, don't fabricate), just phrased as different task
framings. The ``analyst_qa`` prompt (src/ai/prompts/v1/analyst_qa.yaml)
is the one production prompt whose template shape is exactly
``question`` + ``context``, so it is reused as the single target across
every category rather than inventing a separate bespoke prompt per
category that the golden suite was never written against.

Mirrors this codebase's graceful-degradation contract used everywhere
else in the AI core: with no ANTHROPIC_API_KEY configured (a fork's PR,
or a CI run with no secret configured), the AI client is disabled and
there is no meaningful response to grade -- this exits 0 with a
"skipped" notice instead of failing every example on an empty response.

Usage:
    python -m scripts.run_evals                 # check against baseline
    python -m scripts.run_evals --update-baseline  # (re)write the baseline
"""
from __future__ import annotations

import asyncio
import sys

from evals.runner import check_regression, run_category, save_baseline, summarize
from evals.schema import list_categories
from src.ai.client import get_ai_client
from src.ai.prompts import load_prompt


async def _target(inputs: dict) -> str:
    client = get_ai_client()
    prompt = load_prompt("analyst_qa")
    text = await client.complete_text(
        user=prompt.render(
            question=inputs.get("question", ""), context=inputs.get("context", "")
        ),
        system=prompt.system,
        tier=prompt.tier,
        max_tokens=prompt.max_tokens,
        feature=prompt.feature,
    )
    return text or ""


async def main(argv: list[str]) -> int:
    client = get_ai_client()
    if not client.enabled:
        print("AI disabled (no ANTHROPIC_API_KEY) -- skipping golden eval checks.")
        return 0

    categories = list_categories()
    if not categories:
        print("No golden example categories found under evals/golden/.")
        return 0

    update_baseline = "--update-baseline" in argv
    failed = False

    for category in categories:
        results = await run_category(category, _target, judge_client=client)
        if not results:
            continue
        summary = summarize(results)
        regressed, reason = check_regression(category, summary)

        print(
            f"[{category}] {summary['passed']}/{summary['total']} passed, "
            f"avg_judge_overall={summary['avg_judge_overall']}, regression_check={reason}"
        )
        for r in results:
            if not r.passed:
                failed = True
                print(
                    f"  FAIL {r.example_id}: missing_required={r.deterministic.missing_required} "
                    f"forbidden_found={r.deterministic.forbidden_found} "
                    f"over_max_tokens={r.deterministic.over_max_tokens} "
                    f"judge_overall={r.judge_score.overall if r.judge_score else None}"
                )
        if regressed:
            failed = True
            print(f"  REGRESSION in {category}: {reason}")

        if update_baseline:
            save_baseline(category, summary)

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main(sys.argv[1:])))
