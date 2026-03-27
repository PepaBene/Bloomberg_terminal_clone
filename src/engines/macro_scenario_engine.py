"""Pillar 3 Phase 4C — Engine 2: Macro Scenario Analysis Engine.

Pure computation engine for constructing macro scenarios and estimating
their impact on company EPS, margins, ratings, and price targets.

No database access — all functions accept and return plain data.
"""

from __future__ import annotations

from copy import deepcopy


# ── Constants ──────────────────────────────────────────────────────────────

PREBUILT_SCENARIOS: dict[str, dict] = {
    "soft_landing": {
        "scenario_name": "Soft Landing",
        "scenario_type": "prebuilt",
        "description": "Economy decelerates gradually; inflation falls toward target without recession.",
        "assumptions": {
            "gdp_growth_pct": 1.5,
            "inflation_pct": 2.5,
            "fed_funds_rate_pct": 4.0,
            "unemployment_pct": 4.2,
            "sp500_return_pct": 8.0,
            "credit_spread_bps": 120,
            "oil_price_usd": 75,
        },
    },
    "recession": {
        "scenario_name": "Recession",
        "scenario_type": "prebuilt",
        "description": "Two consecutive quarters of negative GDP growth with rising unemployment.",
        "assumptions": {
            "gdp_growth_pct": -2.0,
            "inflation_pct": 1.5,
            "fed_funds_rate_pct": 2.5,
            "unemployment_pct": 6.5,
            "sp500_return_pct": -25.0,
            "credit_spread_bps": 350,
            "oil_price_usd": 55,
        },
    },
    "stagflation": {
        "scenario_name": "Stagflation",
        "scenario_type": "prebuilt",
        "description": "Stagnant growth coupled with elevated inflation; worst of both worlds.",
        "assumptions": {
            "gdp_growth_pct": 0.0,
            "inflation_pct": 6.0,
            "fed_funds_rate_pct": 6.5,
            "unemployment_pct": 5.5,
            "sp500_return_pct": -15.0,
            "credit_spread_bps": 280,
            "oil_price_usd": 100,
        },
    },
    "deflation": {
        "scenario_name": "Deflation",
        "scenario_type": "prebuilt",
        "description": "Falling price levels with weak demand; risk of debt-deflation spiral.",
        "assumptions": {
            "gdp_growth_pct": -1.0,
            "inflation_pct": -1.5,
            "fed_funds_rate_pct": 0.5,
            "unemployment_pct": 5.0,
            "sp500_return_pct": -10.0,
            "credit_spread_bps": 250,
            "oil_price_usd": 45,
        },
    },
}

# Sector sensitivity to macro factors (multipliers for EPS/margin impact)
SECTOR_SENSITIVITIES: dict[str, dict[str, float]] = {
    "Energy": {"gdp": 1.5, "inflation": 0.8, "rates": -0.3, "oil": 2.0},
    "Materials": {"gdp": 1.3, "inflation": 0.6, "rates": -0.4, "oil": 0.5},
    "Industrials": {"gdp": 1.4, "inflation": -0.3, "rates": -0.5, "oil": -0.3},
    "Consumer Discretionary": {"gdp": 1.6, "inflation": -0.7, "rates": -0.6, "oil": -0.2},
    "Consumer Staples": {"gdp": 0.4, "inflation": -0.3, "rates": -0.2, "oil": -0.1},
    "Health Care": {"gdp": 0.5, "inflation": -0.2, "rates": -0.3, "oil": -0.1},
    "Financials": {"gdp": 1.2, "inflation": 0.2, "rates": 0.8, "oil": 0.0},
    "Information Technology": {"gdp": 1.3, "inflation": -0.4, "rates": -0.7, "oil": -0.1},
    "Communication Services": {"gdp": 1.0, "inflation": -0.3, "rates": -0.5, "oil": -0.1},
    "Utilities": {"gdp": 0.3, "inflation": -0.2, "rates": -0.8, "oil": -0.2},
    "Real Estate": {"gdp": 0.6, "inflation": 0.1, "rates": -1.0, "oil": -0.1},
}

# Baseline macro assumptions (current environment reference)
_BASELINE = {
    "gdp_growth_pct": 2.5,
    "inflation_pct": 3.0,
    "fed_funds_rate_pct": 5.0,
    "oil_price_usd": 80,
}


# ── Scenario Construction ─────────────────────────────────────────────────


def get_prebuilt_scenarios() -> dict[str, dict]:
    """Return all prebuilt scenarios (deep copy to prevent mutation)."""
    return deepcopy(PREBUILT_SCENARIOS)


