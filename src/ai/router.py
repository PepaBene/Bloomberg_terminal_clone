"""Task → model-tier routing.

Each AI feature declares which cost/capability tier it should run at by default.
Callers may override per-request (e.g. a user paying for a "deep" answer). Keep
this list in sync as features are migrated onto the new core.
"""
from __future__ import annotations

from src.ai.models import Tier

FEATURE_TIER: dict[str, Tier] = {
    # Layer 1 — Interpreter
    "interpret_metric": Tier.LIGHT,
    "interpret_subject": Tier.SYNTHESIS,
    # Layer 2 — News / Information
    "news_article_summary": Tier.LIGHT,
    "sentiment_score": Tier.LIGHT,
    "news_cluster_analysis": Tier.SYNTHESIS,
    "deep_research": Tier.DEEP,
    # Layer 3 — Adviser
    "adviser_chat": Tier.SYNTHESIS,
    "adviser_recommendation": Tier.DEEP,
    # Legacy narrative features (kept working via the shim during migration)
    "company_primer": Tier.SYNTHESIS,
    "company_briefing": Tier.SYNTHESIS,
    "morning_briefing": Tier.SYNTHESIS,
    "investment_thesis": Tier.DEEP,
    "analyst_qa": Tier.SYNTHESIS,
    "earnings_narrative": Tier.LIGHT,
    "rating_narrative": Tier.LIGHT,
    "legacy_narrative": Tier.SYNTHESIS,
}


def tier_for(feature: str, override: Tier | str | None = None) -> Tier:
    """Return the tier for a feature, honoring an explicit override."""
    if override is not None:
        return Tier(override)
    return FEATURE_TIER.get(feature, Tier.SYNTHESIS)
