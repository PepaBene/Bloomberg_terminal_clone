"""ESG implied-temperature scoring engine.

Converts entity emissions trajectory data into a Paris-aligned
implied temperature rise score.  The methodology is a simplified
version of the TCFD-aligned approach:

1. Compute a linear emissions trend from scope 1+2 (+ scope 3 if available).
2. Project forward to 2050 and compare against global carbon budget paths.
3. Map the projected trajectory to an implied temperature rise.
"""

from __future__ import annotations

from dataclasses import dataclass


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
