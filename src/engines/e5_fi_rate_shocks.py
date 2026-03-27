"""E5 Extension: Fixed Income Rate Shock Scenarios.

Historical rate shock scenarios for bond portfolio stress testing.
Uses the duration-convexity approximation to estimate P&L impact
from rate moves and spread widening.
"""

from __future__ import annotations


# ---------------------------------------------------------------------------
# Historical rate shock scenarios
# ---------------------------------------------------------------------------

FI_RATE_SCENARIOS: dict[str, dict] = {
    "BOND_MASSACRE_1994": {
        "label": "1994 Bond Massacre",
        "rate_shift_bps": 300,
        "spread_impact_ig_bps": 50,
        "spread_impact_hy_bps": 150,
        "duration_months": 12,
        "description": (
            "Fed surprise tightening cycle. Treasury yields rose ~300bps. "
            "IG spreads widened ~50bps, HY ~150bps."
        ),
    },
    "TAPER_TANTRUM_2013": {
        "label": "2013 Taper Tantrum",
        "rate_shift_bps": 140,
        "spread_impact_ig_bps": 30,
        "spread_impact_hy_bps": 100,
        "duration_months": 4,
        "description": (
            "Bernanke taper signal. 10Y rose ~140bps. Moderate spread widening."
        ),
    },
    "RATE_SHOCK_2022": {
        "label": "2022 Fed Hiking Cycle",
        "rate_shift_bps": 425,
        "spread_impact_ig_bps": 80,
        "spread_impact_hy_bps": 250,
        "duration_months": 18,
        "description": (
            "Aggressive Fed tightening from 0% to 5.25%. "
            "Most rapid cycle since Volcker."
        ),
    },
    "BULL_RALLY_2019": {
        "label": "2019 Bull Rally",
        "rate_shift_bps": -200,
        "spread_impact_ig_bps": -40,
        "spread_impact_hy_bps": -80,
        "duration_months": 12,
        "description": (
            "Global slowdown fears. Rates fell ~200bps, spreads compressed."
        ),
    },
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_fi_rate_scenarios() -> dict[str, dict]:
    """Return all available FI rate shock scenarios."""
    return dict(FI_RATE_SCENARIOS)


def get_fi_rate_scenario(scenario_id: str) -> dict | None:
    """Look up a single scenario by ID."""
    return FI_RATE_SCENARIOS.get(scenario_id)


def apply_fi_rate_scenario(
    positions: list[dict],
    scenario_id: str,
) -> dict:
    """Apply a historical rate scenario to a bond portfolio.

    Parameters
    ----------
    positions : list[dict]
        Each position dict must contain:
        - ``market_value`` (float): current market value
        - ``modified_duration`` (float): modified duration
        - ``convexity`` (float, optional, default 0): convexity
        - ``spread_duration`` (float | None): spread duration; defaults to modified_duration
        - ``is_investment_grade`` (bool, default True): IG vs HY classification
        - ``cusip`` (str | None): bond identifier

    scenario_id : str
        Key from ``FI_RATE_SCENARIOS``.

    Returns
    -------
    dict with scenario details, total P&L, and per-position breakdown.

    Raises
    ------
    ValueError
        If the scenario_id is not found.

    Notes
    -----
    Rate P&L   = market_value * (-mod_dur * Δy + 0.5 * convexity * Δy²)
    Spread P&L = market_value * (-spread_dur * Δspread)
    Total P&L  = Rate P&L + Spread P&L

    Δy and Δspread are expressed in decimal (bps / 10000).
    """
    scenario = FI_RATE_SCENARIOS.get(scenario_id)
    if scenario is None:
        raise ValueError(f"Unknown FI rate scenario: {scenario_id}")

    rate_shift = scenario["rate_shift_bps"] / 10_000  # decimal
    spread_ig = scenario["spread_impact_ig_bps"] / 10_000
    spread_hy = scenario["spread_impact_hy_bps"] / 10_000

    total_rate_pnl = 0.0
    total_spread_pnl = 0.0
    total_mv = 0.0
    by_position: list[dict] = []

    for pos in positions:
        mv = float(pos.get("market_value", 0.0))
        mod_dur = float(pos.get("modified_duration", 0.0))
        cvx = float(pos.get("convexity", 0.0) or 0.0)
        spread_dur = pos.get("spread_duration")
        if spread_dur is None:
            spread_dur = mod_dur
        else:
            spread_dur = float(spread_dur)
        is_ig = pos.get("is_investment_grade", True)
        cusip = pos.get("cusip")

        # Rate P&L = MV * (-D * Δy + 0.5 * C * Δy²)
        rate_pnl = mv * (-mod_dur * rate_shift + 0.5 * cvx * rate_shift ** 2)

        # Spread P&L = MV * (-spread_dur * Δspread)
        spread_impact = spread_ig if is_ig else spread_hy
        spread_pnl = mv * (-spread_dur * spread_impact)

        pos_total = rate_pnl + spread_pnl

        total_rate_pnl += rate_pnl
        total_spread_pnl += spread_pnl
        total_mv += mv

        by_position.append({
            "cusip": cusip,
            "total_pnl": round(pos_total, 2),
            "rate_pnl": round(rate_pnl, 2),
            "spread_pnl": round(spread_pnl, 2),
        })

    total_pnl = total_rate_pnl + total_spread_pnl
    total_pnl_pct = (total_pnl / total_mv * 100) if total_mv else 0.0

    return {
        "scenario": {
            "scenario_id": scenario_id,
            **scenario,
        },
        "total_pnl": round(total_pnl, 2),
        "total_pnl_pct": round(total_pnl_pct, 4),
        "rate_pnl": round(total_rate_pnl, 2),
        "spread_pnl": round(total_spread_pnl, 2),
        "by_position": by_position,
    }
