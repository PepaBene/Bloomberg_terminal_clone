"""Pillar 3 Phase 4C — Engine 1: Macro Thematic Exposure Engine.

Pure computation engine that scores company exposure to macro themes
(inflation, deflation, growth, rates, FX, commodities, energy transition)
using sector sensitivities and company-level financial data.

No database access — all functions accept and return plain data.
"""

from __future__ import annotations


# ── Constants ──────────────────────────────────────────────────────────────

MACRO_THEMES = [
    "inflation",
    "deflation",
    "growth",
    "rates",
    "fx",
    "commodities",
    "energy_transition",
]

# Sector-level sensitivity map: GICS sector -> theme -> base sensitivity (-100 to 100)
# Positive = benefits from the theme, Negative = harmed by the theme
SECTOR_THEME_SENSITIVITY: dict[str, dict[str, float]] = {
    "Energy": {
        "inflation": 40.0,
        "deflation": -50.0,
        "growth": 30.0,
        "rates": -20.0,
        "fx": -15.0,
        "commodities": 70.0,
        "energy_transition": -40.0,
    },
    "Materials": {
        "inflation": 35.0,
        "deflation": -40.0,
        "growth": 25.0,
        "rates": -15.0,
        "fx": -20.0,
        "commodities": 60.0,
        "energy_transition": 10.0,
    },
    "Industrials": {
        "inflation": -15.0,
        "deflation": -10.0,
        "growth": 45.0,
        "rates": -25.0,
        "fx": -20.0,
        "commodities": -15.0,
        "energy_transition": 20.0,
    },
    "Consumer Discretionary": {
        "inflation": -40.0,
        "deflation": 20.0,
        "growth": 50.0,
        "rates": -30.0,
        "fx": -10.0,
        "commodities": -20.0,
        "energy_transition": 5.0,
    },
    "Consumer Staples": {
        "inflation": -20.0,
        "deflation": 10.0,
        "growth": 10.0,
        "rates": -10.0,
        "fx": -25.0,
        "commodities": -30.0,
        "energy_transition": 0.0,
    },
    "Health Care": {
        "inflation": -10.0,
        "deflation": 5.0,
        "growth": 20.0,
        "rates": -15.0,
        "fx": -10.0,
        "commodities": -5.0,
        "energy_transition": 0.0,
    },
    "Financials": {
        "inflation": 10.0,
        "deflation": -30.0,
        "growth": 30.0,
        "rates": 50.0,
        "fx": -10.0,
        "commodities": 5.0,
        "energy_transition": 0.0,
    },
    "Information Technology": {
        "inflation": -25.0,
        "deflation": 10.0,
        "growth": 55.0,
        "rates": -40.0,
        "fx": -15.0,
        "commodities": -5.0,
        "energy_transition": 30.0,
    },
    "Communication Services": {
        "inflation": -15.0,
        "deflation": 10.0,
        "growth": 40.0,
        "rates": -30.0,
        "fx": -10.0,
        "commodities": -5.0,
        "energy_transition": 10.0,
    },
    "Utilities": {
        "inflation": -25.0,
        "deflation": 15.0,
        "growth": 5.0,
        "rates": -45.0,
        "fx": -5.0,
        "commodities": -20.0,
        "energy_transition": 35.0,
    },
    "Real Estate": {
        "inflation": 15.0,
        "deflation": -20.0,
        "growth": 20.0,
        "rates": -55.0,
        "fx": -5.0,
        "commodities": -10.0,
        "energy_transition": 5.0,
    },
}


# ── Theme-Specific Exposure Functions ──────────────────────────────────────


