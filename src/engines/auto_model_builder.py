"""Automatic Model Builder Engine.

Auto-assembles structured, scored analytical models across five scopes —
ECONOMIC, MARKET, INDUSTRY, CORPORATE, and COMPANY — from pre-fetched data
dicts. Each builder turns raw inputs into a consistent model envelope:
sections (with metrics + a qualitative read), key drivers, explicit
assumptions, a 0–100 composite score, and a rating/summary.

Pure computation — no DB, network, or heavy numeric deps. The router pulls
the underlying data (fundamentals, macro series, ownership, capital
structure, ...) and feeds it here. The five builders compose cleanly with
the platform's existing engines, which can supply the input metrics.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date


SCOPES = ("ECONOMIC", "MARKET", "INDUSTRY", "CORPORATE", "COMPANY")


@dataclass
class ModelSection:
    title: str
    metrics: dict = field(default_factory=dict)
    assessment: str = ""


@dataclass
class AnalyticalModel:
    scope: str
    subject: str | None = None
    as_of: str | None = None
    sections: list[ModelSection] = field(default_factory=list)
    drivers: list[str] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    scores: dict = field(default_factory=dict)
    composite_score: float = 0.0
    rating: str = "NEUTRAL"
    summary: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        return d


# ── Scoring helpers ─────────────────────────────────────────────────────

def _clamp(x: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, x))


def _band(value: float | None, thresholds: list[tuple[float, str]], default: str) -> str:
    """Map a value to a label using ascending (threshold, label) cutoffs."""
    if value is None:
        return default
    for cutoff, label in thresholds:
        if value <= cutoff:
            return label
    return default


def _rating_from_score(score: float) -> str:
    if score >= 80:
        return "STRONG_BUY"
    if score >= 62:
        return "BUY"
    if score >= 45:
        return "NEUTRAL"
    if score >= 30:
        return "SELL"
    return "STRONG_SELL"


def _today() -> str:
    return date.today().isoformat()


# ── ECONOMIC ────────────────────────────────────────────────────────────

def build_economic_model(data: dict, subject: str = "US Economy") -> AnalyticalModel:
    """Macro regime model from growth/inflation/policy/curve inputs.

    Inputs (all optional): gdp_growth (%, YoY), inflation (%, YoY),
    unemployment (%), policy_rate (%), yield_curve_spread (10y-2y, %),
    pmi (index), leading_index_change (%).
    """
    gdp = data.get("gdp_growth")
    infl = data.get("inflation")
    unemp = data.get("unemployment")
    rate = data.get("policy_rate")
    curve = data.get("yield_curve_spread")
    pmi = data.get("pmi")
    lei = data.get("leading_index_change")

    # Recession probability proxy: inverted curve + sub-50 PMI + negative LEI.
    recession_prob = 0.0
    if curve is not None and curve < 0:
        recession_prob += min(abs(curve) * 30, 45)
    if pmi is not None and pmi < 50:
        recession_prob += min((50 - pmi) * 3, 30)
    if lei is not None and lei < 0:
        recession_prob += min(abs(lei) * 10, 25)
    recession_prob = round(_clamp(recession_prob), 1)

    # Growth regime.
    if gdp is None:
        regime = "UNKNOWN"
    elif gdp >= 2.5:
        regime = "EXPANSION"
    elif gdp >= 1.0:
        regime = "SLOWDOWN"
    elif gdp >= 0:
        regime = "STALL"
    else:
        regime = "CONTRACTION"

    policy_stance = "NEUTRAL"
    if rate is not None and infl is not None:
        real_rate = rate - infl
        policy_stance = "RESTRICTIVE" if real_rate > 1.0 else "ACCOMMODATIVE" if real_rate < 0 else "NEUTRAL"

    # Composite (higher = healthier backdrop for risk assets).
    score = 50.0
    if gdp is not None:
        score += _clamp((gdp - 2.0) * 8, -20, 20)
    if infl is not None:
        score -= _clamp(abs(infl - 2.0) * 4, 0, 15)
    score -= recession_prob * 0.3
    if curve is not None:
        score += _clamp(curve * 10, -15, 10)
    score = round(_clamp(score), 1)

    sections = [
        ModelSection(
            "Growth & Activity",
            {"gdp_growth": gdp, "pmi": pmi, "leading_index_change": lei, "unemployment": unemp},
            f"Growth regime: {regime}.",
        ),
        ModelSection(
            "Inflation & Policy",
            {"inflation": infl, "policy_rate": rate, "policy_stance": policy_stance},
            f"Monetary stance is {policy_stance.lower()}.",
        ),
        ModelSection(
            "Yield Curve & Recession Risk",
            {"yield_curve_spread": curve, "recession_probability_pct": recession_prob},
            f"Recession probability ~{recession_prob:.0f}%.",
        ),
    ]
    drivers = []
    if curve is not None and curve < 0:
        drivers.append("Inverted yield curve signals tightening financial conditions")
    if infl is not None and infl > 3:
        drivers.append("Above-target inflation constrains policy easing")
    if gdp is not None and gdp >= 2.5:
        drivers.append("Resilient growth supports earnings backdrop")

    model = AnalyticalModel(
        scope="ECONOMIC",
        subject=subject,
        as_of=data.get("as_of") or _today(),
        sections=sections,
        drivers=drivers or ["Mixed macro signals"],
        assumptions=["Indicators reflect latest available period", "No exogenous shock modeled"],
        scores={"recession_probability_pct": recession_prob, "macro_health": score},
        composite_score=score,
        rating=regime,
        summary=f"{subject}: {regime} regime, {policy_stance.lower()} policy, ~{recession_prob:.0f}% recession risk.",
    )
    return model


# ── MARKET ──────────────────────────────────────────────────────────────

def build_market_model(data: dict, subject: str = "US Equity Market") -> AnalyticalModel:
    """Market regime model from valuation/breadth/volatility/credit inputs.

    Inputs: index_pe, pe_percentile (0–100 vs history), earnings_growth (%),
    breadth_pct (% above 200dma), vix, credit_spread_bps, trend (-1..1).
    """
    pe = data.get("index_pe")
    pe_pct = data.get("pe_percentile")
    eg = data.get("earnings_growth")
    breadth = data.get("breadth_pct")
    vix = data.get("vix")
    spread = data.get("credit_spread_bps")
    trend = data.get("trend")

    valuation_level = _band(
        pe_pct,
        [(20, "CHEAP"), (45, "FAIR"), (70, "ELEVATED"), (90, "EXPENSIVE")],
        "STRETCHED",
    )
    risk_regime = "RISK_ON"
    if (vix is not None and vix > 25) or (spread is not None and spread > 500):
        risk_regime = "RISK_OFF"
    elif (vix is not None and vix > 18) or (spread is not None and spread > 350):
        risk_regime = "CAUTIOUS"

    score = 50.0
    if pe_pct is not None:
        score += _clamp((50 - pe_pct) * 0.4, -20, 20)  # cheaper = better
    if eg is not None:
        score += _clamp(eg * 1.2, -15, 20)
    if breadth is not None:
        score += _clamp((breadth - 50) * 0.3, -15, 15)
    if vix is not None:
        score -= _clamp((vix - 18) * 0.8, -10, 20)
    if trend is not None:
        score += trend * 10
    score = round(_clamp(score), 1)

    sections = [
        ModelSection("Valuation", {"index_pe": pe, "pe_percentile": pe_pct, "valuation_level": valuation_level},
                     f"Valuation is {valuation_level.lower()} vs history."),
        ModelSection("Earnings & Breadth", {"earnings_growth": eg, "breadth_pct": breadth},
                     "Participation and earnings momentum."),
        ModelSection("Risk Conditions", {"vix": vix, "credit_spread_bps": spread, "risk_regime": risk_regime},
                     f"Risk regime: {risk_regime}."),
    ]
    drivers = []
    if valuation_level in ("EXPENSIVE", "STRETCHED"):
        drivers.append("Rich valuations cap upside / raise drawdown risk")
    if risk_regime == "RISK_OFF":
        drivers.append("Stress in volatility/credit favors defensive posture")
    if eg is not None and eg > 8:
        drivers.append("Strong earnings growth underpins the tape")

    return AnalyticalModel(
        scope="MARKET",
        subject=subject,
        as_of=data.get("as_of") or _today(),
        sections=sections,
        drivers=drivers or ["Balanced market signals"],
        assumptions=["Percentiles measured vs trailing history", "No regime-change shock modeled"],
        scores={"market_score": score},
        composite_score=score,
        rating=_rating_from_score(score),
        summary=f"{subject}: {valuation_level.lower()} valuation, {risk_regime} regime, score {score:.0f}/100.",
    )


# ── INDUSTRY ────────────────────────────────────────────────────────────

def build_industry_model(data: dict, subject: str = "Industry") -> AnalyticalModel:
    """Industry model from growth/margin/cycle/concentration inputs.

    Inputs: revenue_growth (%), margin_trend (-1..1), capex_cycle
    (EARLY/MID/LATE), hhi (0–10000 concentration), demand_score (0–100),
    pricing_power (-1..1).
    """
    rg = data.get("revenue_growth")
    margin_trend = data.get("margin_trend")
    capex_cycle = (data.get("capex_cycle") or "").upper() or None
    hhi = data.get("hhi")
    demand = data.get("demand_score")
    pricing = data.get("pricing_power")

    if rg is None:
        cycle_stage = "UNKNOWN"
    elif rg >= 10:
        cycle_stage = "EXPANSION"
    elif rg >= 3:
        cycle_stage = "MATURE_GROWTH"
    elif rg >= 0:
        cycle_stage = "MATURE"
    else:
        cycle_stage = "DECLINE"

    concentration = _band(hhi, [(1500, "FRAGMENTED"), (2500, "MODERATE")], "CONCENTRATED")

    score = 50.0
    if rg is not None:
        score += _clamp(rg * 1.5, -20, 25)
    if margin_trend is not None:
        score += margin_trend * 12
    if demand is not None:
        score += _clamp((demand - 50) * 0.2, -10, 10)
    if pricing is not None:
        score += pricing * 10
    score = round(_clamp(score), 1)

    sections = [
        ModelSection("Growth & Cycle", {"revenue_growth": rg, "capex_cycle": capex_cycle, "cycle_stage": cycle_stage},
                     f"Industry cycle: {cycle_stage}."),
        ModelSection("Profitability", {"margin_trend": margin_trend, "pricing_power": pricing},
                     "Margin and pricing dynamics."),
        ModelSection("Structure", {"hhi": hhi, "concentration": concentration, "demand_score": demand},
                     f"Market structure is {concentration.lower()}."),
    ]
    drivers = []
    if concentration == "CONCENTRATED":
        drivers.append("Concentrated structure supports pricing/returns for incumbents")
    if margin_trend is not None and margin_trend < 0:
        drivers.append("Margin compression headwind")
    if cycle_stage == "EXPANSION":
        drivers.append("Industry in expansion phase")

    return AnalyticalModel(
        scope="INDUSTRY",
        subject=subject,
        as_of=data.get("as_of") or _today(),
        sections=sections,
        drivers=drivers or ["Stable industry conditions"],
        assumptions=["Single-industry view", "Cross-industry substitution not modeled"],
        scores={"industry_score": score},
        composite_score=score,
        rating=_rating_from_score(score),
        summary=f"{subject}: {cycle_stage} cycle, {concentration.lower()} structure, score {score:.0f}/100.",
    )


# ── CORPORATE (capital structure / credit) ──────────────────────────────

def build_corporate_model(data: dict, subject: str = "Issuer") -> AnalyticalModel:
    """Corporate credit/financial-risk model from leverage & liquidity inputs.

    Inputs: net_debt_to_ebitda, interest_coverage, debt_to_capital (%),
    altman_z, near_term_maturities_pct (% of debt due <=2y), cash_to_debt,
    fcf_margin (%).
    """
    lev = data.get("net_debt_to_ebitda")
    cov = data.get("interest_coverage")
    dtc = data.get("debt_to_capital")
    z = data.get("altman_z")
    wall = data.get("near_term_maturities_pct")
    cash_to_debt = data.get("cash_to_debt")
    fcf = data.get("fcf_margin")

    credit_quality = _band(lev, [(1.5, "STRONG"), (3.0, "ADEQUATE"), (4.5, "LEVERED")], "DISTRESSED")
    if z is not None and z < 1.8:
        credit_quality = "DISTRESSED"

    score = 60.0
    if lev is not None:
        score -= _clamp((lev - 2.0) * 8, -15, 35)
    if cov is not None:
        score += _clamp((cov - 4.0) * 3, -20, 15)
    if z is not None:
        score += _clamp((z - 3.0) * 5, -20, 15)
    if wall is not None:
        score -= _clamp(wall * 0.2, 0, 15)
    score = round(_clamp(score), 1)

    sections = [
        ModelSection("Leverage", {"net_debt_to_ebitda": lev, "debt_to_capital": dtc},
                     f"Credit quality: {credit_quality}."),
        ModelSection("Coverage & Solvency", {"interest_coverage": cov, "altman_z": z},
                     "Ability to service and withstand stress."),
        ModelSection("Liquidity & Maturities", {"cash_to_debt": cash_to_debt,
                                                 "near_term_maturities_pct": wall, "fcf_margin": fcf},
                     "Refinancing and liquidity profile."),
    ]
    drivers = []
    if lev is not None and lev > 4:
        drivers.append("Elevated leverage raises financial risk")
    if wall is not None and wall > 30:
        drivers.append("Sizable near-term maturity wall — refinancing risk")
    if cov is not None and cov > 8:
        drivers.append("Comfortable interest coverage")

    return AnalyticalModel(
        scope="CORPORATE",
        subject=subject,
        as_of=data.get("as_of") or _today(),
        sections=sections,
        drivers=drivers or ["Balanced credit profile"],
        assumptions=["Point-in-time balance sheet", "No covenant detail modeled"],
        scores={"credit_score": score},
        composite_score=score,
        rating=credit_quality,
        summary=f"{subject}: {credit_quality} credit, {lev if lev is not None else 'n/a'}x net leverage, score {score:.0f}/100.",
    )


# ── COMPANY (full equity model) ─────────────────────────────────────────

def build_company_model(data: dict, subject: str = "Company") -> AnalyticalModel:
    """Full company model: financials + valuation + quality + ownership + risk.

    Inputs (optional): revenue_growth, ebitda_margin, net_income, fcf_margin,
    roe, dcf_upside_pct, pe_vs_peers (-1..1; negative = cheaper), piotroski
    (0–9), altman_z, smart_money_signal ('BULLISH'/'BEARISH'/'NEUTRAL'),
    insider_buy_ratio (0–1), key_risks (list[str]).
    """
    rg = data.get("revenue_growth")
    margin = data.get("ebitda_margin")
    fcf = data.get("fcf_margin")
    roe = data.get("roe")
    dcf_up = data.get("dcf_upside_pct")
    pe_vs_peers = data.get("pe_vs_peers")
    piotroski = data.get("piotroski")
    z = data.get("altman_z")
    smart = (data.get("smart_money_signal") or "NEUTRAL").upper()
    insider_ratio = data.get("insider_buy_ratio")

    # Sub-scores (0–100 each).
    growth_score = _clamp(50 + (rg or 0) * 1.5, 0, 100)
    quality_score = 50.0
    if margin is not None:
        quality_score += _clamp((margin - 20) * 0.8, -15, 20)
    if roe is not None:
        quality_score += _clamp((roe - 12) * 0.8, -15, 20)
    if piotroski is not None:
        quality_score += (piotroski - 4.5) * 4
    quality_score = _clamp(quality_score)

    value_score = 50.0
    if dcf_up is not None:
        value_score += _clamp(dcf_up * 0.6, -25, 30)
    if pe_vs_peers is not None:
        value_score -= pe_vs_peers * 15  # cheaper vs peers (negative) raises score
    value_score = _clamp(value_score)

    safety_score = 60.0
    if z is not None:
        safety_score += _clamp((z - 3.0) * 6, -30, 20)
    safety_score = _clamp(safety_score)

    sentiment_score = 50.0
    if smart == "BULLISH":
        sentiment_score += 15
    elif smart == "BEARISH":
        sentiment_score -= 15
    if insider_ratio is not None:
        sentiment_score += (insider_ratio - 0.5) * 30
    sentiment_score = _clamp(sentiment_score)

    weights = {"growth": 0.22, "quality": 0.26, "value": 0.26, "safety": 0.16, "sentiment": 0.10}
    composite = round(
        growth_score * weights["growth"]
        + quality_score * weights["quality"]
        + value_score * weights["value"]
        + safety_score * weights["safety"]
        + sentiment_score * weights["sentiment"],
        1,
    )
    rating = _rating_from_score(composite)

    sections = [
        ModelSection("Financial Profile", {"revenue_growth": rg, "ebitda_margin": margin,
                                            "fcf_margin": fcf, "roe": roe},
                     "Top-line growth and profitability."),
        ModelSection("Valuation", {"dcf_upside_pct": dcf_up, "pe_vs_peers": pe_vs_peers,
                                   "value_score": round(value_score, 1)},
                     "Intrinsic value and relative multiples."),
        ModelSection("Quality & Safety", {"piotroski": piotroski, "altman_z": z,
                                          "quality_score": round(quality_score, 1),
                                          "safety_score": round(safety_score, 1)},
                     "Fundamental quality and bankruptcy distance."),
        ModelSection("Ownership Sentiment", {"smart_money_signal": smart,
                                             "insider_buy_ratio": insider_ratio,
                                             "sentiment_score": round(sentiment_score, 1)},
                     "Smart-money and insider positioning."),
    ]

    drivers = []
    if dcf_up is not None and dcf_up > 20:
        drivers.append(f"DCF implies ~{dcf_up:.0f}% upside")
    if smart == "BULLISH":
        drivers.append("Smart-money flow is supportive")
    if z is not None and z < 1.8:
        drivers.append("Altman-Z in distress zone — elevated solvency risk")
    if piotroski is not None and piotroski >= 7:
        drivers.append("High Piotroski F-score signals improving fundamentals")

    return AnalyticalModel(
        scope="COMPANY",
        subject=subject,
        as_of=data.get("as_of") or _today(),
        sections=sections,
        drivers=drivers or ["Mixed company signals"],
        assumptions=[
            "DCF/peer inputs supplied by valuation engines",
            "Sub-scores weighted growth/quality/value/safety/sentiment",
        ],
        scores={
            "growth": round(growth_score, 1),
            "quality": round(quality_score, 1),
            "value": round(value_score, 1),
            "safety": round(safety_score, 1),
            "sentiment": round(sentiment_score, 1),
        },
        composite_score=composite,
        rating=rating,
        summary=f"{subject}: {rating} (composite {composite:.0f}/100).",
    )


# ── Dispatcher ──────────────────────────────────────────────────────────

_BUILDERS = {
    "ECONOMIC": build_economic_model,
    "MARKET": build_market_model,
    "INDUSTRY": build_industry_model,
    "CORPORATE": build_corporate_model,
    "COMPANY": build_company_model,
}


def build_model(scope: str, data: dict, subject: str | None = None) -> AnalyticalModel:
    """Dispatch to the appropriate builder for ``scope`` (case-insensitive)."""
    key = (scope or "").upper()
    if key not in _BUILDERS:
        raise ValueError(f"Unknown model scope '{scope}'. Valid: {', '.join(SCOPES)}")
    builder = _BUILDERS[key]
    if subject is not None:
        return builder(data, subject)
    return builder(data)
