"""Revenue Drivers Engine — per-segment revenue-growth decomposition.

Pure computation engine for GET /v3/company/{entity_id}/revenue-drivers.
Decomposes company revenue growth into the contribution of individual
business segments (product/business lines), classifies each segment as a
growth driver / drag / stable, and computes a revenue concentration index.

No database access — all functions accept and return plain data.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# ── Dataclasses ───────────────────────────────────────────────────────────


@dataclass
class RevenueDriver:
    """Growth decomposition for a single business segment."""

    segment_name: str
    latest_revenue: float | None = None
    revenue_share_pct: float | None = None  # of total, latest period
    yoy_growth_pct: float | None = None
    cagr_pct: float | None = None  # None if < 3 periods of data
    contribution_to_growth_pct: float | None = None
    classification: str = "INSUFFICIENT_DATA"  # GROWTH_DRIVER/DRAG/STABLE/INSUFFICIENT_DATA


@dataclass
class RevenueDriversResult:
    """Complete revenue drivers analysis."""

    drivers: list[RevenueDriver] = field(default_factory=list)
    revenue_concentration_hhi: float | None = None
    total_revenue_yoy_growth_pct: float | None = None  # company-wide, for context
    periods_analyzed: int = 0


# ── Helpers ───────────────────────────────────────────────────────────────


def _business_segment_names(segment_history: list[dict]) -> list[str]:
    """Collect unique BUSINESS-type segment names, first-seen order."""
    seen: dict[str, None] = {}
    for period in segment_history:
        for seg in period.get("segments", []):
            if seg.get("type") != "BUSINESS":
                continue
            name = seg.get("name")
            if name is None:
                continue
            if name not in seen:
                seen[name] = None
    return list(seen.keys())


def _segment_revenue_series(segment_history: list[dict], name: str) -> list[float | None]:
    """Extract this segment's revenue for each period (None if absent/unpopulated)."""
    series: list[float | None] = []
    for period in segment_history:
        value = None
        for seg in period.get("segments", []):
            if seg.get("type") == "BUSINESS" and seg.get("name") == name:
                rev = seg.get("revenue")
                if rev is not None:
                    value = rev
                break
        series.append(value)
    return series


def _latest_two_valid(
    series: list[float | None],
) -> tuple[int, float, int, float] | None:
    """Find the two most recent periods (by index) where series has a value.

    Returns (prior_idx, prior_value, latest_idx, latest_value) or None if
    fewer than two populated points exist.
    """
    populated = [(i, v) for i, v in enumerate(series) if v is not None]
    if len(populated) < 2:
        return None
    prior_idx, prior_val = populated[-2]
    latest_idx, latest_val = populated[-1]
    return prior_idx, prior_val, latest_idx, latest_val


def _compute_yoy_growth(series: list[float | None]) -> float | None:
    """YoY growth % between the two most recent populated periods."""
    pair = _latest_two_valid(series)
    if pair is None:
        return None
    _, prior_val, _, latest_val = pair
    if prior_val == 0:
        return None
    return round((latest_val - prior_val) / abs(prior_val) * 100.0, 4)


def _compute_cagr(series: list[float | None]) -> float | None:
    """Multi-period CAGR % when segment has data in >= 3 periods spanning
    >= 2 full year-over-year intervals.

    Uses the earliest and latest populated points and the number of period
    steps between them as the year count.
    """
    populated = [(i, v) for i, v in enumerate(series) if v is not None]
    if len(populated) < 3:
        return None
    start_idx, start_val = populated[0]
    end_idx, end_val = populated[-1]
    n_years = end_idx - start_idx
    if n_years < 2:
        return None
    if start_val is None or start_val <= 0:
        return None
    if end_val is None:
        return None
    cagr = (end_val / start_val) ** (1.0 / n_years) - 1.0
    return round(cagr * 100.0, 4)


def _compute_contribution_to_growth(
    segment_series: list[float | None],
    total_revenue_history: list[float | None],
) -> float | None:
    """Segment's contribution to total company revenue growth (%).

    (seg_latest - seg_prior) / (total_latest - total_prior) * 100, using the
    SAME two most-recent-populated periods as the segment's YoY growth
    (item 1), so contribution and growth always describe the same window.
    Falls back to None if total revenue is unavailable for either of those
    two periods or the denominator is zero.
    """
    pair = _latest_two_valid(segment_series)
    if pair is None:
        return None
    prior_idx, seg_prior, latest_idx, seg_latest = pair

    if prior_idx >= len(total_revenue_history) or latest_idx >= len(total_revenue_history):
        return None
    total_prior = total_revenue_history[prior_idx]
    total_latest = total_revenue_history[latest_idx]
    if total_prior is None or total_latest is None:
        return None

    denom = total_latest - total_prior
    if denom == 0:
        return None

    return round((seg_latest - seg_prior) / denom * 100.0, 4)


