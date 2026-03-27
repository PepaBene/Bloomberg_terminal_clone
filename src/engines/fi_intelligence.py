"""Pillar 3 Phase 3C — Part 15: FI Intelligence Engine.

Pure computation engine for fixed-income market intelligence, yield curve
analysis, credit regime classification, and issuer credit profiling.

No database access — all functions accept and return plain data.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from statistics import mean


# ── Dataclasses ────────────────────────────────────────────────────────────


@dataclass
class YieldCurveBriefing:
    curve_shape: str  # STEEP/NORMAL/FLAT/INVERTED
    spread_2s10s_bps: float
    spread_3m10y_bps: float | None
    spread_percentile_5y: float | None
    daily_change_10y_bps: float | None
    equity_implications: list[str]
    key_metrics: dict


@dataclass
class CreditMarketBriefing:
    ig_oas_bps: float
    hy_oas_bps: float
    ig_change_1w: float
    hy_change_1w: float
    credit_regime: str  # RISK_ON/NORMAL/RISK_OFF/STRESS
    ig_percentile_1y: float | None
    hy_percentile_1y: float | None
    fallen_angels: list[dict]
    rising_stars: list[dict]


@dataclass
class IssuanceIntelligence:
    issue_date: str
    issuer: str
    size_mm: float
    coupon: float
    spread_vs_existing: float | None  # tighter or wider than existing bonds
    use_of_proceeds: str
    demand_assessment: str  # STRONG/NORMAL/WEAK
    implications: list[str]


@dataclass
class IssuerCreditProfile:
    entity_id: str
    total_debt_outstanding_mm: float | None
    weighted_avg_ytm: float | None
    weighted_avg_spread_bps: float | None
    credit_rating: str | None
    credit_momentum: str | None
    market_cost_of_debt: float | None
    accounting_cost_of_debt: float | None
    cost_gap_bps: float | None
    maturity_wall: list[dict] = field(default_factory=list)  # [{year, amount_mm}]


# ── Curve Shape ────────────────────────────────────────────────────────────


def classify_curve_shape(spread_2s10s: float) -> str:
    """Classify yield curve shape based on 2s10s spread.

    Parameters
    ----------
    spread_2s10s : float
        2-year to 10-year Treasury spread in basis points.

    Returns
    -------
    str
        STEEP if >100, NORMAL if >20, FLAT if >-20, else INVERTED.
    """
    if spread_2s10s > 100:
        return "STEEP"
    if spread_2s10s > 20:
        return "NORMAL"
    if spread_2s10s > -20:
        return "FLAT"
    return "INVERTED"


# ── Spread Percentile ──────────────────────────────────────────────────────


def compute_spread_percentile(current: float, history: list[float]) -> float:
    """Compute the percentile rank of the current spread within history.

    Parameters
    ----------
    current : float
        Current spread value.
    history : list[float]
        Historical spread values.

    Returns
    -------
    float
        Percentile 0-100. Returns 50.0 if history is empty.
    """
    if not history:
        return 50.0
    count_below = sum(1 for h in history if h <= current)
    return round((count_below / len(history)) * 100, 2)


# ── Auction Assessment ─────────────────────────────────────────────────────


def assess_auction_result(bid_to_cover: float, avg_12m: float) -> str:
    """Assess Treasury auction demand relative to 12-month average.

    Parameters
    ----------
    bid_to_cover : float
        Bid-to-cover ratio for the auction.
    avg_12m : float
        Trailing 12-month average bid-to-cover.

    Returns
    -------
    str
        STRONG if >avg*1.2, WEAK if <avg*0.8, else NORMAL.
    """
    if avg_12m <= 0:
        return "NORMAL"
    if bid_to_cover > avg_12m * 1.2:
        return "STRONG"
    if bid_to_cover < avg_12m * 0.8:
        return "WEAK"
    return "NORMAL"


# ── Equity Implications ───────────────────────────────────────────────────


def generate_equity_implications(
    curve_shape: str, rate_change: float | None
) -> list[str]:
    """Generate equity sector implications based on curve shape and rate moves.

    Parameters
    ----------
    curve_shape : str
        STEEP/NORMAL/FLAT/INVERTED.
    rate_change : float | None
        Daily change in 10-year yield (bps). None if unavailable.

    Returns
    -------
    list[str]
        List of sector/market implications.
    """
    implications: list[str] = []

    if curve_shape == "STEEP":
        implications.append("Steepening curve favors financials (wider NIM)")
        implications.append("Growth/duration-sensitive sectors may face headwinds")
    elif curve_shape == "INVERTED":
        implications.append("Inverted curve signals recession risk — defensive positioning warranted")
        implications.append("Bank margins under pressure from flat/negative NIM")
    elif curve_shape == "FLAT":
        implications.append("Flat curve suggests economic uncertainty")
        implications.append("Rate-sensitive sectors (REITs, utilities) face mixed signals")
    else:  # NORMAL
        implications.append("Normal curve supports broad equity allocation")

    if rate_change is not None:
        if rate_change > 10:
            implications.append("Rising rates pressure high-duration equities (tech, growth)")
            implications.append("Value and financials likely to outperform")
        elif rate_change < -10:
            implications.append("Falling rates support growth and duration-sensitive equities")
            implications.append("Bond proxies (REITs, utilities) likely to rally")

    return implications


# ── Yield Curve Briefing ──────────────────────────────────────────────────


def generate_yield_curve_briefing(
    curve_data: dict, prior_data: dict | None = None
) -> YieldCurveBriefing:
    """Generate a comprehensive yield curve briefing.

    Parameters
    ----------
    curve_data : dict
        Keys: spread_2s10s_bps, spread_3m10y_bps (optional),
              yield_10y (optional), history_5y (optional list[float]).
    prior_data : dict | None
        Previous day curve_data for computing changes.

    Returns
    -------
    YieldCurveBriefing
    """
    spread_2s10s = curve_data.get("spread_2s10s_bps", 0.0)
    spread_3m10y = curve_data.get("spread_3m10y_bps")
    curve_shape = classify_curve_shape(spread_2s10s)

    # Percentile
    history = curve_data.get("history_5y", [])
    percentile = compute_spread_percentile(spread_2s10s, history) if history else None

    # Daily change
    daily_change = None
    if prior_data is not None:
        prior_10y = prior_data.get("yield_10y")
        current_10y = curve_data.get("yield_10y")
        if prior_10y is not None and current_10y is not None:
            daily_change = round((current_10y - prior_10y) * 100, 2)  # to bps

    equity_implications = generate_equity_implications(curve_shape, daily_change)

    key_metrics = {
        "spread_2s10s_bps": spread_2s10s,
        "curve_shape": curve_shape,
    }
    if spread_3m10y is not None:
        key_metrics["spread_3m10y_bps"] = spread_3m10y
    if daily_change is not None:
        key_metrics["daily_change_10y_bps"] = daily_change

    return YieldCurveBriefing(
        curve_shape=curve_shape,
        spread_2s10s_bps=spread_2s10s,
        spread_3m10y_bps=spread_3m10y,
        spread_percentile_5y=percentile,
        daily_change_10y_bps=daily_change,
        equity_implications=equity_implications,
        key_metrics=key_metrics,
    )


# ── Credit Regime ─────────────────────────────────────────────────────────


def classify_credit_regime(ig_oas: float, hy_oas: float) -> str:
    """Classify current credit market regime based on IG OAS.

    Parameters
    ----------
    ig_oas : float
        Investment grade OAS in basis points.
    hy_oas : float
        High yield OAS in basis points (used for context, not thresholds).

    Returns
    -------
    str
        RISK_ON if IG<80, NORMAL if IG<150, RISK_OFF if IG<250, else STRESS.
    """
    if ig_oas < 80:
        return "RISK_ON"
    if ig_oas < 150:
        return "NORMAL"
    if ig_oas < 250:
        return "RISK_OFF"
    return "STRESS"


# ── Credit Market Briefing ────────────────────────────────────────────────


def generate_credit_market_briefing(
    ig_oas: float,
    hy_oas: float,
    prior_ig: float,
    prior_hy: float,
    history: list[dict] | None = None,
    events: list[dict] | None = None,
) -> CreditMarketBriefing:
    """Generate a credit market briefing with regime classification.

    Parameters
    ----------
    ig_oas : float
        Current IG OAS (bps).
    hy_oas : float
        Current HY OAS (bps).
    prior_ig : float
        Prior-week IG OAS (bps).
    prior_hy : float
        Prior-week HY OAS (bps).
    history : list[dict] | None
        Historical OAS observations: [{ig_oas, hy_oas}].
    events : list[dict] | None
        Rating migration events: [{entity, from_rating, to_rating, type}].

    Returns
    -------
    CreditMarketBriefing
    """
    ig_change = round(ig_oas - prior_ig, 2)
    hy_change = round(hy_oas - prior_hy, 2)
    regime = classify_credit_regime(ig_oas, hy_oas)

    # Percentiles
    ig_percentile = None
    hy_percentile = None
    if history:
        ig_vals = [h.get("ig_oas", 0.0) for h in history]
        hy_vals = [h.get("hy_oas", 0.0) for h in history]
        if ig_vals:
            ig_percentile = compute_spread_percentile(ig_oas, ig_vals)
        if hy_vals:
            hy_percentile = compute_spread_percentile(hy_oas, hy_vals)

    # Rating migrations
    fallen_angels: list[dict] = []
    rising_stars: list[dict] = []
    if events:
        for ev in events:
            ev_type = ev.get("type", "")
            if ev_type == "fallen_angel":
                fallen_angels.append(ev)
            elif ev_type == "rising_star":
                rising_stars.append(ev)

    return CreditMarketBriefing(
        ig_oas_bps=ig_oas,
        hy_oas_bps=hy_oas,
        ig_change_1w=ig_change,
        hy_change_1w=hy_change,
        credit_regime=regime,
        ig_percentile_1y=ig_percentile,
        hy_percentile_1y=hy_percentile,
        fallen_angels=fallen_angels,
        rising_stars=rising_stars,
    )


# ── New Issuance Analysis ─────────────────────────────────────────────────


def analyze_new_issuance(
    issue_data: dict, existing_bonds: list[dict] | None = None
) -> IssuanceIntelligence:
    """Analyze a new bond issuance relative to existing curve.

    Parameters
    ----------
    issue_data : dict
        Keys: issue_date, issuer, size_mm, coupon, spread_at_issue_bps,
              initial_talk_bps, use_of_proceeds, bid_to_cover (optional),
              avg_12m_btc (optional).
    existing_bonds : list[dict] | None
        Existing bonds of same issuer: [{spread_bps, maturity_date}].

    Returns
    -------
    IssuanceIntelligence
    """
    spread_at_issue = issue_data.get("spread_at_issue_bps", 0.0)
    initial_talk = issue_data.get("initial_talk_bps")

    # Spread vs existing
    spread_vs_existing = None
    if existing_bonds:
        existing_spreads = [b.get("spread_bps", 0.0) for b in existing_bonds if b.get("spread_bps") is not None]
        if existing_spreads:
            avg_existing = mean(existing_spreads)
            spread_vs_existing = round(spread_at_issue - avg_existing, 2)

    # Demand assessment
    btc = issue_data.get("bid_to_cover")
    avg_btc = issue_data.get("avg_12m_btc")
    if btc is not None and avg_btc is not None and avg_btc > 0:
        demand = assess_auction_result(btc, avg_btc)
    elif initial_talk is not None and spread_at_issue < initial_talk:
        # Priced tighter than initial talk → good demand
        demand = "STRONG"
    elif initial_talk is not None and spread_at_issue > initial_talk:
        demand = "WEAK"
    else:
        demand = "NORMAL"

    # Implications
    implications: list[str] = []
    if spread_vs_existing is not None:
        if spread_vs_existing < -10:
            implications.append("New issue priced significantly tighter than existing curve — strong demand signal")
        elif spread_vs_existing > 10:
            implications.append("New issue priced wider than existing curve — market demands concession")

    use = issue_data.get("use_of_proceeds", "GENERAL")
    if use and use.upper() in ("ACQUISITION", "M&A"):
        implications.append("Acquisition financing may increase leverage")
    elif use and use.upper() == "REFINANCING":
        implications.append("Refinancing extends maturity profile — credit positive")

    size_mm = issue_data.get("size_mm", 0.0)
    if size_mm >= 1000:
        implications.append("Large benchmark deal increases market presence")

    return IssuanceIntelligence(
        issue_date=issue_data.get("issue_date", ""),
        issuer=issue_data.get("issuer", ""),
        size_mm=size_mm,
        coupon=issue_data.get("coupon", 0.0),
        spread_vs_existing=spread_vs_existing,
        use_of_proceeds=use,
        demand_assessment=demand,
        implications=implications,
    )


# ── Weekly Issuance Volume ────────────────────────────────────────────────


def compute_weekly_issuance_volume(issues: list[dict]) -> dict:
    """Aggregate weekly issuance volume by rating category.

    Parameters
    ----------
    issues : list[dict]
        Each dict: {size_mm, rating, use_of_proceeds}.

    Returns
    -------
    dict
        {ig_volume, hy_volume, total, refinancing_pct, acquisition_pct}
    """
    ig_volume = 0.0
    hy_volume = 0.0
    refinancing_count = 0
    acquisition_count = 0
    total_count = len(issues)

    ig_ratings = {"AAA", "AA+", "AA", "AA-", "A+", "A", "A-", "BBB+", "BBB", "BBB-"}

    for issue in issues:
        size = issue.get("size_mm", 0.0)
        rating = issue.get("rating", "")
        use = (issue.get("use_of_proceeds") or "").upper()

        if rating in ig_ratings:
            ig_volume += size
        else:
            hy_volume += size

        if use == "REFINANCING":
            refinancing_count += 1
        elif use in ("ACQUISITION", "M&A"):
            acquisition_count += 1

    total = ig_volume + hy_volume
    refinancing_pct = round((refinancing_count / total_count) * 100, 2) if total_count else 0.0
    acquisition_pct = round((acquisition_count / total_count) * 100, 2) if total_count else 0.0

    return {
        "ig_volume": round(ig_volume, 2),
        "hy_volume": round(hy_volume, 2),
        "total": round(total, 2),
        "refinancing_pct": refinancing_pct,
        "acquisition_pct": acquisition_pct,
    }


# ── Issuer Credit Profile ────────────────────────────────────────────────


def build_issuer_credit_profile(
    bonds: list[dict],
    ratings: list[dict] | None = None,
    financials: dict | None = None,
) -> IssuerCreditProfile:
    """Build an issuer-level credit profile from bond and financial data.

    Parameters
    ----------
    bonds : list[dict]
        Each: {amount_mm, ytm, spread_bps, maturity_year, coupon}.
    ratings : list[dict] | None
        [{agency, rating, outlook, momentum}].
    financials : dict | None
        {interest_expense, total_debt, accounting_cost_of_debt}.

    Returns
    -------
    IssuerCreditProfile
    """
    # Total debt and weighted averages
    total_debt = 0.0
    weighted_ytm_sum = 0.0
    weighted_spread_sum = 0.0
    maturity_buckets: dict[int, float] = {}

    for bond in bonds:
        amt = bond.get("amount_mm", 0.0)
        total_debt += amt
        ytm = bond.get("ytm")
        if ytm is not None:
            weighted_ytm_sum += ytm * amt
        spread = bond.get("spread_bps")
        if spread is not None:
            weighted_spread_sum += spread * amt
        mat_year = bond.get("maturity_year")
        if mat_year is not None:
            maturity_buckets[mat_year] = maturity_buckets.get(mat_year, 0.0) + amt

    weighted_avg_ytm = round(weighted_ytm_sum / total_debt, 4) if total_debt > 0 else None
    weighted_avg_spread = round(weighted_spread_sum / total_debt, 2) if total_debt > 0 else None

    # Credit rating and momentum
    credit_rating = None
    credit_momentum = None
    if ratings:
        # Use first rating as representative
        credit_rating = ratings[0].get("rating")
        credit_momentum = ratings[0].get("momentum")

    # Market vs accounting cost of debt
    market_cost = weighted_avg_ytm
    accounting_cost = None
    cost_gap = None
    if financials:
        accounting_cost = financials.get("accounting_cost_of_debt")
        if market_cost is not None and accounting_cost is not None:
            cost_gap = round((market_cost - accounting_cost) * 10000, 2)  # to bps

    # Maturity wall
    maturity_wall = sorted(
        [{"year": y, "amount_mm": round(a, 2)} for y, a in maturity_buckets.items()],
        key=lambda x: x["year"],
    )

    return IssuerCreditProfile(
        entity_id="",
        total_debt_outstanding_mm=round(total_debt, 2) if total_debt > 0 else None,
        weighted_avg_ytm=weighted_avg_ytm,
        weighted_avg_spread_bps=weighted_avg_spread,
        credit_rating=credit_rating,
        credit_momentum=credit_momentum,
        market_cost_of_debt=market_cost,
        accounting_cost_of_debt=accounting_cost,
        cost_gap_bps=cost_gap,
        maturity_wall=maturity_wall,
    )
