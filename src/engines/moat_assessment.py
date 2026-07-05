"""Pillar 3 Phase 3A — Moat Assessment Engine.

Pure computation engine for competitive moat assessment.
Evaluates ROIC consistency, margin stability, market share trends,
and five moat sources (cost advantage, network effects, switching costs,
intangible assets, efficient scale).

No database access — all functions accept and return plain data.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field


# ── Constants ────────────────────────────────────────────────────────────

MOAT_WIDTH_THRESHOLDS = {"WIDE": 10, "NARROW": 7}  # years ROIC > WACC needed

MARGIN_STABILITY_BANDS = {
    10: 100,
    20: 80,
    30: 60,
    40: 40,
    "else": 20,
}  # std_dev_bps -> score

MOAT_SOURCE_WEIGHTS = {
    "cost_advantage": 0.25,
    "network_effects": 0.20,
    "switching_costs": 0.25,
    "intangible_assets": 0.15,
    "efficient_scale": 0.15,
}


# ── Dataclasses ──────────────────────────────────────────────────────────


@dataclass
class MoatResult:
    """Complete moat assessment result."""

    moat_width: str  # WIDE/NARROW/NONE
    moat_stability: str  # STABLE/WIDENING/ERODING
    moat_score: float  # 0-100
    dominant_source: str  # highest scoring source
    cost_advantage_score: float
    network_effects_score: float
    switching_costs_score: float
    intangible_assets_score: float
    efficient_scale_score: float
    roic_above_wacc_years: int
    evidence: list[dict] = field(default_factory=list)  # [{source, detail, strength}]


# ── ROIC Consistency ─────────────────────────────────────────────────────


def assess_roic_consistency(
    roic_history: list[float],
    wacc_history: list[float],
) -> tuple[int, float]:
    """Count years ROIC > WACC and compute consistency score.

    Parameters
    ----------
    roic_history : list[float]
        Annual ROIC values (decimal, e.g. 0.15 = 15%).
    wacc_history : list[float]
        Annual WACC values (decimal), same length as roic_history.

    Returns
    -------
    tuple[int, float]
        (years_above, consistency_score 0-100).
        consistency_score = 100 * (years / total) * (1 - std_dev_of_spreads / mean_spread)
    """
    if not roic_history or not wacc_history:
        return 0, 0.0

    total = min(len(roic_history), len(wacc_history))
    spreads = [roic_history[i] - wacc_history[i] for i in range(total)]
    years_above = sum(1 for s in spreads if s > 0)

    if total == 0:
        return 0, 0.0

    mean_spread = statistics.mean(spreads)
    if mean_spread <= 0:
        return years_above, 0.0

    std_spread = statistics.stdev(spreads) if len(spreads) > 1 else 0.0
    ratio = years_above / total
    volatility_penalty = std_spread / mean_spread
    # Clamp the volatility penalty to avoid negative scores
    volatility_penalty = min(volatility_penalty, 1.0)

    score = 100.0 * ratio * (1.0 - volatility_penalty)
    return years_above, max(0.0, min(100.0, round(score, 2)))


# ── Margin Stability ─────────────────────────────────────────────────────


def assess_gross_margin_stability(margin_history: list[float]) -> float:
    """Score gross margin stability 0-100 based on std dev bands.

    Parameters
    ----------
    margin_history : list[float]
        Annual gross margin values (e.g. [0.45, 0.46, 0.44]).

    Returns
    -------
    float
        Score 0-100. Lower std dev = higher score.
    """
    if len(margin_history) < 2:
        return 50.0  # Unknown

    std_dev = statistics.stdev(margin_history)
    std_dev_bps = std_dev * 10000  # convert to basis points

    for threshold in sorted(k for k in MARGIN_STABILITY_BANDS if isinstance(k, int)):
        if std_dev_bps <= threshold:
            return float(MARGIN_STABILITY_BANDS[threshold])

    return float(MARGIN_STABILITY_BANDS["else"])


# ── Market Share Trend ───────────────────────────────────────────────────


def assess_market_share_trend(
    entity_revenue_growth: float,
    industry_revenue_growth: float,
) -> tuple[str, float]:
    """Assess market share trend from revenue growth comparison.

    Parameters
    ----------
    entity_revenue_growth : float
        Entity revenue growth rate (percentage points, e.g. 12.0 = 12%).
    industry_revenue_growth : float
        Industry revenue growth rate (percentage points).

    Returns
    -------
    tuple[str, float]
        (trend: GAINING/LOSING/STABLE, delta: entity - industry).
    """
    delta = entity_revenue_growth - industry_revenue_growth

    if delta > 2.0:
        return "GAINING", round(delta, 2)
    elif delta < -2.0:
        return "LOSING", round(delta, 2)
    else:
        return "STABLE", round(delta, 2)


# ── Moat Source Scoring ──────────────────────────────────────────────────


def score_cost_advantage(
    operating_margin: float,
    peer_median_margin: float,
    capex_intensity: float,
) -> float:
    """Score cost advantage 0-100.

    High margin above peers + efficient capex = high score.

    Parameters
    ----------
    operating_margin : float
        Entity operating margin (decimal, e.g. 0.30 = 30%).
    peer_median_margin : float
        Peer median operating margin (decimal).
    capex_intensity : float
        Capex / revenue ratio (decimal, e.g. 0.05 = 5%).
    """
    score = 0.0

    # Margin advantage (max 60 pts)
    margin_spread = operating_margin - peer_median_margin
    if margin_spread > 0.15:
        score += 60.0
    elif margin_spread > 0.10:
        score += 50.0
    elif margin_spread > 0.05:
        score += 35.0
    elif margin_spread > 0.02:
        score += 20.0
    elif margin_spread > 0:
        score += 10.0

    # Capex efficiency (max 40 pts) — lower capex intensity is better
    if capex_intensity < 0.03:
        score += 40.0
    elif capex_intensity < 0.05:
        score += 30.0
    elif capex_intensity < 0.08:
        score += 20.0
    elif capex_intensity < 0.12:
        score += 10.0

    return min(100.0, round(score, 2))


def score_network_effects(
    user_growth_rate: float | None,
    revenue_per_user_trend: float | None,
    platform_flag: bool,
) -> float:
    """Score network effects 0-100.

    If user growth drives revenue disproportionately.

    Parameters
    ----------
    user_growth_rate : float | None
        Year-over-year user growth (decimal, e.g. 0.20 = 20%).
    revenue_per_user_trend : float | None
        Year-over-year change in revenue per user (decimal).
    platform_flag : bool
        Whether entity operates a platform/marketplace.
    """
    score = 0.0

    if platform_flag:
        score += 30.0

    if user_growth_rate is not None:
        if user_growth_rate > 0.20:
            score += 35.0
        elif user_growth_rate > 0.10:
            score += 25.0
        elif user_growth_rate > 0.05:
            score += 15.0

    if revenue_per_user_trend is not None:
        if revenue_per_user_trend > 0.10:
            score += 35.0
        elif revenue_per_user_trend > 0.05:
            score += 25.0
        elif revenue_per_user_trend > 0:
            score += 15.0

    return min(100.0, round(score, 2))


def score_switching_costs(
    recurring_revenue_pct: float,
    avg_contract_years: float | None,
    customer_retention_rate: float | None,
) -> float:
    """Score switching costs 0-100.

    High recurring + long contracts + high retention = high score.

    Parameters
    ----------
    recurring_revenue_pct : float
        Recurring revenue as a fraction (e.g. 0.80 = 80%).
    avg_contract_years : float | None
        Average contract length in years.
    customer_retention_rate : float | None
        Customer retention rate (e.g. 0.95 = 95%).
    """
    score = 0.0

    # Recurring revenue (max 40 pts)
    if recurring_revenue_pct > 0.80:
        score += 40.0
    elif recurring_revenue_pct > 0.60:
        score += 30.0
    elif recurring_revenue_pct > 0.40:
        score += 20.0
    elif recurring_revenue_pct > 0.20:
        score += 10.0

    # Contract length (max 30 pts)
    if avg_contract_years is not None:
        if avg_contract_years > 5.0:
            score += 30.0
        elif avg_contract_years > 3.0:
            score += 25.0
        elif avg_contract_years > 1.0:
            score += 15.0
        elif avg_contract_years > 0.5:
            score += 5.0

    # Retention rate (max 30 pts)
    if customer_retention_rate is not None:
        if customer_retention_rate > 0.95:
            score += 30.0
        elif customer_retention_rate > 0.90:
            score += 25.0
        elif customer_retention_rate > 0.80:
            score += 15.0
        elif customer_retention_rate > 0.70:
            score += 5.0

    return min(100.0, round(score, 2))


def score_intangible_assets(
    rd_intensity: float,
    patent_count: int | None,
    brand_premium: float | None,
) -> float:
    """Score intangible assets 0-100.

    Parameters
    ----------
    rd_intensity : float
        R&D spend / revenue (decimal, e.g. 0.15 = 15%).
    patent_count : int | None
        Number of active patents.
    brand_premium : float | None
        Brand premium over generic alternatives (decimal, e.g. 0.30 = 30%).
    """
    score = 0.0

    # R&D intensity (max 40 pts)
    if rd_intensity > 0.15:
        score += 40.0
    elif rd_intensity > 0.10:
        score += 30.0
    elif rd_intensity > 0.05:
        score += 20.0
    elif rd_intensity > 0.02:
        score += 10.0

    # Patent portfolio (max 30 pts)
    if patent_count is not None:
        if patent_count > 5000:
            score += 30.0
        elif patent_count > 1000:
            score += 25.0
        elif patent_count > 100:
            score += 15.0
        elif patent_count > 10:
            score += 5.0

    # Brand premium (max 30 pts)
    if brand_premium is not None:
        if brand_premium > 0.30:
            score += 30.0
        elif brand_premium > 0.15:
            score += 25.0
        elif brand_premium > 0.05:
            score += 15.0

    return min(100.0, round(score, 2))


def score_efficient_scale(
    market_share: float,
    hhi: float,
    capacity_share: float | None,
) -> float:
    """Score efficient scale 0-100.

    High market share in concentrated market = high score.

    Parameters
    ----------
    market_share : float
        Entity market share (decimal, e.g. 0.35 = 35%).
    hhi : float
        Herfindahl-Hirschman Index of the industry (0-10000).
    capacity_share : float | None
        Entity share of industry capacity (decimal).
    """
    score = 0.0

    # Market share (max 40 pts)
    if market_share > 0.40:
        score += 40.0
    elif market_share > 0.25:
        score += 30.0
    elif market_share > 0.15:
        score += 20.0
    elif market_share > 0.05:
        score += 10.0

    # HHI — concentrated market (max 35 pts)
    if hhi > 2500:
        score += 35.0
    elif hhi > 1500:
        score += 25.0
    elif hhi > 1000:
        score += 15.0
    elif hhi > 500:
        score += 5.0

    # Capacity share (max 25 pts)
    if capacity_share is not None:
        if capacity_share > 0.40:
            score += 25.0
        elif capacity_share > 0.25:
            score += 20.0
        elif capacity_share > 0.10:
            score += 10.0

    return min(100.0, round(score, 2))


# ── Moat Stability ───────────────────────────────────────────────────────


def assess_moat_stability(
    current_spread: float,
    prior_spread: float,
    current_margin: float,
    prior_margin: float,
) -> str:
    """Determine if the moat is widening, eroding, or stable.

    Parameters
    ----------
    current_spread : float
        Current ROIC - WACC spread.
    prior_spread : float
        Prior period ROIC - WACC spread.
    current_margin : float
        Current gross/operating margin.
    prior_margin : float
        Prior period gross/operating margin.

    Returns
    -------
    str
        WIDENING, ERODING, or STABLE.
    """
    spread_change = current_spread - prior_spread
    margin_change = current_margin - prior_margin

    # If both spread and margin improving -> WIDENING
    if spread_change > 0.005 and margin_change > 0.005:
        return "WIDENING"
    # If both deteriorating -> ERODING
    elif spread_change < -0.005 and margin_change < -0.005:
        return "ERODING"
    # If spread improving but margin stable/declining or vice versa
    elif spread_change > 0.01:
        return "WIDENING"
    elif spread_change < -0.01:
        return "ERODING"
    else:
        return "STABLE"


# ── Full Orchestrator ────────────────────────────────────────────────────


def assess_moat(
    roic_history: list[float],
    wacc_history: list[float],
    margin_history: list[float],
    entity_revenue_growth: float,
    industry_revenue_growth: float,
    peer_median_margin: float,
    operating_margin: float,
    capex_intensity: float,
    recurring_pct: float,
    hhi: float,
    market_share: float,
    qualitative_inputs: dict | None = None,
) -> MoatResult:
    """Full moat assessment orchestrator.

    Parameters
    ----------
    roic_history : list[float]
        Annual ROIC values (decimal).
    wacc_history : list[float]
        Annual WACC values (decimal).
    margin_history : list[float]
        Annual gross margin values (decimal).
    entity_revenue_growth : float
        Entity revenue growth (percentage points).
    industry_revenue_growth : float
        Industry revenue growth (percentage points).
    peer_median_margin : float
        Peer median operating margin (decimal).
    operating_margin : float
        Entity operating margin (decimal).
    capex_intensity : float
        Capex / revenue (decimal).
    recurring_pct : float
        Recurring revenue fraction (decimal).
    hhi : float
        Industry HHI (0-10000).
    market_share : float
        Entity market share (decimal).
    qualitative_inputs : dict | None
        Optional qualitative data:
        - user_growth_rate: float | None
        - revenue_per_user_trend: float | None
        - platform_flag: bool
        - avg_contract_years: float | None
        - customer_retention_rate: float | None
        - rd_intensity: float
        - patent_count: int | None
        - brand_premium: float | None
        - capacity_share: float | None

    Returns
    -------
    MoatResult
    """
    qi = qualitative_inputs or {}

    # 1. ROIC consistency
    years_above, roic_score = assess_roic_consistency(roic_history, wacc_history)

    # 2. Margin stability
    margin_score = assess_gross_margin_stability(margin_history)

    # 3. Market share trend
    share_trend, share_delta = assess_market_share_trend(
        entity_revenue_growth, industry_revenue_growth,
    )

    # 4. Score individual moat sources
    ca_score = score_cost_advantage(operating_margin, peer_median_margin, capex_intensity)
    ne_score = score_network_effects(
        qi.get("user_growth_rate"),
        qi.get("revenue_per_user_trend"),
        qi.get("platform_flag", False),
    )
    sc_score = score_switching_costs(
        recurring_pct,
        qi.get("avg_contract_years"),
        qi.get("customer_retention_rate"),
    )
    ia_score = score_intangible_assets(
        qi.get("rd_intensity", 0.0),
        qi.get("patent_count"),
        qi.get("brand_premium"),
    )
    es_score = score_efficient_scale(
        market_share,
        hhi,
        qi.get("capacity_share"),
    )

    # 5. Weighted moat score
    source_scores = {
        "cost_advantage": ca_score,
        "network_effects": ne_score,
        "switching_costs": sc_score,
        "intangible_assets": ia_score,
        "efficient_scale": es_score,
    }
    weighted_source = sum(
        source_scores[k] * MOAT_SOURCE_WEIGHTS[k] for k in source_scores
    )

    # Combine: 40% ROIC consistency, 20% margin stability, 40% source scores
    moat_score = 0.40 * roic_score + 0.20 * margin_score + 0.40 * weighted_source
    moat_score = round(max(0.0, min(100.0, moat_score)), 2)

    # 6. Moat width classification
    if years_above >= MOAT_WIDTH_THRESHOLDS["WIDE"]:
        moat_width = "WIDE"
    elif years_above >= MOAT_WIDTH_THRESHOLDS["NARROW"]:
        moat_width = "NARROW"
    else:
        moat_width = "NONE"

    # 7. Moat stability
    if len(roic_history) >= 2 and len(wacc_history) >= 2 and len(margin_history) >= 2:
        current_spread = roic_history[-1] - wacc_history[-1]
        prior_spread = roic_history[-2] - wacc_history[-2]
        moat_stability = assess_moat_stability(
            current_spread, prior_spread,
            margin_history[-1], margin_history[-2],
        )
    else:
        moat_stability = "STABLE"

    # 8. Dominant source
    dominant_source = max(source_scores, key=source_scores.get)

    # 9. Evidence
    evidence: list[dict] = []
    if ca_score >= 40:  # Include borderline evidence
        evidence.append({
            "source": "cost_advantage",
            "detail": f"Operating margin {operating_margin:.1%} vs peer {peer_median_margin:.1%}",
            "strength": "STRONG" if ca_score > 70 else "MODERATE",
        })
    if ne_score >= 40:  # Include borderline evidence
        evidence.append({
            "source": "network_effects",
            "detail": "Platform with strong user growth dynamics",
            "strength": "STRONG" if ne_score > 70 else "MODERATE",
        })
    if sc_score >= 40:  # Include borderline evidence
        evidence.append({
            "source": "switching_costs",
            "detail": f"Recurring revenue {recurring_pct:.0%}",
            "strength": "STRONG" if sc_score > 70 else "MODERATE",
        })
    if ia_score >= 40:  # Include borderline evidence
        evidence.append({
            "source": "intangible_assets",
            "detail": f"R&D intensity {qi.get('rd_intensity', 0):.1%}",
            "strength": "STRONG" if ia_score > 70 else "MODERATE",
        })
    if es_score >= 40:  # Include borderline evidence
        evidence.append({
            "source": "efficient_scale",
            "detail": f"Market share {market_share:.1%} in concentrated market (HHI {hhi:.0f})",
            "strength": "STRONG" if es_score > 70 else "MODERATE",
        })
    if share_trend == "GAINING":
        evidence.append({
            "source": "market_share",
            "detail": f"Gaining share: entity growth +{share_delta:.1f}pp vs industry",
            "strength": "MODERATE",
        })

    return MoatResult(
        moat_width=moat_width,
        moat_stability=moat_stability,
        moat_score=moat_score,
        dominant_source=dominant_source,
        cost_advantage_score=ca_score,
        network_effects_score=ne_score,
        switching_costs_score=sc_score,
        intangible_assets_score=ia_score,
        efficient_scale_score=es_score,
        roic_above_wacc_years=years_above,
        evidence=evidence,
    )
