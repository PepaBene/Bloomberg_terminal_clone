"""Pillar 3 Phase 2 — Part 7a: Business Model Analysis Engine.

Pure computation engine for analyzing company business models:
revenue quality, unit economics, scaling behavior, and durability.

No database access — all functions accept and return plain data.
"""

from __future__ import annotations

import logging
import statistics
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# ── Dataclasses ───────────────────────────────────────────────────────────


@dataclass
class RevenueQuality:
    """Revenue quality assessment."""

    recurring_pct: float | None = None
    deferred_revenue_trend: str = "UNKNOWN"  # GROWING/STABLE/DECLINING
    customer_concentration: float | None = None  # top customer %
    diversification_score: float = 0.0  # 0-100
    cyclicality_score: float = 0.0  # 0-100 (higher = more cyclical)


@dataclass
class UnitEconomics:
    """Unit economics metrics."""

    revenue_per_employee: float | None = None
    revenue_per_subscriber: float | None = None
    contribution_margin_by_segment: dict[str, float] = field(default_factory=dict)


@dataclass
class ScalingBehavior:
    """Scaling and operating leverage metrics."""

    operating_leverage: float | None = None  # % change EBIT / % change revenue
    incremental_margin: float | None = None  # delta EBIT / delta revenue
    sga_scalability: float | None = None  # SGA growth / revenue growth (<1 = scalable)


@dataclass
class BusinessModelDurability:
    """Business model durability assessment."""

    switching_cost_score: float = 0.0  # 0-100
    moat_type: str | None = None  # NETWORK_EFFECT, BRAND, SCALE, COST, REGULATORY, NONE
    disruption_vulnerability: float = 50.0  # 0-100 (higher = more vulnerable)


@dataclass
class BusinessModelResult:
    """Complete business model analysis."""

    revenue_quality: RevenueQuality = field(default_factory=RevenueQuality)
    unit_economics: UnitEconomics = field(default_factory=UnitEconomics)
    scaling: ScalingBehavior = field(default_factory=ScalingBehavior)
    durability: BusinessModelDurability = field(default_factory=BusinessModelDurability)


# ── Revenue Quality Assessment ────────────────────────────────────────────


