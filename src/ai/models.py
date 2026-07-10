"""Model tiers, IDs, and pricing for the AI core.

Central place that maps a *tier* (light / synthesis / deep) to a concrete
Anthropic model id, and knows the approximate USD price per million tokens so
telemetry can attribute cost per call. Prices are list-price estimates — adjust
here if Anthropic pricing changes; nothing else needs to know the numbers.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Tier(str, Enum):
    """Cost/capability tier a feature routes to."""

    LIGHT = "light"          # cheap, high-volume: per-metric / per-article snippets
    SYNTHESIS = "synthesis"  # default: rollups, briefings, Q&A, adviser chat
    DEEP = "deep"            # highest-stakes: deep research, recommendations, scenarios


# Current Anthropic model ids (2026).
TIER_MODEL: dict[Tier, str] = {
    Tier.LIGHT: "claude-haiku-4-5",
    Tier.SYNTHESIS: "claude-sonnet-5",
    Tier.DEEP: "claude-opus-4-8",
}

DEFAULT_TIER = Tier.SYNTHESIS


@dataclass(frozen=True)
class Pricing:
    """USD per 1,000,000 tokens."""

    input: float
    output: float
    cache_write: float
    cache_read: float


# Approximate list prices (USD / 1M tokens). Editable in one place.
MODEL_PRICING: dict[str, Pricing] = {
    "claude-haiku-4-5": Pricing(input=1.0, output=5.0, cache_write=1.25, cache_read=0.10),
    "claude-sonnet-5": Pricing(input=3.0, output=15.0, cache_write=3.75, cache_read=0.30),
    "claude-opus-4-8": Pricing(input=15.0, output=75.0, cache_write=18.75, cache_read=1.50),
}


def model_for_tier(tier: Tier | str) -> str:
    """Resolve a tier (enum or string) to a concrete model id."""
    return TIER_MODEL[Tier(tier)]


def estimate_cost_usd(
    model: str,
    *,
    input_tokens: int = 0,
    output_tokens: int = 0,
    cache_write_tokens: int = 0,
    cache_read_tokens: int = 0,
) -> float:
    """Estimate the USD cost of a call from token counts. Unknown model → 0.0."""
    p = MODEL_PRICING.get(model)
    if p is None:
        return 0.0
    return (
        input_tokens * p.input
        + output_tokens * p.output
        + cache_write_tokens * p.cache_write
        + cache_read_tokens * p.cache_read
    ) / 1_000_000