def build_custom_scenario(
    scenario_name: str,
    assumptions: dict,
    description: str = "",
    created_by: str = "analyst",
) -> dict:
    """Build a custom macro scenario from user-supplied assumptions.

    Parameters
    ----------
    scenario_name : str
    assumptions : dict
        Must include at least gdp_growth_pct and inflation_pct.
    description : str
    created_by : str

    Returns
    -------
    dict
        Scenario definition.
    """
    required = {"gdp_growth_pct", "inflation_pct"}
    missing = required - set(assumptions.keys())
    if missing:
        raise ValueError(f"Missing required assumptions: {missing}")

    return {
        "scenario_name": scenario_name,
        "scenario_type": "custom",
        "description": description,
        "assumptions": assumptions,
        "created_by": created_by,
    }


# ── Impact Estimation ──────────────────────────────────────────────────────


def estimate_eps_impact(
    base_eps: float,
    scenario_assumptions: dict,
    sector: str,
) -> dict:
    """Estimate EPS under a macro scenario.

    Parameters
    ----------
    base_eps : float
        Current/consensus EPS.
    scenario_assumptions : dict
        Macro assumptions for the scenario.
    sector : str
        GICS sector.

    Returns
    -------
    dict
        {scenario_eps, eps_change_pct}
    """
    sensitivities = SECTOR_SENSITIVITIES.get(sector, {"gdp": 1.0, "inflation": -0.3, "rates": -0.4, "oil": 0.0})

    # Compute deviations from baseline
    gdp_delta = scenario_assumptions.get("gdp_growth_pct", _BASELINE["gdp_growth_pct"]) - _BASELINE["gdp_growth_pct"]
    inflation_delta = scenario_assumptions.get("inflation_pct", _BASELINE["inflation_pct"]) - _BASELINE["inflation_pct"]
    rates_delta = scenario_assumptions.get("fed_funds_rate_pct", _BASELINE["fed_funds_rate_pct"]) - _BASELINE["fed_funds_rate_pct"]
    oil_delta_pct = (
        (scenario_assumptions.get("oil_price_usd", _BASELINE["oil_price_usd"]) - _BASELINE["oil_price_usd"])
        / _BASELINE["oil_price_usd"]
        * 100
    )

    # Weighted impact on EPS (percentage)
    eps_impact_pct = (
        sensitivities["gdp"] * gdp_delta * 2.0
        + sensitivities["inflation"] * inflation_delta * 1.5
        + sensitivities["rates"] * rates_delta * 1.0
        + sensitivities["oil"] * (oil_delta_pct / 10.0) * 1.0
    )

    scenario_eps = round(base_eps * (1 + eps_impact_pct / 100), 2)
    eps_change_pct = round(eps_impact_pct, 2)

    return {"scenario_eps": scenario_eps, "eps_change_pct": eps_change_pct}


def estimate_margin_impact(
    base_margin_bps: float,
    scenario_assumptions: dict,
    sector: str,
) -> dict:
    """Estimate operating margin impact in basis points.

    Parameters
    ----------
    base_margin_bps : float
        Current margin in basis points (e.g. 1500 = 15%).
    scenario_assumptions : dict
    sector : str

    Returns
    -------
    dict
        {scenario_margin_bps, margin_change_bps}
    """
    sensitivities = SECTOR_SENSITIVITIES.get(sector, {"gdp": 1.0, "inflation": -0.3, "rates": -0.4, "oil": 0.0})

    gdp_delta = scenario_assumptions.get("gdp_growth_pct", _BASELINE["gdp_growth_pct"]) - _BASELINE["gdp_growth_pct"]
    inflation_delta = scenario_assumptions.get("inflation_pct", _BASELINE["inflation_pct"]) - _BASELINE["inflation_pct"]

    # Margin impact in bps
    margin_change = (
        sensitivities["gdp"] * gdp_delta * 30
        + sensitivities["inflation"] * inflation_delta * 25
    )
    margin_change = round(margin_change, 2)
    scenario_margin = round(base_margin_bps + margin_change, 2)

    return {"scenario_margin_bps": scenario_margin, "margin_change_bps": margin_change}


def classify_rating_implication(eps_change_pct: float) -> str:
    """Classify rating implication based on EPS change.

    Returns one of: UPGRADE, MAINTAIN, DOWNGRADE.
    """
    if eps_change_pct >= 10.0:
        return "UPGRADE"
    elif eps_change_pct <= -10.0:
        return "DOWNGRADE"
    return "MAINTAIN"