def compute_inflation_exposure(company: dict) -> dict:
    """Compute inflation exposure for a company.

    Parameters
    ----------
    company : dict
        - sector: str (GICS sector)
        - gross_margin: float (0-100)
        - pricing_power_score: float (0-100, optional)
        - cost_structure_pct_variable: float (0-100, optional)
        - revenue_growth_yoy: float (%, optional)

    Returns
    -------
    dict
        {score, direction, evidence}
    """
    sector = company.get("sector", "")
    base = SECTOR_THEME_SENSITIVITY.get(sector, {}).get("inflation", 0.0)

    adjustments = 0.0
    evidence = []

    # Pricing power mitigates inflation harm
    pricing_power = company.get("pricing_power_score")
    if pricing_power is not None:
        if pricing_power >= 70:
            adjustments += 15.0
            evidence.append("Strong pricing power mitigates inflation risk")
        elif pricing_power <= 30:
            adjustments -= 10.0
            evidence.append("Weak pricing power amplifies inflation risk")

    # High variable costs amplify inflation exposure
    variable_pct = company.get("cost_structure_pct_variable")
    if variable_pct is not None:
        if variable_pct >= 70:
            adjustments -= 15.0
            evidence.append("High variable cost structure increases inflation sensitivity")
        elif variable_pct <= 30:
            adjustments += 10.0
            evidence.append("Low variable costs provide inflation buffer")

    # High gross margin provides buffer
    gross_margin = company.get("gross_margin")
    if gross_margin is not None:
        if gross_margin >= 60:
            adjustments += 10.0
            evidence.append("High gross margin provides inflation cushion")
        elif gross_margin <= 25:
            adjustments -= 10.0
            evidence.append("Low gross margin increases inflation vulnerability")

    score = max(-100.0, min(100.0, base + adjustments))
    direction = "positive" if score > 0 else "negative" if score < 0 else "neutral"

    return {"score": round(score, 2), "direction": direction, "evidence": evidence}


def compute_rates_exposure(company: dict) -> dict:
    """Compute interest rate exposure.

    Parameters
    ----------
    company : dict
        - sector: str
        - debt_to_equity: float
        - pct_floating_rate_debt: float (0-100, optional)
        - duration_years: float (optional, for financial companies)
    """
    sector = company.get("sector", "")
    base = SECTOR_THEME_SENSITIVITY.get(sector, {}).get("rates", 0.0)

    adjustments = 0.0
    evidence = []

    # High leverage amplifies rate sensitivity
    dte = company.get("debt_to_equity")
    if dte is not None:
        if dte >= 2.0:
            adjustments -= 20.0
            evidence.append("High leverage amplifies rate sensitivity")
        elif dte <= 0.3:
            adjustments += 10.0
            evidence.append("Low leverage reduces rate sensitivity")

    # Floating rate debt
    floating_pct = company.get("pct_floating_rate_debt")
    if floating_pct is not None:
        if floating_pct >= 50:
            adjustments -= 15.0
            evidence.append("High floating-rate debt increases rate exposure")
        elif floating_pct <= 10:
            adjustments += 5.0
            evidence.append("Minimal floating-rate debt limits direct rate impact")

    # Duration for financials (banks benefit from rising rates with short assets/long liabilities)
    duration = company.get("duration_years")
    if duration is not None and sector == "Financials":
        if duration <= 2.0:
            adjustments += 15.0
            evidence.append("Short duration benefits from rising rates")
        elif duration >= 8.0:
            adjustments -= 15.0
            evidence.append("Long duration amplifies rate risk")

    score = max(-100.0, min(100.0, base + adjustments))
    direction = "positive" if score > 0 else "negative" if score < 0 else "neutral"

    return {"score": round(score, 2), "direction": direction, "evidence": evidence}


def compute_fx_exposure(company: dict) -> dict:
    """Compute foreign exchange exposure.

    Parameters
    ----------
    company : dict
        - sector: str
        - international_revenue_pct: float (0-100)
        - hedging_ratio: float (0-100, optional)
        - functional_currency: str (optional)
    """
    sector = company.get("sector", "")
    base = SECTOR_THEME_SENSITIVITY.get(sector, {}).get("fx", 0.0)

    adjustments = 0.0
    evidence = []

    intl_rev = company.get("international_revenue_pct", 0.0)
    if intl_rev >= 60:
        adjustments -= 20.0
        evidence.append("High international revenue increases FX exposure")
    elif intl_rev >= 30:
        adjustments -= 10.0
        evidence.append("Moderate international revenue creates FX exposure")
    elif intl_rev <= 10:
        adjustments += 10.0
        evidence.append("Domestic-focused revenue limits FX exposure")

    hedging = company.get("hedging_ratio")
    if hedging is not None:
        if hedging >= 70:
            adjustments += 15.0
            evidence.append("Strong hedging program mitigates FX risk")
        elif hedging <= 20:
            adjustments -= 5.0
            evidence.append("Limited hedging leaves FX exposure unmanaged")

    score = max(-100.0, min(100.0, base + adjustments))
    direction = "positive" if score > 0 else "negative" if score < 0 else "neutral"

    return {"score": round(score, 2), "direction": direction, "evidence": evidence}