def _compute_trend(values: list[float]) -> str:
    """Classify a time series trend as GROWING/STABLE/DECLINING."""
    if len(values) < 2:
        return "UNKNOWN"
    first_half = statistics.mean(values[: len(values) // 2])
    second_half = statistics.mean(values[len(values) // 2 :])
    if first_half == 0:
        return "STABLE"
    change = (second_half - first_half) / abs(first_half)
    if change > 0.05:
        return "GROWING"
    elif change < -0.05:
        return "DECLINING"
    return "STABLE"


def _compute_diversification_score(
    geo_segments: int,
    product_segments: int,
    top_customer_pct: float | None,
) -> float:
    """Score revenue diversification 0-100.

    Higher segments + lower concentration = higher score.
    """
    score = 0.0

    # Geographic diversification (max 35 pts)
    score += min(geo_segments * 7.0, 35.0)

    # Product diversification (max 35 pts)
    score += min(product_segments * 7.0, 35.0)

    # Customer concentration (max 30 pts)
    if top_customer_pct is not None:
        if top_customer_pct < 10:
            score += 30.0
        elif top_customer_pct < 20:
            score += 20.0
        elif top_customer_pct < 40:
            score += 10.0
    else:
        score += 15.0  # Unknown = neutral

    return min(score, 100.0)


def _compute_cyclicality(revenue_history: list[float]) -> float:
    """Score cyclicality 0-100 from revenue volatility.

    Higher volatility = higher cyclicality score.
    """
    if len(revenue_history) < 3:
        logger.warning(
            "Cyclicality score defaulting to 50.0 (neutral): "
            "insufficient revenue history (%d periods, need >= 3)",
            len(revenue_history),
        )
        return 50.0  # Insufficient data — neutral default

    growth_rates = []
    for i in range(1, len(revenue_history)):
        if revenue_history[i - 1] != 0:
            gr = (revenue_history[i] - revenue_history[i - 1]) / abs(revenue_history[i - 1])
            growth_rates.append(gr)

    if not growth_rates:
        return 50.0

    volatility = statistics.stdev(growth_rates) if len(growth_rates) > 1 else 0.0
    # Map volatility to 0-100: 0% vol → 0, 30%+ vol → 100
    return min(volatility / 0.30 * 100.0, 100.0)


def assess_revenue_quality(financials: dict) -> RevenueQuality:
    """Assess revenue quality from financial data.

    Parameters
    ----------
    financials : dict
        Expected keys:
        - recurring_revenue_pct: float | None
        - deferred_revenue_history: list[float] (time series)
        - top_customer_pct: float | None
        - geo_segment_count: int
        - product_segment_count: int
        - revenue_history: list[float] (annual revenue time series)
    """
    recurring_pct = financials.get("recurring_revenue_pct")

    deferred = financials.get("deferred_revenue_history", [])
    deferred_trend = _compute_trend(deferred) if deferred else "UNKNOWN"

    top_customer = financials.get("top_customer_pct")
    geo_segs = financials.get("geo_segment_count", 1)
    prod_segs = financials.get("product_segment_count", 1)

    div_score = _compute_diversification_score(geo_segs, prod_segs, top_customer)
    cyc_score = _compute_cyclicality(financials.get("revenue_history", []))

    return RevenueQuality(
        recurring_pct=recurring_pct,
        deferred_revenue_trend=deferred_trend,
        customer_concentration=top_customer,
        diversification_score=round(div_score, 2),
        cyclicality_score=round(cyc_score, 2),
    )


# ── Unit Economics ────────────────────────────────────────────────────────


def compute_unit_economics(financials: dict) -> UnitEconomics:
    """Compute unit economics from financial data.

    Parameters
    ----------
    financials : dict
        Expected keys:
        - revenue: float
        - employee_count: int | None
        - subscriber_count: int | None
        - segments: list[{name, revenue, operating_income}]
    """
    revenue = financials.get("revenue", 0)
    employees = financials.get("employee_count")
    subscribers = financials.get("subscriber_count")

    rev_per_employee = None
    if employees and employees > 0 and revenue > 0:
        rev_per_employee = round(revenue / employees, 2)

    rev_per_sub = None
    if subscribers and subscribers > 0 and revenue > 0:
        rev_per_sub = round(revenue / subscribers, 2)

    margins = {}
    for seg in financials.get("segments", []):
        seg_rev = seg.get("revenue", 0)
        seg_income = seg.get("operating_income", 0)
        if seg_rev > 0:
            margins[seg.get("name", "Unknown")] = round(seg_income / seg_rev, 4)

    return UnitEconomics(
        revenue_per_employee=rev_per_employee,
        revenue_per_subscriber=rev_per_sub,
        contribution_margin_by_segment=margins,
    )


# ── Scaling Behavior ──────────────────────────────────────────────────────


def compute_scaling_behavior(history: list[dict]) -> ScalingBehavior:
    """Compute scaling behavior from multi-period financials.

    Parameters
    ----------
    history : list[dict]
        Each period has: revenue, ebit (operating_income), sga. Sorted oldest→newest.
    """
    if len(history) < 2:
        return ScalingBehavior()

    latest = history[-1]
    prior = history[-2]

    rev_now = latest.get("revenue", 0)
    rev_prior = prior.get("revenue", 0)
    ebit_now = latest.get("ebit", 0) or latest.get("operating_income", 0)
    ebit_prior = prior.get("ebit", 0) or prior.get("operating_income", 0)
    sga_now = latest.get("sga", 0)
    sga_prior = prior.get("sga", 0)

    # Operating leverage: % change EBIT / % change revenue
    op_lev = None
    if rev_prior and rev_prior != 0:
        rev_change = (rev_now - rev_prior) / abs(rev_prior)
        if abs(rev_change) > 0.001 and ebit_prior != 0:
            ebit_change = (ebit_now - ebit_prior) / abs(ebit_prior)
            op_lev = round(ebit_change / rev_change, 4)

    # Incremental margin: delta EBIT / delta revenue
    incr_margin = None
    delta_rev = rev_now - rev_prior
    delta_ebit = ebit_now - ebit_prior
    if abs(delta_rev) > 0:
        incr_margin = round(delta_ebit / delta_rev, 4)

    # SGA scalability: SGA growth / revenue growth
    sga_scal = None
    if rev_prior and rev_prior != 0 and sga_prior and sga_prior != 0:
        rev_gr = (rev_now - rev_prior) / abs(rev_prior)
        sga_gr = (sga_now - sga_prior) / abs(sga_prior)
        if abs(rev_gr) > 0.001:
            sga_scal = round(sga_gr / rev_gr, 4)

    return ScalingBehavior(
        operating_leverage=op_lev,
        incremental_margin=incr_margin,
        sga_scalability=sga_scal,
    )


# ── Business Model Durability ─────────────────────────────────────────────

MOAT_KEYWORDS = {
    "NETWORK_EFFECT": ["network", "marketplace", "platform", "ecosystem", "users"],
    "BRAND": ["brand", "premium", "reputation", "trust", "loyalty"],
    "SCALE": ["scale", "cost advantage", "economies of scale", "largest", "market leader"],
    "COST": ["low cost", "cost leader", "efficient", "lowest cost"],
    "REGULATORY": ["license", "regulatory", "patent", "exclusive", "barrier"],
}


def assess_business_model_durability(data: dict) -> BusinessModelDurability:
    """Assess business model durability.

    Parameters
    ----------
    data : dict
        Expected keys:
        - gross_margin_history: list[float] (for stability analysis)
        - roic_history: list[float] (for competitive advantage persistence)
        - business_description: str (for moat keyword detection)
        - r_and_d_pct: float | None (R&D as % of revenue)
        - contract_length_avg: float | None (years)
    """
    # Switching cost score (0-100)
    switching = 0.0
    contract_len = data.get("contract_length_avg")
    if contract_len and contract_len > 3:
        switching += 30.0
    elif contract_len and contract_len > 1:
        switching += 15.0

    rd_pct = data.get("r_and_d_pct")
    if rd_pct and rd_pct > 0.10:
        switching += 25.0  # High R&D = product complexity = switching costs
    elif rd_pct and rd_pct > 0.05:
        switching += 15.0

    # Gross margin stability as proxy for pricing power
    gm_history = data.get("gross_margin_history", [])
    if len(gm_history) >= 3:
        gm_vol = statistics.stdev(gm_history) if len(gm_history) > 1 else 0
        if gm_vol < 0.02:
            switching += 25.0  # Very stable margins = strong positioning
        elif gm_vol < 0.05:
            switching += 15.0

    # ROIC persistence bonus
    roic_hist = data.get("roic_history", [])
    if roic_hist and all(r > 0.10 for r in roic_hist[-3:]):
        switching += 20.0

    switching = min(switching, 100.0)

    # Moat type detection from business description
    desc = (data.get("business_description") or "").lower()
    detected_moat = None
    max_hits = 0
    for moat_type, keywords in MOAT_KEYWORDS.items():
        hits = sum(1 for kw in keywords if kw in desc)
        if hits > max_hits:
            max_hits = hits
            detected_moat = moat_type

    if max_hits < 1:  # Single strong keyword is sufficient for detection
        detected_moat = None

    # Disruption vulnerability (0-100, higher = more vulnerable)
    disruption = 50.0  # Neutral default
    if rd_pct and rd_pct < 0.02:
        disruption += 20.0  # Low R&D = not investing in defense
    if gm_history and statistics.mean(gm_history) < 0.25:
        disruption += 15.0  # Low margins = vulnerable to cost disruption
    if switching > 60:
        disruption -= 20.0  # High switching costs protect

    disruption = max(0.0, min(100.0, disruption))

    return BusinessModelDurability(
        switching_cost_score=round(switching, 2),
        moat_type=detected_moat,
        disruption_vulnerability=round(disruption, 2),
    )


# ── Orchestrator ──────────────────────────────────────────────────────────


def analyze_business_model(
    financials: dict,
    history: list[dict] | None = None,
) -> BusinessModelResult:
    """Complete business model analysis.

    Parameters
    ----------
    financials : dict
        Current period financial data.
    history : list[dict] | None
        Multi-period financial history (oldest→newest).
    """
    return BusinessModelResult(
        revenue_quality=assess_revenue_quality(financials),
        unit_economics=compute_unit_economics(financials),
        scaling=compute_scaling_behavior(history or []),
        durability=assess_business_model_durability(financials),
    )
