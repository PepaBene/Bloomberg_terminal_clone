"""Growth Profile & Operating Leverage Engine.

Pure computation engine for multi-period growth-trend analysis (revenue,
net income, EPS, FCF) and multi-period operating leverage / incremental
margin trend analysis.

This is the fuller, multi-period companion to
`business_model_engine.compute_scaling_behavior()`, which only computes a
single latest-vs-prior-period operating leverage figure. Backs the
`/v3/company/{entity_id}/growth-profile` and
`/v3/company/{entity_id}/operating-leverage` endpoints.

No database access — all functions accept and return plain data.
"""

from __future__ import annotations

import logging
import statistics
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Metrics analyzed in the growth profile section, in output order.
GROWTH_METRICS = ("revenue", "net_income", "eps", "fcf")


# ── Dataclasses ───────────────────────────────────────────────────────────


@dataclass
class GrowthSeries:
    """Growth-trend analysis for a single financial metric."""

    metric: str  # "revenue" / "net_income" / "eps" / "fcf"
    latest_yoy_growth_pct: float | None = None
    cagr_pct: float | None = None
    growth_volatility: float | None = None
    growth_trend: str = "UNKNOWN"  # ACCELERATING/DECELERATING/STABLE/UNKNOWN
    positive_growth_period_pct: float | None = None


@dataclass
class OperatingLeverageDetail:
    """Multi-period operating leverage and incremental margin trend."""

    avg_operating_leverage: float | None = None
    operating_leverage_stability: float | None = None  # stdev; lower = more stable
    operating_leverage_trend: list[dict] = field(default_factory=list)
    incremental_margin_trend: list[dict] = field(default_factory=list)


@dataclass
class GrowthProfileResult:
    """Complete growth profile and operating leverage analysis."""

    growth_series: list[GrowthSeries] = field(default_factory=list)
    operating_leverage: OperatingLeverageDetail = field(default_factory=OperatingLeverageDetail)
    periods_analyzed: int = 0


# ── Shared helpers ────────────────────────────────────────────────────────


def _extract_series(history: list[dict], key: str) -> list[tuple[str | None, float]]:
    """Extract (period_end_date, value) pairs for `key`, skipping missing/None values."""
    out: list[tuple[str | None, float]] = []
    for period in history:
        value = period.get(key)
        if value is None:
            continue
        out.append((period.get("period_end_date"), value))
    return out


def _consecutive_growth_rates(points: list[tuple[str | None, float]]) -> list[float]:
    """Period-over-period growth rate (%) for every consecutive pair with a non-zero prior."""
    rates: list[float] = []
    for i in range(1, len(points)):
        _, prior = points[i - 1]
        _, curr = points[i]
        if prior == 0:
            continue
        rates.append((curr - prior) / abs(prior) * 100.0)
    return rates


