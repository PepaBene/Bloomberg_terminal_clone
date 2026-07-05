"""Pillar 3 Phase 3A — Industry Economics Engine.

Pure computation engine for industry-level economic analysis:
revenue growth, margin profiles, ROIC spreads, capital cycle
indicators, and company positioning within an industry.

No database access — all functions accept and return plain data.
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass


# ── Constants ────────────────────────────────────────────────────────────

CAPITAL_CYCLE_THRESHOLDS = {
    "EXPANDING": 0.05,   # capex growth > 5%
    "CONTRACTING": -0.02,  # capex growth < -2%
    # Anything in between is STABLE
}


# ── Dataclasses ──────────────────────────────────────────────────────────


@dataclass
class IndustryEconomics:
    """Industry-level economic profile."""

    revenue_growth_3y_cagr: float | None = None
    revenue_growth_5y_cagr: float | None = None
    revenue_dispersion: float | None = None
    median_gross_margin: float | None = None
    median_operating_margin: float | None = None
    median_capex_to_revenue: float | None = None
    median_rd_to_revenue: float | None = None
    median_roic: float | None = None
    median_wacc: float | None = None
    roic_wacc_spread: float | None = None
    roic_dispersion: float | None = None
    capital_cycle_indicator: str = "STABLE"
    top_quartile_roic: float | None = None
    bottom_quartile_roic: float | None = None


@dataclass
class CompanyIndustryPosition:
    """A company's position relative to its industry."""

    entity_id: str = ""
    revenue_growth_vs_industry: float | None = None
    margin_vs_industry: float | None = None
    roic_vs_industry: float | None = None
    roic_percentile: float | None = None
    margin_percentile: float | None = None


# ── Helper Functions ─────────────────────────────────────────────────────


def compute_cagr(start_value: float, end_value: float, years: float) -> float:
    """Compute compound annual growth rate.

    Returns (end/start)^(1/years) - 1.
    Handles zero/negative start values by returning 0.0.
    """
    if years <= 0 or start_value <= 0 or end_value <= 0:
        return 0.0
    return (end_value / start_value) ** (1.0 / years) - 1.0


def compute_dispersion(values: list[float]) -> float:
    """Compute standard deviation of a list of values.

    Returns 0.0 for fewer than 2 values.
    """
    if len(values) < 2:
        return 0.0
    return statistics.stdev(values)


def compute_median(values: list[float]) -> float:
    """Compute median of a list of values.

    Returns 0.0 for empty list.
    """
    if not values:
        return 0.0
    return statistics.median(values)


def compute_percentile(value: float, values: list[float]) -> float:
    """Compute the percentile rank of *value* within *values*.

    Returns the percentage (0-100) of values that are strictly below *value*.
    Returns 0.0 for an empty list.
    """
    if not values:
        return 0.0
    below = sum(1 for v in values if v < value)
    return (below / len(values)) * 100.0


def classify_capital_cycle(
    capex_growth_history: list[float],
    roic_trend: float | None,
) -> str:
    """Classify industry capital cycle position.

    Parameters
    ----------
    capex_growth_history : list[float]
        Year-over-year capex growth rates (e.g. [0.08, 0.10, 0.06]).
    roic_trend : float | None
        Recent change in ROIC (positive = rising, negative = falling).
        None if trend data is unavailable.

    Returns
    -------
    str
        EXPANDING, CONTRACTING, or STABLE.
    """
    if not capex_growth_history:
        return "STABLE"

    avg_capex_growth = statistics.mean(capex_growth_history)

    if (
        avg_capex_growth > CAPITAL_CYCLE_THRESHOLDS["EXPANDING"]
        and roic_trend is not None
        and roic_trend > 0
    ):
        return "EXPANDING"

    if avg_capex_growth < CAPITAL_CYCLE_THRESHOLDS["CONTRACTING"]:
        return "CONTRACTING"

    return "STABLE"


# ── Core Computation ─────────────────────────────────────────────────────


