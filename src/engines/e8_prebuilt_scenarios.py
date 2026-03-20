"""E8 Pre-built macro shock scenarios for DCF sensitivity analysis.

Each scenario defines additive deltas applied to base DCF assumptions.
For example, ``discount_rate: 0.03`` means the WACC increases by 3 percentage
points from its base value.
"""

from __future__ import annotations


PREBUILT_SCENARIOS: dict[str, dict] = {
    "STAGFLATION": {
        "label": "Stagflation",
        "description": "Rising rates with falling growth and compressed margins.",
        "shocks": {
            "discount_rate": 0.03,
            "revenue_growth": -0.05,
            "ebit_margin": -0.03,
        },
    },
    "DEFLATION": {
        "label": "Deflation / Secular Stagnation",
        "description": "Low rates but collapsing demand and terminal growth.",
        "shocks": {
            "discount_rate": -0.02,
            "revenue_growth": -0.08,
            "terminal_growth": -0.01,
        },
    },
    "RATE_NORMALIZATION": {
        "label": "Rate Normalization",
        "description": "Rates revert higher with mild demand softening.",
        "shocks": {
            "discount_rate": 0.02,
            "revenue_growth": -0.02,
        },
    },
    "TRADE_WAR": {
        "label": "Trade War",
        "description": "Tariffs compress margins and crimp growth, with higher capex for re-shoring.",
        "shocks": {
            "revenue_growth": -0.04,
            "ebit_margin": -0.05,
            "capex_to_revenue": 0.01,
        },
    },
    "PANDEMIC_SHOCK": {
        "label": "Pandemic Shock",
        "description": "Severe demand collapse with margin compression and working-capital drag.",
        "shocks": {
            "discount_rate": -0.015,
            "revenue_growth": -0.15,
            "ebit_margin": -0.08,
            "wc_to_revenue": 0.03,
        },
    },
}


def get_prebuilt_scenario(name: str) -> dict | None:
    """Look up a pre-built scenario by name."""
    return PREBUILT_SCENARIOS.get(name)


def list_prebuilt_scenarios() -> list[dict]:
    """Return summary list of all pre-built scenarios."""
    return [
        {"name": key, **val}
        for key, val in PREBUILT_SCENARIOS.items()
    ]