def compute_commodity_exposure(company: dict) -> dict:
    """Compute commodity price exposure.

    Parameters
    ----------
    company : dict
        - sector: str
        - commodity_input_pct: float (0-100, pct of COGS from commodities)
        - is_commodity_producer: bool
        - hedging_months: int (months of forward hedging)
    """
    sector = company.get("sector", "")
    base = SECTOR_THEME_SENSITIVITY.get(sector, {}).get("commodities", 0.0)

    adjustments = 0.0
    evidence = []

    if company.get("is_commodity_producer"):
        adjustments += 25.0
        evidence.append("Commodity producer benefits from rising commodity prices")

    commodity_input = company.get("commodity_input_pct", 0.0)
    if commodity_input >= 50:
        adjustments -= 20.0
        evidence.append("High commodity input costs create negative exposure")
    elif commodity_input >= 25:
        adjustments -= 10.0
        evidence.append("Moderate commodity input exposure")

    hedge_months = company.get("hedging_months")
    if hedge_months is not None:
        if hedge_months >= 12:
            adjustments += 10.0
            evidence.append("Long-dated hedging reduces near-term commodity risk")
        elif hedge_months <= 3:
            adjustments -= 5.0
            evidence.append("Short hedging horizon leaves commodity risk open")

    score = max(-100.0, min(100.0, base + adjustments))
    direction = "positive" if score > 0 else "negative" if score < 0 else "neutral"

    return {"score": round(score, 2), "direction": direction, "evidence": evidence}


def compute_growth_exposure(company: dict) -> dict:
    """Compute exposure to economic growth / slowdown.

    Parameters
    ----------
    company : dict
        - sector: str
        - revenue_growth_yoy: float (%)
        - earnings_cyclicality: float (0-100, higher = more cyclical)
        - backlog_months: float (months of order backlog, optional)
    """
    sector = company.get("sector", "")
    base = SECTOR_THEME_SENSITIVITY.get(sector, {}).get("growth", 0.0)

    adjustments = 0.0
    evidence = []

    cyclicality = company.get("earnings_cyclicality")
    if cyclicality is not None:
        if cyclicality >= 70:
            adjustments += 15.0
            evidence.append("Highly cyclical earnings amplify growth exposure")
        elif cyclicality <= 30:
            adjustments -= 10.0
            evidence.append("Defensive earnings reduce growth sensitivity")

    rev_growth = company.get("revenue_growth_yoy")
    if rev_growth is not None:
        if rev_growth >= 20:
            adjustments += 10.0
            evidence.append("Strong revenue growth signals high growth leverage")
        elif rev_growth <= 0:
            adjustments -= 10.0
            evidence.append("Revenue decline suggests vulnerability in slowdown")

    backlog = company.get("backlog_months")
    if backlog is not None:
        if backlog >= 12:
            adjustments += 10.0
            evidence.append("Deep order backlog provides growth visibility")
        elif backlog <= 2:
            adjustments -= 5.0
            evidence.append("Thin backlog limits near-term growth visibility")

    score = max(-100.0, min(100.0, base + adjustments))
    direction = "positive" if score > 0 else "negative" if score < 0 else "neutral"

    return {"score": round(score, 2), "direction": direction, "evidence": evidence}


