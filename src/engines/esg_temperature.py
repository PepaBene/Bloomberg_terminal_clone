"""ESG implied-temperature scoring engine.

Converts entity emissions trajectory data into a Paris-aligned
implied temperature rise score.  The methodology is a simplified
version of the TCFD-aligned approach:

1. Compute a linear emissions trend from scope 1+2 (+ scope 3 if available).
2. Project forward to 2050 and compare against global carbon budget paths.
3. Map the projected trajectory to an implied temperature rise.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from typing import Any


# Budget parameters (simplified — GtCO2 remaining from 2025 to 2050)
_BUDGET_1_5 = 400   # ~1.5 °C budget
_BUDGET_2_0 = 1150  # ~2.0 °C budget
_BUDGET_3_0 = 2300  # ~3.0 °C budget


@dataclass
class TemperatureResult:
    """Output of the temperature scoring engine."""

    implied_temperature: float
    alignment: str
    emissions_trend_pct: float | None
    data_quality_flag: str


def classify_alignment(temp: float) -> str:
    """Map an implied temperature to an alignment bucket."""
    if temp <= 1.5:
        return "BELOW_1_5C"
    if temp <= 2.0:
        return "BETWEEN_1_5_AND_2C"
    if temp <= 3.0:
        return "BETWEEN_2_AND_3C"
    return "ABOVE_3C"


def compute_emissions_trend(emissions_series: list[float]) -> float | None:
    """YoY percentage change (last vs first) annualised.

    Parameters
    ----------
    emissions_series : list[float]
        Annual total emissions (oldest first), must have ≥ 2 values.

    Returns
    -------
    float | None
        Annualised % change, or None if insufficient data.
    """
    if len(emissions_series) < 2:
        return None
    first, last = emissions_series[0], emissions_series[-1]
    n_years = len(emissions_series) - 1
    if first == 0:
        return None
    return ((last / first) ** (1 / n_years) - 1) * 100


def score_temperature(
    current_annual_emissions: float,
    emissions_trend_pct: float | None,
    has_scope3: bool = False,
) -> TemperatureResult:
    """Compute implied temperature rise for a single entity.

    Parameters
    ----------
    current_annual_emissions : float
        Latest total emissions (scope 1 + 2, optionally + 3) in tonnes CO2e.
    emissions_trend_pct : float | None
        Annualised emissions growth rate (%). Negative = shrinking.
    has_scope3 : bool
        Whether scope 3 is included — affects data quality flag.

    Returns
    -------
    TemperatureResult
    """
    if emissions_trend_pct is None:
        return TemperatureResult(
            implied_temperature=0.0,
            alignment="INSUFFICIENT_DATA",
            emissions_trend_pct=None,
            data_quality_flag="INSUFFICIENT",
        )

    # Project cumulative emissions over 25 years (2025-2050)
    annual_growth = 1 + emissions_trend_pct / 100
    cumulative = 0.0
    annual = current_annual_emissions
    for _ in range(25):
        cumulative += annual
        annual *= annual_growth

    # Convert entity cumulative to a proportion-of-budget proxy
    # (In production this would be weighted by the entity's share of global output;
    #  here we use a heuristic scale factor.)
    #
    # Map: cumulative ≤ budget_1.5 → 1.2°C, ... ≥ budget_3.0 → 3.5°C
    # Linear interpolation between budget boundaries.
    if cumulative <= 0:
        temp = 1.0
    elif cumulative <= _BUDGET_1_5:
        temp = 1.0 + 0.5 * (cumulative / _BUDGET_1_5)
    elif cumulative <= _BUDGET_2_0:
        temp = 1.5 + 0.5 * ((cumulative - _BUDGET_1_5) / (_BUDGET_2_0 - _BUDGET_1_5))
    elif cumulative <= _BUDGET_3_0:
        temp = 2.0 + 1.0 * ((cumulative - _BUDGET_2_0) / (_BUDGET_3_0 - _BUDGET_2_0))
    else:
        temp = 3.0 + 0.5 * min((cumulative - _BUDGET_3_0) / _BUDGET_3_0, 1.0)

    temp = round(temp, 2)
    alignment = classify_alignment(temp)
    quality = "FULL" if has_scope3 else "PARTIAL"

    return TemperatureResult(
        implied_temperature=temp,
        alignment=alignment,
        emissions_trend_pct=round(emissions_trend_pct, 4),
        data_quality_flag=quality,
    )


# ---------------------------------------------------------------------------
# ESGMetric -> temperature score assembly (persistence input builder)
# ---------------------------------------------------------------------------
# ESGMetric.metric_type values are matched case-insensitively by substring so
# the connector naming can vary. A metric is assigned to a scope by whichever
# scope token it contains.

_SCOPE1_TOKENS = ("scope1", "scope_1", "scope 1")
_SCOPE2_TOKENS = ("scope2", "scope_2", "scope 2")
_SCOPE3_TOKENS = ("scope3", "scope_3", "scope 3")


def _classify_scope(metric_type: str) -> str | None:
    """Return 'scope1'/'scope2'/'scope3'/'total' for an emissions metric, else None."""
    t = (metric_type or "").lower()
    if "emission" not in t and "ghg" not in t and "carbon" not in t and "co2" not in t:
        return None
    if any(tok in t for tok in _SCOPE1_TOKENS):
        return "scope1"
    if any(tok in t for tok in _SCOPE2_TOKENS):
        return "scope2"
    if any(tok in t for tok in _SCOPE3_TOKENS):
        return "scope3"
    return "total"


def summarize_entity_emissions(
    metric_rows: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Build ESGTemperatureScore field values from raw ESGMetric rows.

    Parameters
    ----------
    metric_rows:
        List of dicts with keys ``metric_type``, ``period_end_date`` (date),
        and ``value`` (float | None).

    Returns
    -------
    dict | None
        Field values for ``ESGTemperatureScore`` (excluding entity_id), or
        None when no usable emissions metrics are present (clean degrade).
    """
    # year -> {scope: value}
    by_year: dict[int, dict[str, float]] = defaultdict(dict)
    latest_by_year: dict[int, date] = {}

    for row in metric_rows:
        period_end = row.get("period_end_date")
        if period_end is None:
            continue
        scope = _classify_scope(row.get("metric_type", ""))
        if scope is None:
            continue
        value = row.get("value")
        if value is None:
            continue
        year = period_end.year
        # First-seen (or overwrite) per scope per year.
        by_year[year][scope] = float(value)
        if year not in latest_by_year or period_end > latest_by_year[year]:
            latest_by_year[year] = period_end

    if not by_year:
        return None

    def year_total(scopes: dict[str, float]) -> float:
        if "total" in scopes:
            base = scopes["total"]
        else:
            base = scopes.get("scope1", 0.0) + scopes.get("scope2", 0.0)
        return base + scopes.get("scope3", 0.0)

    years = sorted(by_year)
    series = [year_total(by_year[y]) for y in years]
    latest_year = years[-1]
    latest = by_year[latest_year]

    trend = compute_emissions_trend(series)
    current = series[-1]
    has_scope3 = "scope3" in latest

    result = score_temperature(current, trend, has_scope3=has_scope3)

    return {
        "as_of_date": latest_by_year[latest_year],
        "implied_temperature": result.implied_temperature,
        "alignment": result.alignment,
        "scope1_emissions": latest.get("scope1"),
        "scope2_emissions": latest.get("scope2"),
        "scope3_emissions": latest.get("scope3"),
        "emissions_trend_pct": result.emissions_trend_pct,
        "data_quality_flag": result.data_quality_flag,
    }