def _compute_growth_trend(growth_rates: list[float]) -> str:
    """Classify growth-rate trend as ACCELERATING/DECELERATING/STABLE/UNKNOWN.

    Mirrors business_model_engine._compute_trend()'s first-half/second-half-mean
    comparison pattern, but applied to growth RATES rather than levels.
    """
    if len(growth_rates) < 2:
        return "UNKNOWN"
    first_half = statistics.mean(growth_rates[: len(growth_rates) // 2])
    second_half = statistics.mean(growth_rates[len(growth_rates) // 2 :])
    diff = second_half - first_half
    # Absolute threshold on percentage-point difference in growth rate.
    if diff > 1.0:
        return "ACCELERATING"
    elif diff < -1.0:
        return "DECELERATING"
    return "STABLE"


def analyze_growth_series(history: list[dict], metric: str) -> GrowthSeries:
    """Analyze growth trend for a single metric across multi-period history.

    Parameters
    ----------
    history : list[dict]
        Oldest -> newest financial periods.
    metric : str
        Key to extract from each period dict (e.g. "revenue", "net_income").
    """
    points = _extract_series(history, metric)

    latest_yoy: float | None = None
    if len(points) >= 2:
        _, prior_val = points[-2]
        _, latest_val = points[-1]
        if prior_val != 0:
            latest_yoy = round((latest_val - prior_val) / abs(prior_val) * 100.0, 4)

    cagr: float | None = None
    if len(points) >= 3:
        earliest_date, earliest_val = points[0]
        latest_date, latest_val = points[-1]
        n_periods = len(points) - 1  # number of intervals spanned
        if n_periods >= 2 and earliest_val > 0:
            cagr = round(((latest_val / earliest_val) ** (1.0 / n_periods) - 1.0) * 100.0, 4)
        elif earliest_val <= 0:
            logger.info(
                "Skipping CAGR for metric=%s: non-positive base period value (%s) "
                "makes CAGR mathematically undefined/misleading.",
                metric,
                earliest_val,
            )

    growth_rates = _consecutive_growth_rates(points)

    volatility: float | None = None
    if len(growth_rates) >= 2:
        volatility = round(statistics.stdev(growth_rates), 4)

    trend = _compute_growth_trend(growth_rates)

    positive_pct: float | None = None
    if growth_rates:
        positive_pct = round(
            sum(1 for r in growth_rates if r > 0) / len(growth_rates) * 100.0, 4
        )

    return GrowthSeries(
        metric=metric,
        latest_yoy_growth_pct=latest_yoy,
        cagr_pct=cagr,
        growth_volatility=volatility,
        growth_trend=trend,
        positive_growth_period_pct=positive_pct,
    )


# ── Operating Leverage Detail ────────────────────────────────────────────


def compute_operating_leverage_detail(history: list[dict]) -> OperatingLeverageDetail:
    """Compute the full multi-period operating leverage / incremental margin trend.

    Parameters
    ----------
    history : list[dict]
        Oldest -> newest financial periods, each with revenue, ebit,
        period_end_date. Guards mirror business_model_engine.compute_scaling_behavior():
        a pair is skipped if %-change in revenue is ~0 (abs <= 0.001) or prior
        EBIT is 0 (would produce a nonsense huge/undefined value).
    """
    op_lev_trend: list[dict] = []
    incr_margin_trend: list[dict] = []
    op_lev_values: list[float] = []

    for i in range(1, len(history)):
        prior = history[i - 1]
        curr = history[i]

        rev_prior = prior.get("revenue")
        rev_now = curr.get("revenue")
        ebit_prior = prior.get("ebit")
        ebit_now = curr.get("ebit")
        period_end_date = curr.get("period_end_date")

        if rev_prior is None or rev_now is None or ebit_prior is None or ebit_now is None:
            continue

        # Operating leverage: % change EBIT / % change revenue
        if rev_prior != 0:
            rev_change = (rev_now - rev_prior) / abs(rev_prior)
            if abs(rev_change) > 0.001 and ebit_prior != 0:
                ebit_change = (ebit_now - ebit_prior) / abs(ebit_prior)
                op_lev = round(ebit_change / rev_change, 4)
                op_lev_values.append(op_lev)
                op_lev_trend.append(
                    {"period_end_date": period_end_date, "operating_leverage": op_lev}
                )

        # Incremental margin: delta EBIT / delta revenue (no %-change denominator issue)
        delta_rev = rev_now - rev_prior
        delta_ebit = ebit_now - ebit_prior
        if abs(delta_rev) > 0:
            incr_margin = round(delta_ebit / delta_rev, 4)
            incr_margin_trend.append(
                {"period_end_date": period_end_date, "incremental_margin": incr_margin}
            )

    avg_op_lev = round(statistics.mean(op_lev_values), 4) if op_lev_values else None
    op_lev_stability = (
        round(statistics.stdev(op_lev_values), 4) if len(op_lev_values) >= 2 else None
    )

    return OperatingLeverageDetail(
        avg_operating_leverage=avg_op_lev,
        operating_leverage_stability=op_lev_stability,
        operating_leverage_trend=op_lev_trend,
        incremental_margin_trend=incr_margin_trend,
    )


# ── Orchestrator ──────────────────────────────────────────────────────────


def analyze_growth_profile(history: list[dict]) -> GrowthProfileResult:
    """Complete growth profile and operating leverage analysis.

    Parameters
    ----------
    history : list[dict]
        Oldest -> newest, one dict per real ingested fiscal period (2-8
        periods typical). Each dict may have: period_end_date, revenue,
        net_income, ebit, ebitda, eps, fcf — any of which may be missing
        or None.
    """
    history = history or []

    growth_series = [analyze_growth_series(history, metric) for metric in GROWTH_METRICS]
    operating_leverage = compute_operating_leverage_detail(history)

    return GrowthProfileResult(
        growth_series=growth_series,
        operating_leverage=operating_leverage,
        periods_analyzed=len(history),
    )