def compute_scenario_price_target(
    current_price: float,
    base_eps: float,
    scenario_eps: float,
    current_pe: float | None = None,
) -> float:
    """Estimate price target under a scenario using PE-based valuation.

    Parameters
    ----------
    current_price : float
    base_eps : float
    scenario_eps : float
    current_pe : float | None
        If not provided, derived from current_price / base_eps.

    Returns
    -------
    float
        Scenario price target.
    """
    if current_pe is None:
        if base_eps == 0:
            return current_price
        current_pe = current_price / base_eps

    # PE may compress/expand based on EPS direction
    eps_ratio = scenario_eps / base_eps if base_eps != 0 else 1.0
    if eps_ratio < 0.9:
        pe_adjustment = 0.9  # PE compression in stress
    elif eps_ratio > 1.1:
        pe_adjustment = 1.05  # Slight PE expansion
    else:
        pe_adjustment = 1.0

    scenario_pe = current_pe * pe_adjustment
    return round(scenario_pe * scenario_eps, 2)


# ── Company-Level Scenario Analysis ───────────────────────────────────────


def run_company_scenario(
    company: dict,
    scenario: dict,
) -> dict:
    """Run a full scenario analysis for a single company.

    Parameters
    ----------
    company : dict
        Must include: base_eps, sector, current_price, and optionally
        base_margin_bps, current_pe.
    scenario : dict
        Scenario definition with 'assumptions' key.

    Returns
    -------
    dict
        Full impact analysis.
    """
    assumptions = scenario.get("assumptions", {})
    sector = company.get("sector", "")
    base_eps = company.get("base_eps", 0.0)
    current_price = company.get("current_price", 0.0)
    base_margin_bps = company.get("base_margin_bps", 1500.0)

    eps_result = estimate_eps_impact(base_eps, assumptions, sector)
    margin_result = estimate_margin_impact(base_margin_bps, assumptions, sector)
    rating = classify_rating_implication(eps_result["eps_change_pct"])
    price_target = compute_scenario_price_target(
        current_price, base_eps, eps_result["scenario_eps"],
        current_pe=company.get("current_pe"),
    )

    return {
        "entity_id": company.get("entity_id"),
        "scenario_name": scenario.get("scenario_name", ""),
        "base_eps": base_eps,
        "scenario_eps": eps_result["scenario_eps"],
        "eps_change_pct": eps_result["eps_change_pct"],
        "margin_impact_bps": margin_result["margin_change_bps"],
        "rating_implication": rating,
        "price_target_scenario": price_target,
    }


def run_portfolio_scenario(
    companies: list[dict],
    scenario: dict,
) -> list[dict]:
    """Run scenario analysis across a portfolio of companies.

    Returns a list of impact dicts, sorted by EPS impact (most negative first).
    """
    results = [run_company_scenario(c, scenario) for c in companies]
    results.sort(key=lambda x: x["eps_change_pct"])
    return results


def compare_scenarios(
    company: dict,
    scenarios: list[dict],
) -> list[dict]:
    """Compare multiple scenarios for a single company.

    Returns list sorted by EPS change ascending (worst first).
    """
    results = [run_company_scenario(company, s) for s in scenarios]
    results.sort(key=lambda x: x["eps_change_pct"])
    return results


def generate_scenario_narrative_template(impact: dict) -> str:
    """Generate a text narrative template for a scenario impact.

    Parameters
    ----------
    impact : dict
        Output of run_company_scenario.

    Returns
    -------
    str
        Narrative template.
    """
    scenario = impact.get("scenario_name", "scenario")
    eps_chg = impact.get("eps_change_pct", 0.0)
    rating = impact.get("rating_implication", "MAINTAIN")
    margin_bps = impact.get("margin_impact_bps", 0.0)
    price_target = impact.get("price_target_scenario", 0.0)

    direction = "increase" if eps_chg >= 0 else "decrease"
    severity = "significantly " if abs(eps_chg) >= 15 else ""

    narrative = (
        f"Under the {scenario} scenario, EPS is estimated to {severity}{direction} "
        f"by {abs(eps_chg):.1f}%, with operating margins "
        f"{'expanding' if margin_bps >= 0 else 'compressing'} by "
        f"{abs(margin_bps):.0f} bps. "
        f"The rating implication is {rating}, with a scenario-implied "
        f"price target of ${price_target:,.2f}."
    )

    return narrative
