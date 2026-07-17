"""Pillar 3 Phase 2 — margin trend and cost-structure analysis.

Pure computation engine backing the previously-unimplemented
``GET /v3/company/{entity_id}/margin-analysis`` and
``GET /v3/company/{entity_id}/cost-structure`` endpoints. Both are direct
transformations of the same multi-period fundamentals history the sibling
deep-intelligence engines (business_model_engine.py etc.) already consume —
no new data source, just two views over real per-period income-statement
figures that previously had no dedicated endpoint.

No database access — all functions accept and return plain data.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field

# Minimum periods of history required before a "5-year average" is reported
# rather than left None — using fewer periods to average would silently
# relabel a 2-year average as a "5Y avg", which is misleading.
_FIVE_YEAR_MIN_PERIODS = 4


@dataclass
class MarginMetric:
    """One margin line's current/prior/multi-period-average trend."""

    metric: str  # "gross_margin" / "operating_margin" / "net_margin"
    current_pct: float | None = None
    prior_pct: float | None = None
    five_year_avg_pct: float | None = None
    trend: str = "UNKNOWN"  # EXPANDING / CONTRACTING / STABLE / UNKNOWN


@dataclass
class MarginAnalysisResult:
    """Gross/operating/net margin trend analysis."""

    margins: list[MarginMetric] = field(default_factory=list)
    periods_analyzed: int = 0


@dataclass
class CostLineItem:
    """One cost category's share of revenue and trend."""

    category: str  # "COGS" / "SG&A" / "R&D"
    pct_of_revenue: float | None = None
    prior_pct_of_revenue: float | None = None
    trend: str = "UNKNOWN"  # RISING / FALLING / STABLE / UNKNOWN


@dataclass
class CostStructureResult:
    """Cost-structure (COGS/SG&A/R&D as % of revenue) analysis."""

    items: list[CostLineItem] = field(default_factory=list)
    periods_analyzed: int = 0


def _pct_trend(current: float | None, prior: float | None, *, higher_is_expanding: bool) -> str:
    """Classify a metric's direction from current vs. prior period.

    ``higher_is_expanding`` controls the label polarity: for margins, a
    rising value is "EXPANDING"; for cost-as-%-of-revenue lines, a rising
    value is "RISING" (this function returns the neutral EXPANDING/
    CONTRACTING/STABLE label; callers needing RISING/FALLING wording map it
    themselves so this helper stays reusable for both).
    """
    if current is None or prior is None:
        return "UNKNOWN"
    delta = current - prior
    if abs(delta) < 0.5:  # < 0.5 percentage-point move is noise, not a trend
        return "STABLE"
    rising = delta > 0
    if rising == higher_is_expanding:
        return "EXPANDING"
    return "CONTRACTING"


def analyze_margin_trends(history: list[dict]) -> MarginAnalysisResult:
    """Compute gross/operating/net margin current/prior/5yr-avg/trend.

    Parameters
    ----------
    history : list[dict]
        Oldest -> newest. Each period dict may contain ``revenue``,
        ``cogs``, ``operating_income``, ``net_income`` (any may be missing
        or None; periods missing the fields needed for a given margin are
        skipped for that margin's series, never treated as 0).
    """
    if not history:
        return MarginAnalysisResult(margins=[], periods_analyzed=0)

    def _margin_series(numerator_key: str, revenue_key: str = "revenue") -> list[float]:
        series = []
        for p in history:
            rev = p.get(revenue_key)
            num = p.get(numerator_key)
            if rev is None or rev == 0 or num is None:
                continue
            series.append(num / rev * 100.0)
        return series

    def _gross_margin_series() -> list[float]:
        # gross_profit isn't always carried in `history`; derive from
        # revenue - cogs when cogs is present, else fall back to a
        # pre-computed `gross_margin` field if the caller already supplied one.
        series = []
        for p in history:
            if p.get("gross_margin") is not None:
                series.append(float(p["gross_margin"]))
                continue
            rev = p.get("revenue")
            cogs = p.get("cogs")
            if rev and cogs is not None:
                series.append((rev - cogs) / rev * 100.0)
        return series

    def _build_metric(name: str, series: list[float]) -> MarginMetric:
        if not series:
            return MarginMetric(metric=name)
        current = series[-1]
        prior = series[-2] if len(series) >= 2 else None
        five_yr = (
            round(statistics.mean(series[-5:]), 2)
            if len(series) >= _FIVE_YEAR_MIN_PERIODS
            else None
        )
        trend = _pct_trend(current, prior, higher_is_expanding=True)
        return MarginMetric(
            metric=name,
            current_pct=round(current, 2),
            prior_pct=round(prior, 2) if prior is not None else None,
            five_year_avg_pct=five_yr,
            trend=trend,
        )

    margins = [
        _build_metric("gross_margin", _gross_margin_series()),
        _build_metric("operating_margin", _margin_series("operating_income")),
        _build_metric("net_margin", _margin_series("net_income")),
    ]
    return MarginAnalysisResult(margins=margins, periods_analyzed=len(history))


def analyze_cost_structure(history: list[dict]) -> CostStructureResult:
    """Compute COGS/SG&A/R&D as % of revenue, current vs. prior, trend.

    Parameters
    ----------
    history : list[dict]
        Oldest -> newest. Each period dict may contain ``revenue``,
        ``cogs``, ``sga``, ``rd`` (research & development; any may be
        missing or None).
    """
    if not history:
        return CostStructureResult(items=[], periods_analyzed=0)

    def _pct_series(key: str) -> list[float]:
        series = []
        for p in history:
            rev = p.get("revenue")
            val = p.get(key)
            if rev is None or rev == 0 or val is None:
                continue
            series.append(val / rev * 100.0)
        return series

    def _build_item(category: str, key: str) -> CostLineItem:
        series = _pct_series(key)
        if not series:
            return CostLineItem(category=category)
        current = series[-1]
        prior = series[-2] if len(series) >= 2 else None
        # For cost lines, a RISING share of revenue is the "expanding"
        # direction in the neutral helper's polarity terms, so
        # higher_is_expanding=True there maps to RISING here.
        neutral_trend = _pct_trend(current, prior, higher_is_expanding=True)
        trend_map = {"EXPANDING": "RISING", "CONTRACTING": "FALLING", "STABLE": "STABLE", "UNKNOWN": "UNKNOWN"}
        return CostLineItem(
            category=category,
            pct_of_revenue=round(current, 2),
            prior_pct_of_revenue=round(prior, 2) if prior is not None else None,
            trend=trend_map[neutral_trend],
        )

    items = [
        _build_item("COGS", "cogs"),
        _build_item("SG&A", "sga"),
        _build_item("R&D", "rd"),
    ]
    return CostStructureResult(items=items, periods_analyzed=len(history))
