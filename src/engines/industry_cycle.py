"""Pillar 3 Phase 3A — Industry Cycle Engine.

Pure computation engine for industry cycle positioning and competitive
structure analysis: cycle classification, HHI, pricing power, barriers
to entry, and consolidation trends.

No database access — all functions accept and return plain data.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field


# ── Constants ────────────────────────────────────────────────────────────

HHI_THRESHOLDS = {
    "UNCONCENTRATED": 1500,
    "MODERATE": 2500,
}

CYCLE_INDICATORS = {
    "revenue_acceleration": 0.30,
    "margin_direction": 0.30,
    "capacity_utilization": 0.20,
    "inventory_dynamics": 0.20,
}


# ── Dataclasses ──────────────────────────────────────────────────────────


@dataclass
class CycleAssessment:
    """Industry cycle position assessment."""

    cycle_position: str = "MID_CYCLE"  # EARLY_CYCLE/MID_CYCLE/LATE_CYCLE/DOWNTURN
    confidence: float = 0.0  # 0-100
    revenue_growth_acceleration: float | None = None
    capacity_utilization_proxy: float | None = None
    inventory_dynamics: str = "STABLE"  # BUILDING/STABLE/DEPLETING
    margin_cycle_direction: str = "STABLE"  # EXPANDING/PEAK/CONTRACTING/TROUGH
    signals: dict = field(default_factory=dict)


@dataclass
class CompetitiveStructure:
    """Industry competitive structure profile."""

    hhi_index: float = 0.0
    hhi_classification: str = "UNCONCENTRATED"
    top3_market_share: float | None = None
    top5_market_share: float | None = None
    top10_market_share: float | None = None
    consolidation_trend: str = "STABLE"  # CONSOLIDATING/STABLE/FRAGMENTING
    barrier_to_entry: str = "LOW"  # HIGH/MEDIUM/LOW
    pricing_power: str = "WEAK"  # STRONG/MODERATE/WEAK
    competitive_dynamics: str = ""


# ── Cycle Signal Functions ───────────────────────────────────────────────


def compute_revenue_acceleration(revenue_history: list[float]) -> float:
    """Compute revenue growth acceleration (2nd derivative).

    Needs at least 3 periods. Returns the difference between recent
    growth rate and prior growth rate.
    """
    if len(revenue_history) < 3:
        return 0.0

    # Compute period-over-period growth rates
    growth_rates: list[float] = []
    for i in range(1, len(revenue_history)):
        prev = revenue_history[i - 1]
        if prev != 0:
            growth_rates.append((revenue_history[i] - prev) / abs(prev))
        else:
            growth_rates.append(0.0)

    if len(growth_rates) < 2:
        return 0.0

    # 2nd derivative: recent growth - prior growth
    recent = statistics.mean(growth_rates[len(growth_rates) // 2 :])
    prior = statistics.mean(growth_rates[: len(growth_rates) // 2])
    return recent - prior


def compute_capacity_utilization_proxy(
    capex_history: list[float],
    depreciation_history: list[float],
) -> float:
    """Compute capacity utilization proxy as capex/depreciation ratio.

    > 1.2 = expanding capacity, < 0.8 = contracting capacity.
    Returns 1.0 if insufficient data.
    """
    if not capex_history or not depreciation_history:
        return 1.0

    # Use most recent values
    capex = abs(capex_history[-1]) if capex_history[-1] != 0 else 0.0
    depr = abs(depreciation_history[-1]) if depreciation_history[-1] != 0 else 0.0

    if depr == 0:
        return 1.0

    return capex / depr


def classify_inventory_dynamics(inventory_to_sales: list[float]) -> str:
    """Classify inventory dynamics from inventory-to-sales ratio history.

    Rising = BUILDING, falling = DEPLETING, flat = STABLE.
    """
    if len(inventory_to_sales) < 2:
        return "STABLE"

    first_half = statistics.mean(inventory_to_sales[: len(inventory_to_sales) // 2])
    second_half = statistics.mean(inventory_to_sales[len(inventory_to_sales) // 2 :])

    if first_half == 0:
        return "STABLE"

    change = (second_half - first_half) / abs(first_half)

    if change > 0.05:
        return "BUILDING"
    elif change < -0.05:
        return "DEPLETING"
    return "STABLE"


def classify_margin_cycle(margin_history: list[float]) -> str:
    """Classify margin cycle direction.

    Rising and high = PEAK, rising = EXPANDING,
    falling and low = TROUGH, falling = CONTRACTING.
    """
    if len(margin_history) < 2:
        return "STABLE"

    n = len(margin_history)
    first_half = statistics.mean(margin_history[: n // 2])
    second_half = statistics.mean(margin_history[n // 2 :])

    is_rising = second_half > first_half + 0.005
    is_falling = second_half < first_half - 0.005

    # Determine level relative to the full history
    overall_mean = statistics.mean(margin_history)
    current = margin_history[-1]
    is_high = current > overall_mean + 0.01
    is_low = current < overall_mean - 0.01

    if is_rising and is_high:
        return "PEAK"
    elif is_rising:
        return "EXPANDING"
    elif is_falling and is_low:
        return "TROUGH"
    elif is_falling:
        return "CONTRACTING"
    return "STABLE"


# ── Cycle Position Classifier ────────────────────────────────────────────


def compute_cycle_position(
    revenue_history: list[float] | None = None,
    margin_history: list[float] | None = None,
    capex_history: list[float] | None = None,
    depreciation_history: list[float] | None = None,
    inventory_to_sales_history: list[float] | None = None,
) -> CycleAssessment:
    """Multi-signal cycle position classifier.

    EARLY_CYCLE  = acceleration + expanding margins + depleting inventory
    MID_CYCLE    = moderate growth + stable
    LATE_CYCLE   = deceleration + peak margins + building inventory
    DOWNTURN     = negative growth + contracting margins
    """
    rev_accel = compute_revenue_acceleration(revenue_history or [])
    cap_util = compute_capacity_utilization_proxy(
        capex_history or [], depreciation_history or [],
    )
    inv_dyn = classify_inventory_dynamics(inventory_to_sales_history or [])
    margin_dir = classify_margin_cycle(margin_history or [])

    signals = {
        "revenue_acceleration": rev_accel,
        "capacity_utilization_proxy": cap_util,
        "inventory_dynamics": inv_dyn,
        "margin_cycle_direction": margin_dir,
    }

    # Score each cycle position
    scores = {
        "EARLY_CYCLE": 0.0,
        "MID_CYCLE": 0.0,
        "LATE_CYCLE": 0.0,
        "DOWNTURN": 0.0,
    }

    # Revenue acceleration signal
    w_rev = CYCLE_INDICATORS["revenue_acceleration"]
    if rev_accel > 0.02:
        scores["EARLY_CYCLE"] += w_rev
    elif rev_accel > -0.01:
        scores["MID_CYCLE"] += w_rev
    elif rev_accel > -0.05:
        scores["LATE_CYCLE"] += w_rev
    else:
        scores["DOWNTURN"] += w_rev

    # Margin direction signal
    w_mar = CYCLE_INDICATORS["margin_direction"]
    if margin_dir == "EXPANDING":
        scores["EARLY_CYCLE"] += w_mar
    elif margin_dir == "PEAK":
        scores["LATE_CYCLE"] += w_mar
    elif margin_dir == "CONTRACTING":
        scores["DOWNTURN"] += w_mar
    elif margin_dir == "TROUGH":
        scores["EARLY_CYCLE"] += w_mar * 0.5
        scores["DOWNTURN"] += w_mar * 0.5
    else:
        scores["MID_CYCLE"] += w_mar

    # Capacity utilization signal
    w_cap = CYCLE_INDICATORS["capacity_utilization"]
    if cap_util > 1.2:
        scores["EARLY_CYCLE"] += w_cap * 0.5
        scores["MID_CYCLE"] += w_cap * 0.5
    elif cap_util < 0.8:
        scores["DOWNTURN"] += w_cap
    else:
        scores["MID_CYCLE"] += w_cap * 0.5
        scores["LATE_CYCLE"] += w_cap * 0.5

    # Inventory dynamics signal
    w_inv = CYCLE_INDICATORS["inventory_dynamics"]
    if inv_dyn == "DEPLETING":
        scores["EARLY_CYCLE"] += w_inv
    elif inv_dyn == "BUILDING":
        scores["LATE_CYCLE"] += w_inv
    else:
        scores["MID_CYCLE"] += w_inv

    # Pick the winner
    best_position = max(scores, key=scores.get)  # type: ignore[arg-type]
    best_score = scores[best_position]
    total = sum(scores.values())
    confidence = (best_score / total * 100.0) if total > 0 else 0.0

    return CycleAssessment(
        cycle_position=best_position,
        confidence=round(confidence, 1),
        revenue_growth_acceleration=round(rev_accel, 6),
        capacity_utilization_proxy=round(cap_util, 4),
        inventory_dynamics=inv_dyn,
        margin_cycle_direction=margin_dir,
        signals=signals,
    )


# ── Competitive Structure Functions ──────────────────────────────────────


def compute_hhi(market_shares: list[float]) -> float:
    """Compute Herfindahl-Hirschman Index.

    market_shares are percentage points (e.g. [30.0, 25.0, 15.0, ...]).
    Normalizes so they sum to 100% before squaring.
    Returns sum of squared shares * 10000 / (sum^2).
    """
    if not market_shares:
        return 0.0

    total = sum(market_shares)
    if total <= 0:
        return 0.0

    # Normalize to sum to 100
    normalized = [(s / total) * 100.0 for s in market_shares]
    return sum(s * s for s in normalized)


def classify_hhi(hhi: float) -> str:
    """Classify HHI into concentration categories.

    < 1500 = UNCONCENTRATED, 1500-2500 = MODERATE, > 2500 = CONCENTRATED.
    """
    if hhi < HHI_THRESHOLDS["UNCONCENTRATED"]:
        return "UNCONCENTRATED"
    elif hhi < HHI_THRESHOLDS["MODERATE"]:
        return "MODERATE"
    return "CONCENTRATED"


def assess_pricing_power(
    gross_margin_history: list[float],
    threshold_std: float = 0.02,
) -> str:
    """Assess pricing power from gross margin stability.

    Std dev < threshold = STRONG, < 2*threshold = MODERATE, else WEAK.
    """
    if len(gross_margin_history) < 2:
        return "MODERATE"

    std = statistics.stdev(gross_margin_history)
    if std < threshold_std:
        return "STRONG"
    elif std < 2 * threshold_std:
        return "MODERATE"
    return "WEAK"


def assess_barriers_to_entry(
    capex_intensity: float,
    rd_intensity: float,
    regulatory_score: float,
) -> str:
    """Assess barriers to entry from capital, R&D, and regulatory intensity.

    Parameters
    ----------
    capex_intensity : float
        CapEx as fraction of revenue (0-1).
    rd_intensity : float
        R&D as fraction of revenue (0-1).
    regulatory_score : float
        Regulatory barrier score (0-1).

    Weighted sum > 0.5 = HIGH, > 0.25 = MEDIUM, else LOW.
    """
    weighted = (
        capex_intensity * 0.35
        + rd_intensity * 0.35
        + regulatory_score * 0.30
    )

    if weighted > 0.5:
        return "HIGH"
    elif weighted > 0.25:
        return "MEDIUM"
    return "LOW"


# ── Competitive Structure Orchestrator ───────────────────────────────────


def compute_competitive_structure(
    company_revenues: list[dict],
    gross_margin_history: list[float] | None = None,
    capex_intensity: float = 0.0,
    rd_intensity: float = 0.0,
    regulatory_score: float = 0.0,
) -> CompetitiveStructure:
    """Compute full competitive structure analysis.

    Parameters
    ----------
    company_revenues : list[dict]
        Each dict has: {entity_id: str, revenue: float}.
        Used to compute market shares and HHI.
    gross_margin_history : list[float] | None
        Industry-level gross margin history for pricing power.
    capex_intensity : float
        Industry average capex/revenue.
    rd_intensity : float
        Industry average R&D/revenue.
    regulatory_score : float
        Regulatory barrier score (0-1).
    """
    if not company_revenues:
        return CompetitiveStructure()

    # Compute market shares from revenue
    revenues = [c.get("revenue", 0.0) for c in company_revenues]
    total_rev = sum(revenues)
    if total_rev <= 0:
        return CompetitiveStructure()

    shares = [(r / total_rev) * 100.0 for r in revenues]
    shares_sorted = sorted(shares, reverse=True)

    hhi = compute_hhi(shares)
    hhi_class = classify_hhi(hhi)

    # Top N market share
    top3 = sum(shares_sorted[:3]) if len(shares_sorted) >= 3 else sum(shares_sorted)
    top5 = sum(shares_sorted[:5]) if len(shares_sorted) >= 5 else sum(shares_sorted)
    top10 = sum(shares_sorted[:10]) if len(shares_sorted) >= 10 else sum(shares_sorted)

    # Consolidation trend: compare top3 share to what equal distribution would be
    equal_share = 100.0 / len(shares) * 3.0 if len(shares) >= 3 else 100.0
    if top3 > equal_share + 15:
        consolidation = "CONSOLIDATING"
    elif top3 < equal_share - 5:
        consolidation = "FRAGMENTING"
    else:
        consolidation = "STABLE"

    # Pricing power
    pricing = assess_pricing_power(gross_margin_history or [])

    # Barriers
    barriers = assess_barriers_to_entry(capex_intensity, rd_intensity, regulatory_score)

    # Competitive dynamics description
    dynamics = (
        f"{hhi_class.lower().replace('_', ' ')} market with "
        f"{barriers.lower()} barriers to entry and "
        f"{pricing.lower()} pricing power"
    )

    return CompetitiveStructure(
        hhi_index=round(hhi, 2),
        hhi_classification=hhi_class,
        top3_market_share=round(top3, 2),
        top5_market_share=round(top5, 2),
        top10_market_share=round(top10, 2),
        consolidation_trend=consolidation,
        barrier_to_entry=barriers,
        pricing_power=pricing,
        competitive_dynamics=dynamics,
    )
