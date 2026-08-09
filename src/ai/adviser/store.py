"""Persistence + guardrails for Layer 3 recommendations (§5.4):
"Guardrails: every recommendation cites evidence, passes compliance,
includes a not-financial-advice disclaimer, and respects per-user cost
budgets."

Cost budgets are enforced upstream, before the adviser LLM call even
happens (``src.ai.guardrails.budget.check_budget``, called by the chat
endpoint per its own docstring: "an API route, before invoking the agent
loop"). The disclaimer is a fixed constant
(``src.ai.adviser.adviser.DISCLAIMER``) the chat endpoint attaches to
every response -- not something to bake into stored rationale text, which
should stay clean data. That leaves two guardrails this module actually
enforces, as a hard filter BEFORE persistence rather than a warning
alongside a bad row:

- Evidence: a recommendation with no cited evidence is dropped, not saved
  with an empty list -- an uncited recommendation is exactly the failure
  mode this codebase's citation guardrails (``src/ai/guardrails/
  citations.py``) exist to catch elsewhere; the same standard applies here.
- Compliance: a recommendation whose ``compliance`` check (real, verified
  data from ``adviser.verify_recommendation`` -- never the LLM's own
  account) came back NOT approved is dropped, not saved as a live
  proposal. Recommendations with no compliance check at all (non-trade
  advice, ``compliance is None``) pass through -- there's nothing to
  check.
"""
from __future__ import annotations

import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from src.ai.adviser.adviser import VerifiedRecommendation
from src.models.advice_recommendation import AdviceRecommendation

logger = logging.getLogger(__name__)


def passes_guardrails(verified: VerifiedRecommendation) -> tuple[bool, str | None]:
    """Pure: ``(ok, reason)`` -- ``reason`` is set only when ``ok`` is
    ``False``, for logging what got dropped and why."""
    if not verified.recommendation.evidence:
        return False, "no cited evidence"
    if verified.compliance is not None and not verified.compliance.get("approved", False):
        return False, "failed compliance check"
    return True, None


async def save_recommendations(
    session: AsyncSession,
    *,
    user_id: str,
    portfolio_id: uuid.UUID,
    verified: list[VerifiedRecommendation],
) -> list[AdviceRecommendation]:
    """Persist only the recommendations that pass ``passes_guardrails``.
    Returns the saved rows (may be fewer than ``len(verified)`` -- dropped
    ones are logged, not silently discarded without a trace).
    """
    saved: list[AdviceRecommendation] = []
    for v in verified:
        ok, reason = passes_guardrails(v)
        if not ok:
            logger.info(
                "dropping recommendation (kind=%s) for portfolio %s: %s",
                v.recommendation.kind, portfolio_id, reason,
            )
            continue
        row = AdviceRecommendation(
            id=uuid.uuid4(), user_id=user_id, portfolio_id=portfolio_id,
            kind=v.recommendation.kind, action=v.recommendation.action or None,
            rationale=v.recommendation.rationale, evidence=v.recommendation.evidence,
            whatif_impact=v.whatif_impact, compliance=v.compliance,
            confidence=v.recommendation.confidence, status="PROPOSED",
        )
        session.add(row)
        saved.append(row)
    if saved:
        await session.flush()
    return saved


async def set_recommendation_status(
    session: AsyncSession, recommendation_id: uuid.UUID, status: str,
) -> AdviceRecommendation | None:
    """Move a recommendation to ACCEPTED or DISMISSED. Returns ``None`` if
    it doesn't exist."""
    row = await session.get(AdviceRecommendation, recommendation_id)
    if row is None:
        return None
    row.status = status
    await session.flush()
    return row
