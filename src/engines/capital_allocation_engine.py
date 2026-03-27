"""Pillar 3 Phase 2 — Part 7b: Capital Allocation Analysis Engine.

Pure computation engine for assessing capital allocation quality:
FCF conversion, CapEx discipline, working capital, M&A track record,
buyback effectiveness, dividend sustainability.

No database access — all functions accept and return plain data.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field


# ── Dataclasses ───────────────────────────────────────────────────────────


@dataclass
class FCFConversion:
    """FCF conversion quality."""

    ebitda_to_fcf_ratio: float | None = None
    is_red_flag: bool = False  # < 50% conversion
    gap_decomposition: dict = field(default_factory=dict)


@dataclass
class CapExClassification:
    """CapEx breakdown into maintenance vs growth."""

    total_capex: float | None = None
    maintenance_capex: float | None = None  # ≈ depreciation
    growth_capex: float | None = None  # total - maintenance
    growth_capex_revenue_pct: float | None = None
    maintenance_capex_revenue_pct: float | None = None


@dataclass
class WorkingCapitalDiscipline:
    """Working capital management metrics."""

    ccc: float | None = None  # Cash Conversion Cycle
    dio: float | None = None  # Days Inventory Outstanding
    dso: float | None = None  # Days Sales Outstanding
    dpo: float | None = None  # Days Payable Outstanding
    ccc_trend: str = "UNKNOWN"  # IMPROVING/STABLE/DETERIORATING


@dataclass
class MADiscipline:
    """M&A discipline assessment."""

    acquisition_count: int = 0
    serial_acquirer: bool = False  # >3 significant deals in 3 years
    goodwill_assets_ratio: float | None = None
    goodwill_trend: str = "UNKNOWN"  # GROWING/STABLE/DECLINING
    impairment_count: int = 0
    post_acquisition_roic_impact: str = "UNKNOWN"  # IMPROVED/STABLE/DECLINED


@dataclass
class BuybackEffectiveness:
    """Share buyback effectiveness."""

    shares_outstanding_trend: str = "UNKNOWN"  # DECREASING/STABLE/INCREASING
    shares_5y_change_pct: float | None = None
    avg_repurchase_price: float | None = None
    current_price: float | None = None
    repurchase_vs_current: str = "UNKNOWN"  # GOOD/NEUTRAL/BAD
    buyback_yield: float | None = None


@dataclass
class DividendSustainability:
    """Dividend sustainability assessment."""

    eps_payout_ratio: float | None = None
    fcf_payout_ratio: float | None = None
    fcf_coverage: float | None = None  # FCF / dividends paid
    consecutive_growth_years: int | None = None
    is_sustainable: bool = True


@dataclass
class CapitalAllocationResult:
    """Complete capital allocation assessment."""

    fcf_conversion: FCFConversion = field(default_factory=FCFConversion)
    capex: CapExClassification = field(default_factory=CapExClassification)
    working_capital: WorkingCapitalDiscipline = field(default_factory=WorkingCapitalDiscipline)
    ma_discipline: MADiscipline = field(default_factory=MADiscipline)
    buybacks: BuybackEffectiveness = field(default_factory=BuybackEffectiveness)
    dividends: DividendSustainability = field(default_factory=DividendSustainability)
    overall_score: float = 50.0  # 0-100


# ── Core Functions ────────────────────────────────────────────────────────


def compute_fcf_conversion(
    ebitda: float | None,
    fcf: float | None,
    capex: float | None = None,
    working_capital_change: float | None = None,
) -> FCFConversion:
    """Compute FCF conversion quality. < 50% conversion is a red flag."""
    if ebitda is None or ebitda <= 0 or fcf is None:
        return FCFConversion()

    ratio = fcf / ebitda
    gap_decomp = {}
    if capex is not None:
        gap_decomp["capex_pct_of_ebitda"] = round(abs(capex) / ebitda, 4)
    if working_capital_change is not None:
        gap_decomp["wc_change_pct_of_ebitda"] = round(working_capital_change / ebitda, 4)

    return FCFConversion(
        ebitda_to_fcf_ratio=round(ratio, 4),
        is_red_flag=ratio < 0.50,
        gap_decomposition=gap_decomp,
    )


def classify_capex(
    total_capex: float | None,
    depreciation: float | None,
    revenue: float | None = None,
) -> CapExClassification:
    """Classify CapEx into maintenance vs growth."""
    if total_capex is None:
        return CapExClassification()

    capex_abs = abs(total_capex)
    maintenance = abs(depreciation) if depreciation else 0.0
    growth = max(capex_abs - maintenance, 0.0)

    growth_rev_pct = None
    maint_rev_pct = None
    if revenue and revenue > 0:
        growth_rev_pct = round(growth / revenue, 4)
        maint_rev_pct = round(maintenance / revenue, 4)

    return CapExClassification(
        total_capex=capex_abs,
        maintenance_capex=round(maintenance, 2),
        growth_capex=round(growth, 2),
        growth_capex_revenue_pct=growth_rev_pct,
        maintenance_capex_revenue_pct=maint_rev_pct,
    )


def compute_working_capital_discipline(
    receivables: float | None,
    inventory: float | None,
    payables: float | None,
    revenue: float | None,
    cogs: float | None,
    history: list[dict] | None = None,
) -> WorkingCapitalDiscipline:
    """Compute working capital metrics: CCC, DIO, DSO, DPO."""
    dso = None
    dio = None
    dpo = None
    ccc = None

    if receivables is not None and revenue and revenue > 0:
        dso = round((receivables / revenue) * 365, 1)

    if inventory is not None and cogs and cogs > 0:
        dio = round((inventory / abs(cogs)) * 365, 1)

    if payables is not None and cogs and cogs > 0:
        dpo = round((payables / abs(cogs)) * 365, 1)

    if dso is not None and dio is not None and dpo is not None:
        ccc = round(dso + dio - dpo, 1)

    # Trend from history
    trend = "UNKNOWN"
    if history and len(history) >= 2:
        ccc_values = [h.get("ccc") for h in history if h.get("ccc") is not None]
        if len(ccc_values) >= 2:
            first = statistics.mean(ccc_values[: len(ccc_values) // 2])
            second = statistics.mean(ccc_values[len(ccc_values) // 2 :])
            diff = second - first
            if diff < -3:
                trend = "IMPROVING"
            elif diff > 3:
                trend = "DETERIORATING"
            else:
                trend = "STABLE"

    return WorkingCapitalDiscipline(ccc=ccc, dio=dio, dso=dso, dpo=dpo, ccc_trend=trend)


def assess_ma_discipline(
    acquisitions: list[dict],
    goodwill_history: list[float] | None = None,
    total_assets_history: list[float] | None = None,
    roic_history: list[dict] | None = None,
) -> MADiscipline:
    """Assess M&A discipline from acquisition history.

    Parameters
    ----------
    acquisitions : list[dict]
        Each: {date, value, is_significant, had_impairment}
    """
    count = len(acquisitions)

    # Serial acquirer: >3 significant in 3 years
    significant = [a for a in acquisitions if a.get("is_significant", False)]
    serial = len(significant) > 3

    # Goodwill/Assets trend
    gw_ratio = None
    gw_trend = "UNKNOWN"
    if goodwill_history and total_assets_history and len(goodwill_history) == len(total_assets_history):
        ratios = []
        for gw, ta in zip(goodwill_history, total_assets_history):
            if ta and ta > 0:
                ratios.append(gw / ta)
        if ratios:
            gw_ratio = round(ratios[-1], 4)
            if len(ratios) >= 2:
                first = statistics.mean(ratios[: len(ratios) // 2])
                second = statistics.mean(ratios[len(ratios) // 2 :])
                if second > first + 0.02:
                    gw_trend = "GROWING"
                elif second < first - 0.02:
                    gw_trend = "DECLINING"
                else:
                    gw_trend = "STABLE"

    impairments = sum(1 for a in acquisitions if a.get("had_impairment", False))

    return MADiscipline(
        acquisition_count=count,
        serial_acquirer=serial,
        goodwill_assets_ratio=gw_ratio,
        goodwill_trend=gw_trend,
        impairment_count=impairments,
    )


def assess_buyback_effectiveness(
    shares_history: list[float] | None,
    avg_repurchase_price: float | None = None,
    current_price: float | None = None,
    buyback_amount: float | None = None,
    market_cap: float | None = None,
) -> BuybackEffectiveness:
    """Assess share buyback effectiveness."""
    trend = "UNKNOWN"
    change_pct = None

    if shares_history and len(shares_history) >= 2:
        first = shares_history[0]
        last = shares_history[-1]
        if first > 0:
            change_pct = round((last - first) / first * 100, 2)
            if change_pct < -2:
                trend = "DECREASING"
            elif change_pct > 2:
                trend = "INCREASING"
            else:
                trend = "STABLE"

    rep_vs_current = "UNKNOWN"
    if avg_repurchase_price is not None and current_price is not None and avg_repurchase_price > 0:
        ratio = current_price / avg_repurchase_price
        if ratio > 1.1:
            rep_vs_current = "GOOD"  # Bought below current price
        elif ratio < 0.9:
            rep_vs_current = "BAD"  # Overpaid
        else:
            rep_vs_current = "NEUTRAL"

    bb_yield = None
    if buyback_amount and market_cap and market_cap > 0:
        bb_yield = round(buyback_amount / market_cap * 100, 2)

    return BuybackEffectiveness(
        shares_outstanding_trend=trend,
        shares_5y_change_pct=change_pct,
        avg_repurchase_price=avg_repurchase_price,
        current_price=current_price,
        repurchase_vs_current=rep_vs_current,
        buyback_yield=bb_yield,
    )


def assess_dividend_sustainability(
    eps: float | None,
    fcf_per_share: float | None,
    dividend_per_share: float | None,
    total_dividends: float | None = None,
    total_fcf: float | None = None,
    consecutive_growth_years: int | None = None,
) -> DividendSustainability:
    """Assess dividend sustainability."""
    eps_payout = None
    fcf_payout = None
    coverage = None
    sustainable = True

    if eps and eps > 0 and dividend_per_share:
        eps_payout = round(dividend_per_share / eps, 4)
        if eps_payout > 1.0:
            sustainable = False  # Paying more than earning

    if fcf_per_share and fcf_per_share > 0 and dividend_per_share:
        fcf_payout = round(dividend_per_share / fcf_per_share, 4)
        if fcf_payout > 0.90:
            sustainable = False  # Very thin coverage

    if total_fcf and total_dividends and total_fcf > 0:
        coverage = round(total_fcf / total_dividends, 4)
        if coverage < 1.2:
            sustainable = False

    return DividendSustainability(
        eps_payout_ratio=eps_payout,
        fcf_payout_ratio=fcf_payout,
        fcf_coverage=coverage,
        consecutive_growth_years=consecutive_growth_years,
        is_sustainable=sustainable,
    )


def compute_capital_allocation_score(
    fcf: FCFConversion,
    wc: WorkingCapitalDiscipline,
    ma: MADiscipline,
    buybacks: BuybackEffectiveness,
    dividends: DividendSustainability,
) -> float:
    """Compute overall capital allocation score (0-100).

    Components:
    - FCF conversion (25 pts)
    - Working capital discipline (20 pts)
    - M&A discipline (20 pts)
    - Buyback effectiveness (15 pts)
    - Dividend sustainability (20 pts)
    """
    score = 50.0  # Start at neutral

    # FCF conversion (max 25 pts above baseline, min -25)
    if fcf.ebitda_to_fcf_ratio is not None:
        if fcf.ebitda_to_fcf_ratio >= 0.80:
            score += 25.0
        elif fcf.ebitda_to_fcf_ratio >= 0.60:
            score += 15.0
        elif fcf.ebitda_to_fcf_ratio >= 0.50:
            score += 5.0
        else:
            score -= 15.0  # Red flag

    # Working capital (max 10 pts)
    if wc.ccc_trend == "IMPROVING":
        score += 10.0
    elif wc.ccc_trend == "DETERIORATING":
        score -= 10.0

    # M&A discipline (max 10 pts, min -15)
    if not ma.serial_acquirer and ma.impairment_count == 0:
        score += 10.0
    elif ma.serial_acquirer:
        score -= 5.0
    if ma.impairment_count > 0:
        score -= min(ma.impairment_count * 5.0, 15.0)

    # Buybacks
    if buybacks.repurchase_vs_current == "GOOD":
        score += 7.5
    elif buybacks.repurchase_vs_current == "BAD":
        score -= 7.5

    # Dividends
    if dividends.is_sustainable:
        score += 10.0
    else:
        score -= 10.0
    if dividends.consecutive_growth_years and dividends.consecutive_growth_years >= 10:
        score += 5.0

    return max(0.0, min(100.0, round(score, 2)))


# ── Orchestrator ──────────────────────────────────────────────────────────


def analyze_capital_allocation(data: dict) -> CapitalAllocationResult:
    """Complete capital allocation analysis.

    Parameters
    ----------
    data : dict
        Expected keys: ebitda, fcf, capex, depreciation, revenue, cogs,
        receivables, inventory, payables, acquisitions, goodwill_history,
        total_assets_history, shares_history, avg_repurchase_price,
        current_price, buyback_amount, market_cap, eps, fcf_per_share,
        dividend_per_share, total_dividends, total_fcf, consecutive_growth_years,
        wc_history
    """
    fcf = compute_fcf_conversion(
        data.get("ebitda"), data.get("fcf"),
        data.get("capex"), data.get("working_capital_change"),
    )
    capex = classify_capex(
        data.get("capex"), data.get("depreciation"), data.get("revenue"),
    )
    wc = compute_working_capital_discipline(
        data.get("receivables"), data.get("inventory"), data.get("payables"),
        data.get("revenue"), data.get("cogs"), data.get("wc_history"),
    )
    ma = assess_ma_discipline(
        data.get("acquisitions", []),
        data.get("goodwill_history"),
        data.get("total_assets_history"),
    )
    bb = assess_buyback_effectiveness(
        data.get("shares_history"),
        data.get("avg_repurchase_price"),
        data.get("current_price"),
        data.get("buyback_amount"),
        data.get("market_cap"),
    )
    div = assess_dividend_sustainability(
        data.get("eps"), data.get("fcf_per_share"), data.get("dividend_per_share"),
        data.get("total_dividends"), data.get("total_fcf"),
        data.get("consecutive_growth_years"),
    )

    score = compute_capital_allocation_score(fcf, wc, ma, bb, div)

    return CapitalAllocationResult(
        fcf_conversion=fcf,
        capex=capex,
        working_capital=wc,
        ma_discipline=ma,
        buybacks=bb,
        dividends=div,
        overall_score=score,
    )