def compute_industry_economics(
    company_data: list[dict],
) -> IndustryEconomics:
    """Compute industry-level economics from a list of company data dicts.

    Each dict should have:
        - revenue_history: list[float]  (oldest -> newest, at least 2 values)
        - gross_margin: float
        - operating_margin: float
        - capex_to_revenue: float
        - rd_to_revenue: float | None
        - roic: float
        - wacc: float | None
        - capex_growth_history: list[float] (optional)
    """
    if not company_data:
        return IndustryEconomics()

    # Collect per-company metrics
    gross_margins: list[float] = []
    operating_margins: list[float] = []
    capex_ratios: list[float] = []
    rd_ratios: list[float] = []
    roics: list[float] = []
    waccs: list[float] = []
    revenue_growths_3y: list[float] = []
    revenue_growths_5y: list[float] = []
    all_capex_growth: list[float] = []

    for c in company_data:
        if c.get("gross_margin") is not None:
            gross_margins.append(c["gross_margin"])
        if c.get("operating_margin") is not None:
            operating_margins.append(c["operating_margin"])
        if c.get("capex_to_revenue") is not None:
            capex_ratios.append(c["capex_to_revenue"])
        if c.get("rd_to_revenue") is not None:
            rd_ratios.append(c["rd_to_revenue"])
        if c.get("roic") is not None:
            roics.append(c["roic"])
        if c.get("wacc") is not None:
            waccs.append(c["wacc"])

        rev = c.get("revenue_history", [])
        if len(rev) >= 4:
            cagr_3y = compute_cagr(rev[-4], rev[-1], 3.0)
            revenue_growths_3y.append(cagr_3y)
        if len(rev) >= 6:
            cagr_5y = compute_cagr(rev[-6], rev[-1], 5.0)
            revenue_growths_5y.append(cagr_5y)

        cgh = c.get("capex_growth_history", [])
        all_capex_growth.extend(cgh)

    # CAGR medians
    rev_3y = compute_median(revenue_growths_3y) if revenue_growths_3y else None
    rev_5y = compute_median(revenue_growths_5y) if revenue_growths_5y else None

    # Revenue dispersion (based on 3y CAGR across companies)
    rev_disp = compute_dispersion(revenue_growths_3y) if len(revenue_growths_3y) >= 2 else None

    # Medians
    med_gm = compute_median(gross_margins) if gross_margins else None
    med_om = compute_median(operating_margins) if operating_margins else None
    med_capex = compute_median(capex_ratios) if capex_ratios else None
    med_rd = compute_median(rd_ratios) if rd_ratios else None
    med_roic = compute_median(roics) if roics else None
    med_wacc = compute_median(waccs) if waccs else None

    # ROIC-WACC spread
    spread = None
    if med_roic is not None and med_wacc is not None:
        spread = med_roic - med_wacc

    # ROIC dispersion
    roic_disp = compute_dispersion(roics) if len(roics) >= 2 else None

    # ROIC quartiles
    top_q = None
    bottom_q = None
    if roics:
        sorted_roics = sorted(roics)
        n = len(sorted_roics)
        q1_idx = max(0, int(n * 0.25))
        q3_idx = min(n - 1, int(n * 0.75))
        bottom_q = sorted_roics[q1_idx]
        top_q = sorted_roics[q3_idx]

    # Capital cycle indicator
    # Cannot determine trend from a single point-in-time spread;
    # a level (spread) is not a trend (delta). Without historical spread
    # data to compute a delta, we pass None to indicate unknown trend.
    roic_trend = None

    cycle = classify_capital_cycle(all_capex_growth, roic_trend)

    return IndustryEconomics(
        revenue_growth_3y_cagr=rev_3y,
        revenue_growth_5y_cagr=rev_5y,
        revenue_dispersion=rev_disp,
        median_gross_margin=med_gm,
        median_operating_margin=med_om,
        median_capex_to_revenue=med_capex,
        median_rd_to_revenue=med_rd,
        median_roic=med_roic,
        median_wacc=med_wacc,
        roic_wacc_spread=spread,
        roic_dispersion=roic_disp,
        capital_cycle_indicator=cycle,
        top_quartile_roic=top_q,
        bottom_quartile_roic=bottom_q,
    )


# ── Company Ranking ──────────────────────────────────────────────────────


def rank_companies_in_industry(
    company_data: list[dict],
    industry_stats: IndustryEconomics,
) -> list[CompanyIndustryPosition]:
    """Position each company versus industry medians and compute percentiles.

    Each company dict should have:
        - entity_id: str
        - revenue_history: list[float]
        - operating_margin: float
        - roic: float
    """
    if not company_data:
        return []

    # Collect all ROIC and margin values for percentile computation
    all_roics = [c["roic"] for c in company_data if c.get("roic") is not None]
    all_margins = [
        c["operating_margin"]
        for c in company_data
        if c.get("operating_margin") is not None
    ]

    results: list[CompanyIndustryPosition] = []
    for c in company_data:
        entity_id = c.get("entity_id", "")

        # Revenue growth vs industry
        rev_vs = None
        rev = c.get("revenue_history", [])
        if len(rev) >= 4 and industry_stats.revenue_growth_3y_cagr is not None:
            co_cagr = compute_cagr(rev[-4], rev[-1], 3.0)
            rev_vs = co_cagr - industry_stats.revenue_growth_3y_cagr

        # Margin vs industry
        margin_vs = None
        co_margin = c.get("operating_margin")
        if co_margin is not None and industry_stats.median_operating_margin is not None:
            margin_vs = co_margin - industry_stats.median_operating_margin

        # ROIC vs industry
        roic_vs = None
        co_roic = c.get("roic")
        if co_roic is not None and industry_stats.median_roic is not None:
            roic_vs = co_roic - industry_stats.median_roic

        # Percentiles
        roic_pct = None
        if co_roic is not None and all_roics:
            roic_pct = compute_percentile(co_roic, all_roics)

        margin_pct = None
        if co_margin is not None and all_margins:
            margin_pct = compute_percentile(co_margin, all_margins)

        results.append(CompanyIndustryPosition(
            entity_id=entity_id,
            revenue_growth_vs_industry=rev_vs,
            margin_vs_industry=margin_vs,
            roic_vs_industry=roic_vs,
            roic_percentile=roic_pct,
            margin_percentile=margin_pct,
        ))

    return results


# ── Industry Comparison ──────────────────────────────────────────────────


def compare_industries(
    a: IndustryEconomics,
    b: IndustryEconomics,
) -> dict:
    """Compare two industry profiles, returning deltas for all comparable metrics.

    Returns dict with key = metric name, value = (a_value - b_value) or None
    if either side is missing.
    """
    fields = [
        "revenue_growth_3y_cagr",
        "revenue_growth_5y_cagr",
        "revenue_dispersion",
        "median_gross_margin",
        "median_operating_margin",
        "median_capex_to_revenue",
        "median_rd_to_revenue",
        "median_roic",
        "median_wacc",
        "roic_wacc_spread",
        "roic_dispersion",
        "top_quartile_roic",
        "bottom_quartile_roic",
    ]

    deltas: dict = {}
    for f in fields:
        va = getattr(a, f)
        vb = getattr(b, f)
        if va is not None and vb is not None:
            deltas[f] = va - vb
        else:
            deltas[f] = None

    # Capital cycle comparison (non-numeric)
    deltas["capital_cycle_indicator"] = {
        "a": a.capital_cycle_indicator,
        "b": b.capital_cycle_indicator,
    }

    return deltas
