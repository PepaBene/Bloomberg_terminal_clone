"""E5 Pre-defined stress-test scenarios.

Historical scenarios reference actual market event date ranges.
Hypothetical scenarios define parameterised shocks applied to the current position.
"""

from __future__ import annotations


# ---------------------------------------------------------------------------
# Historical Scenarios (replay actual market returns)
# ---------------------------------------------------------------------------

HISTORICAL_SCENARIOS: dict[str, dict] = {
    "GFC_2008": {
        "label": "Global Financial Crisis",
        "start": "2008-09-01",
        "end": "2009-03-31",
        "description": "Sep 2008 – Mar 2009 credit crisis and equity sell-off.",
    },
    "COVID_2020": {
        "label": "COVID Crash",
        "start": "2020-02-19",
        "end": "2020-03-23",
        "description": "Rapid, indiscriminate sell-off during pandemic onset.",
    },
    "RATE_SHOCK_2022": {
        "label": "2022 Rate Shock",
        "start": "2022-01-03",
        "end": "2022-10-14",
        "description": "Duration/growth stock impact from aggressive rate hikes.",
    },
    "DOTCOM_2000": {
        "label": "Dot-Com Bust",
        "start": "2000-03-10",
        "end": "2002-10-09",
        "description": "Long, grinding bear market following tech bubble.",
    },
}


# ---------------------------------------------------------------------------
# Hypothetical Scenarios (user-defined shocks)
# ---------------------------------------------------------------------------

HYPOTHETICAL_SCENARIOS: dict[str, dict] = {
    # `equity_shock`/`rate_shock_bps`/`spread_shock_bps` mirror the field
    # shape used by `portfolio_risk_engine.HISTORICAL_SCENARIOS` so callers
    # can treat security-level and portfolio-level scenario dicts uniformly.
    # `shock_pct` is kept alongside `equity_shock` (same value) since
    # existing callers in `e5_risk.py` still key off it.
    "EQUITY_MINUS_10": {
        "label": "Equity -10%",
        "shock_pct": -0.10,
        "equity_shock": -0.10,
        "rate_shock_bps": 0,
        "spread_shock_bps": 0,
        "description": "Uniform 10% equity market decline.",
    },
    "EQUITY_MINUS_20": {
        "label": "Equity -20%",
        "shock_pct": -0.20,
        "equity_shock": -0.20,
        "rate_shock_bps": 0,
        "spread_shock_bps": 0,
        "description": "Uniform 20% equity market decline.",
    },
    "EQUITY_MINUS_30": {
        "label": "Equity -30%",
        "shock_pct": -0.30,
        "equity_shock": -0.30,
        "rate_shock_bps": 0,
        "spread_shock_bps": 0,
        "description": "Uniform 30% equity market decline.",
    },
    "EQUITY_MINUS_40": {
        "label": "Equity -40%",
        "shock_pct": -0.40,
        "equity_shock": -0.40,
        "rate_shock_bps": 0,
        "spread_shock_bps": 0,
        "description": "Uniform 40% equity market decline.",
    },
    "RATE_PLUS_100BPS": {
        "label": "Rates +100bps",
        "rate_shock_bps": 100,
        "equity_shock": 0.0,
        "spread_shock_bps": 0,
        "description": "Interest rates rise 100 basis points.",
    },
    "RATE_PLUS_200BPS": {
        "label": "Rates +200bps",
        "rate_shock_bps": 200,
        "equity_shock": 0.0,
        "spread_shock_bps": 0,
        "description": "Interest rates rise 200 basis points.",
    },
    "RATE_PLUS_300BPS": {
        "label": "Rates +300bps",
        "rate_shock_bps": 300,
        "equity_shock": 0.0,
        "spread_shock_bps": 0,
        "description": "Interest rates rise 300 basis points.",
    },
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_all_scenarios() -> dict[str, dict]:
    """Return combined dict of all scenario definitions."""
    combined: dict[str, dict] = {}
    for k, v in HISTORICAL_SCENARIOS.items():
        combined[k] = {**v, "type": "HISTORICAL"}
    for k, v in HYPOTHETICAL_SCENARIOS.items():
        combined[k] = {**v, "type": "HYPOTHETICAL"}
    return combined


def get_scenario(name: str) -> dict | None:
    """Look up a scenario by name."""
    if name in HISTORICAL_SCENARIOS:
        return {**HISTORICAL_SCENARIOS[name], "type": "HISTORICAL"}
    if name in HYPOTHETICAL_SCENARIOS:
        return {**HYPOTHETICAL_SCENARIOS[name], "type": "HYPOTHETICAL"}
    return None
