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
    # A single-sentence elevator pitch, not full thesis generation/validation
    # -- deliberately lighter than "investment_thesis" above (DEEP/opus would
    # be a real cost mismatch for a <400-char one-liner).
    "investment_thesis_pitch": Tier.SYNTHESIS,
    "analyst_qa": Tier.SYNTHESIS,
    "earnings_narrative": Tier.LIGHT,
    "rating_narrative": Tier.LIGHT,
    "legacy_narrative": Tier.SYNTHESIS,
    # §4.7 Pillar-3 follow-through: commodity price/supply and insider/
    # congressional-disclosure narratives (src/ai/narratives/).
    "commodity_narrative": Tier.LIGHT,
    "insider_narrative": Tier.LIGHT,
    # Ingestion-side AI augmentation (not a router; src/ingestion/guidance_extraction.py)
    "guidance_extraction": Tier.LIGHT,
}


def tier_for(feature: str, override: Tier | str | None = None) -> Tier:
    """Return the tier for a feature, honoring an explicit override."""
    if override is not None:
        return Tier(override)
    return FEATURE_TIER.get(feature, Tier.SYNTHESIS)