def _classify_segment(
    n_populated_periods: int,
    yoy_growth_pct: float | None,
    contribution_to_growth_pct: float | None,
) -> str:
    """Classify a segment as GROWTH_DRIVER / DRAG / STABLE / INSUFFICIENT_DATA."""
    if n_populated_periods < 2 or yoy_growth_pct is None:
        return "INSUFFICIENT_DATA"

    is_drag = yoy_growth_pct < -5.0 or (
        contribution_to_growth_pct is not None and contribution_to_growth_pct < 0
    )
    if is_drag:
        return "DRAG"

    is_growth_driver = yoy_growth_pct > 5.0 and (
        contribution_to_growth_pct is not None and contribution_to_growth_pct > 0
    )
    if is_growth_driver:
        return "GROWTH_DRIVER"

    return "STABLE"


def _compute_hhi(shares_pct: list[float]) -> float | None:
    """Herfindahl-Hirschman Index from % shares (0-10000 scale)."""
    if len(shares_pct) < 2:
        return None
    return round(sum(s * s for s in shares_pct), 4)


# ── Core computation ─────────────────────────────────────────────────────


def compute_revenue_drivers(
    segment_history: list[dict],
    total_revenue_history: list[float | None],
) -> list[RevenueDriver]:
    """Compute per-segment revenue driver decomposition for BUSINESS segments.

    Parameters
    ----------
    segment_history : list[dict]
        Oldest -> newest. See module docstring / analyze_revenue_drivers for shape.
    total_revenue_history : list[float | None]
        Company-wide total revenue per period, same order/length as segment_history.
    """
    names = _business_segment_names(segment_history)
    latest_total = total_revenue_history[-1] if total_revenue_history else None

    drivers: list[RevenueDriver] = []
    for name in names:
        series = _segment_revenue_series(segment_history, name)
        n_populated = sum(1 for v in series if v is not None)

        latest_revenue = series[-1] if series else None

        revenue_share_pct = None
        if latest_revenue is not None and latest_total not in (None, 0):
            revenue_share_pct = round(latest_revenue / latest_total * 100.0, 4)

        yoy_growth_pct = _compute_yoy_growth(series)
        cagr_pct = _compute_cagr(series)
        contribution_to_growth_pct = _compute_contribution_to_growth(
            series, total_revenue_history
        )
        classification = _classify_segment(n_populated, yoy_growth_pct, contribution_to_growth_pct)

        drivers.append(
            RevenueDriver(
                segment_name=name,
                latest_revenue=latest_revenue,
                revenue_share_pct=revenue_share_pct,
                yoy_growth_pct=yoy_growth_pct,
                cagr_pct=cagr_pct,
                contribution_to_growth_pct=contribution_to_growth_pct,
                classification=classification,
            )
        )

    # Rank by |contribution_to_growth_pct| descending, None values last.
    drivers.sort(
        key=lambda d: (
            d.contribution_to_growth_pct is None,
            -abs(d.contribution_to_growth_pct) if d.contribution_to_growth_pct is not None else 0.0,
        )
    )

    return drivers


def compute_revenue_concentration_hhi(
    segment_history: list[dict],
    total_revenue_history: list[float | None],
) -> float | None:
    """Herfindahl-Hirschman Index of latest-period BUSINESS segment revenue shares."""
    if not segment_history:
        return None
    latest_total = total_revenue_history[-1] if total_revenue_history else None
    if latest_total in (None, 0):
        return None

    latest_period = segment_history[-1]
    shares = []
    for seg in latest_period.get("segments", []):
        if seg.get("type") != "BUSINESS":
            continue
        rev = seg.get("revenue")
        if rev is None:
            continue
        shares.append(rev / latest_total * 100.0)

    return _compute_hhi(shares)


def compute_total_revenue_growth(total_revenue_history: list[float | None]) -> float | None:
    """Company-wide YoY revenue growth % using the two most recent valid periods."""
    return _compute_yoy_growth(total_revenue_history)


# ── Orchestrator ──────────────────────────────────────────────────────────


def analyze_revenue_drivers(
    segment_history: list[dict],
    total_revenue_history: list[float] | None = None,
) -> RevenueDriversResult:
    """Complete revenue drivers analysis.

    Parameters
    ----------
    segment_history : list[dict]
        Oldest -> newest, one entry per fiscal period actually ingested:
        [{"period_end_date": "2023-12-31", "segments": [{"name", "type", "revenue"}, ...]}, ...]
        Segment revenue may be None (skip, don't treat as 0). The same
        segment name can appear across multiple periods; a period's segment
        list can be missing a segment present in other periods.
    total_revenue_history : list[float | None] | None
        Company-wide total revenue per period, same order/length as
        segment_history. May contain None entries for periods with no
        reported total_revenue.
    """
    segment_history = segment_history or []
    total_revenue_history = total_revenue_history or []

    drivers = compute_revenue_drivers(segment_history, total_revenue_history)
    hhi = compute_revenue_concentration_hhi(segment_history, total_revenue_history)
    total_growth = compute_total_revenue_growth(total_revenue_history)

    return RevenueDriversResult(
        drivers=drivers,
        revenue_concentration_hhi=hhi,
        total_revenue_yoy_growth_pct=total_growth,
        periods_analyzed=len(segment_history),
    )