def compute_energy_transition_exposure(company: dict) -> dict:
    """Compute exposure to the energy transition theme.

    Parameters
    ----------
    company : dict
        - sector: str
        - green_revenue_pct: float (0-100)
        - carbon_intensity: float (tons CO2 / $M revenue, optional)
        - capex_green_pct: float (0-100, optional)
    """
    sector = company.get("sector", "")
    base = SECTOR_THEME_SENSITIVITY.get(sector, {}).get("energy_transition", 0.0)

    adjustments = 0.0
    evidence = []

    green_rev = company.get("green_revenue_pct", 0.0)
    if green_rev >= 50:
        adjustments += 25.0
        evidence.append("Majority green revenue benefits from energy transition")
    elif green_rev >= 20:
        adjustments += 10.0
        evidence.append("Meaningful green revenue exposure")

    carbon = company.get("carbon_intensity")
    if carbon is not None:
        if carbon >= 500:
            adjustments -= 25.0
            evidence.append("High carbon intensity creates transition risk")
        elif carbon >= 200:
            adjustments -= 10.0
            evidence.append("Moderate carbon intensity creates some transition risk")
        elif carbon <= 50:
            adjustments += 10.0
            evidence.append("Low carbon intensity positions well for transition")

    capex_green = company.get("capex_green_pct")
    if capex_green is not None:
        if capex_green >= 40:
            adjustments += 15.0
            evidence.append("Significant green capex signals transition readiness")
        elif capex_green <= 5:
            adjustments -= 5.0
            evidence.append("Minimal green capex investment")

    score = max(-100.0, min(100.0, base + adjustments))
    direction = "positive" if score > 0 else "negative" if score < 0 else "neutral"

    return {"score": round(score, 2), "direction": direction, "evidence": evidence}


# ── Aggregate Functions ─────────────────────────────────────────────────


_THEME_COMPUTERS = {
    "inflation": compute_inflation_exposure,
    "deflation": lambda c: _deflation_from_inflation(c),
    "growth": compute_growth_exposure,
    "rates": compute_rates_exposure,
    "fx": compute_fx_exposure,
    "commodities": compute_commodity_exposure,
    "energy_transition": compute_energy_transition_exposure,
}


def _deflation_from_inflation(company: dict) -> dict:
    """Deflation exposure is roughly the inverse of inflation exposure."""
    inflation = compute_inflation_exposure(company)
    score = -inflation["score"]
    score = max(-100.0, min(100.0, score))
    direction = "positive" if score > 0 else "negative" if score < 0 else "neutral"
    evidence = ["Deflation exposure derived as inverse of inflation exposure"]
    return {"score": round(score, 2), "direction": direction, "evidence": evidence}


def score_all_themes(company: dict) -> dict[str, dict]:
    """Score a company across all 7 macro themes.

    Parameters
    ----------
    company : dict
        Company financial/sector data.

    Returns
    -------
    dict[str, dict]
        Theme name -> {score, direction, evidence}.
    """
    results = {}
    for theme in MACRO_THEMES:
        computer = _THEME_COMPUTERS[theme]
        results[theme] = computer(company)
    return results


def screen_by_theme(
    companies: list[dict],
    theme: str,
    min_score: float | None = None,
    max_score: float | None = None,
    direction: str | None = None,
) -> list[dict]:
    """Screen a list of companies by their exposure to a given theme.

    Parameters
    ----------
    companies : list[dict]
        Each dict must include fields needed by the relevant theme scorer,
        plus an 'entity_id' or 'ticker' identifier.
    theme : str
        One of MACRO_THEMES.
    min_score : float | None
        Minimum exposure score to include.
    max_score : float | None
        Maximum exposure score to include.
    direction : str | None
        Filter by 'positive', 'negative', or 'neutral'.

    Returns
    -------
    list[dict]
        Matching companies with {company, exposure} sub-dicts.
    """
    if theme not in MACRO_THEMES:
        raise ValueError(f"Unknown theme '{theme}'. Must be one of {MACRO_THEMES}")

    computer = _THEME_COMPUTERS[theme]
    results = []

    for company in companies:
        exposure = computer(company)
        score = exposure["score"]

        if min_score is not None and score < min_score:
            continue
        if max_score is not None and score > max_score:
            continue
        if direction is not None and exposure["direction"] != direction:
            continue

        results.append({
            "company": company,
            "exposure": exposure,
        })

    # Sort by absolute exposure descending
    results.sort(key=lambda x: abs(x["exposure"]["score"]), reverse=True)
    return results
