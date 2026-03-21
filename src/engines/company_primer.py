"""Company Primer Engine.

Assembles data for one-page company summaries and optionally generates
AI narrative. Pure computation functions operate on pre-fetched data dicts.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PrimerData:
    """Assembled primer data."""
    entity_id: str
    entity_name: str | None = None
    business_description: str | None = None
    segments_breakdown: dict | None = None
    competitive_position: str | None = None
    financial_summary: dict | None = None
    valuation_summary: dict | None = None
    ownership_summary: dict | None = None
    key_risks: list[str] = field(default_factory=list)
    recent_developments: list[dict] = field(default_factory=list)
    ai_enabled: bool = False


def compute_financial_summary(data: dict) -> dict:
    """Compute a financial summary from fundamental data.

    Pure computation — always works regardless of AI availability.

    Parameters
    ----------
    data : dict with optional keys:
        - revenue, revenue_growth, ebitda, ebitda_margin,
          net_income, eps, free_cash_flow, total_debt, total_equity

    Returns
    -------
    dict with computed financial metrics.
    """
    summary = {}

    revenue = data.get("revenue")
    if revenue is not None:
        summary["revenue"] = revenue
        revenue_growth = data.get("revenue_growth")
        if revenue_growth is not None:
            summary["revenue_growth_pct"] = round(revenue_growth, 2)

    ebitda = data.get("ebitda")
    if ebitda is not None:
        summary["ebitda"] = ebitda
        if revenue and revenue > 0:
            summary["ebitda_margin_pct"] = round(ebitda / revenue * 100, 2)

    net_income = data.get("net_income")
    if net_income is not None:
        summary["net_income"] = net_income
        if revenue and revenue > 0:
            summary["net_margin_pct"] = round(net_income / revenue * 100, 2)

    eps = data.get("eps")
    if eps is not None:
        summary["eps"] = eps

    fcf = data.get("free_cash_flow")
    if fcf is not None:
        summary["free_cash_flow"] = fcf

    total_debt = data.get("total_debt")
    total_equity = data.get("total_equity")
    if total_debt is not None and total_equity is not None and total_equity > 0:
        summary["debt_to_equity"] = round(total_debt / total_equity, 2)

    return summary


def compute_valuation_summary(data: dict) -> dict:
    """Compute a valuation summary from market/fundamental data.

    Parameters
    ----------
    data : dict with optional keys:
        - market_cap, pe_ratio, ev_ebitda, pb_ratio,
          price_to_sales, dividend_yield

    Returns
    -------
    dict with valuation metrics.
    """
    summary = {}
    for key in ("market_cap", "pe_ratio", "ev_ebitda", "pb_ratio",
                "price_to_sales", "dividend_yield"):
        val = data.get(key)
        if val is not None:
            summary[key] = val
    return summary


def compute_ownership_summary(data: dict) -> dict:
    """Compute ownership summary.

    Parameters
    ----------
    data : dict with optional keys:
        - institutional_pct, insider_pct, top_holders (list of dicts)

    Returns
    -------
    dict with ownership breakdown.
    """
    summary = {}
    inst = data.get("institutional_pct")
    if inst is not None:
        summary["institutional_pct"] = round(inst, 2)

    insider = data.get("insider_pct")
    if insider is not None:
        summary["insider_pct"] = round(insider, 2)

    holders = data.get("top_holders")
    if holders:
        summary["top_holders"] = holders[:5]  # Top 5

    return summary


def extract_key_risks(data: dict) -> list[str]:
    """Extract key risk factors from data.

    Parameters
    ----------
    data : dict with optional keys:
        - debt_to_equity, interest_coverage, revenue_concentration,
          regulatory_risk, litigation_pending, currency_exposure

    Returns
    -------
    list of risk description strings.
    """
    risks = []

    dte = data.get("debt_to_equity")
    if dte is not None and dte > 2.0:
        risks.append(f"High leverage: debt-to-equity ratio of {dte:.1f}x")

    coverage = data.get("interest_coverage")
    if coverage is not None and coverage < 2.0:
        risks.append(f"Tight interest coverage at {coverage:.1f}x")

    concentration = data.get("revenue_concentration")
    if concentration is not None and concentration > 50:
        risks.append(f"Revenue concentration risk: {concentration:.0f}% from top segment")

    if data.get("regulatory_risk"):
        risks.append("Regulatory risk: pending regulatory action")

    if data.get("litigation_pending"):
        risks.append("Litigation risk: material pending litigation")

    if data.get("currency_exposure"):
        risks.append("Currency exposure: significant international revenue")

    return risks


def generate_primer(
    entity_id: str,
    entity_name: str | None,
    financial_data: dict,
    valuation_data: dict,
    ownership_data: dict,
    risk_data: dict,
    recent_events: list[dict] | None = None,
    ai_description: str | None = None,
    ai_competitive: str | None = None,
) -> PrimerData:
    """Generate a company primer from assembled data.

    Parameters
    ----------
    entity_id : Entity UUID string.
    entity_name : Company name.
    financial_data : Data for compute_financial_summary.
    valuation_data : Data for compute_valuation_summary.
    ownership_data : Data for compute_ownership_summary.
    risk_data : Data for extract_key_risks.
    recent_events : List of recent event dicts.
    ai_description : AI-generated business description (None when AI disabled).
    ai_competitive : AI-generated competitive position (None when AI disabled).

    Returns
    -------
    PrimerData with all fields populated.
    """
    return PrimerData(
        entity_id=entity_id,
        entity_name=entity_name,
        business_description=ai_description,
        competitive_position=ai_competitive,
        financial_summary=compute_financial_summary(financial_data),
        valuation_summary=compute_valuation_summary(valuation_data),
        ownership_summary=compute_ownership_summary(ownership_data),
        key_risks=extract_key_risks(risk_data),
        recent_developments=recent_events or [],
        ai_enabled=ai_description is not None,
    )
