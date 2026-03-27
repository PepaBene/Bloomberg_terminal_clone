"""Pillar 3 Phase 2 — Part 7c: Balance Sheet Risk Analysis Engine.

Pure computation engine for assessing balance sheet and financial risk:
leverage trajectory, liquidity, refinancing risk, bond market context.

No database access — all functions accept and return plain data.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field


# ── Dataclasses ───────────────────────────────────────────────────────────


@dataclass
class LeverageTrajectory:
    """Leverage metrics with trend analysis."""

    net_debt_ebitda: float | None = None
    net_debt_ebitda_trend: str = "UNKNOWN"  # IMPROVING/STABLE/DETERIORATING
    interest_coverage: float | None = None
    interest_coverage_trend: str = "UNKNOWN"
    debt_maturity_profile: dict = field(default_factory=dict)  # {near_term, medium, long_term}


@dataclass
class LiquidityAssessment:
    """Liquidity assessment."""

    liquidity_ratio: float | None = None  # (cash + revolver) / 12mo obligations
    cash_burn_rate: float | None = None  # monthly, if negative FCF
    months_of_runway: float | None = None
    working_capital_needs: str = "UNKNOWN"  # LOW/MODERATE/HIGH


@dataclass
class RefinancingRisk:
    """Refinancing risk score."""

    score: float = 50.0  # 0-100 (lower = lower risk)
    classification: str = "MODERATE_RISK"  # LOW_RISK, MODERATE_RISK, ELEVATED_RISK, HIGH_RISK
    maturity_24mo_pct: float | None = None
    coverage_trend: str = "UNKNOWN"
    z_score: float | None = None
    components: dict = field(default_factory=dict)


@dataclass
class FIProfile:
    """Fixed income profile summary from Pillar 2 FI data."""

    total_outstanding: float | None = None
    weighted_avg_ytm: float | None = None
    weighted_avg_spread: float | None = None
    fixed_pct: float | None = None
    floating_pct: float | None = None
    is_investment_grade: bool | None = None
    credit_rating: str | None = None
    credit_outlook: str | None = None
    credit_momentum: str | None = None
    market_cost_of_debt: float | None = None
    accounting_cost_of_debt: float | None = None
    cost_gap_bps: float | None = None  # market - accounting, flagged if >150
    maturity_wall: list[dict] = field(default_factory=list)  # [{year, amount, pct}]


@dataclass
class BalanceSheetRiskResult:
    """Complete balance sheet risk assessment."""

    leverage: LeverageTrajectory = field(default_factory=LeverageTrajectory)
    liquidity: LiquidityAssessment = field(default_factory=LiquidityAssessment)
    refinancing_risk: RefinancingRisk = field(default_factory=RefinancingRisk)
    fi_profile: FIProfile | None = None


# ── Core Functions ────────────────────────────────────────────────────────


def _classify_trend(values: list[float]) -> str:
    """Classify a time series trend."""
    if len(values) < 2:
        return "UNKNOWN"
    first = statistics.mean(values[: len(values) // 2])
    second = statistics.mean(values[len(values) // 2 :])
    if first == 0:
        return "STABLE"
    change = (second - first) / abs(first)
    if change > 0.05:
        return "DETERIORATING"  # For debt ratios, rising = deteriorating
    elif change < -0.05:
        return "IMPROVING"  # Falling debt ratio = improving
    return "STABLE"


def _classify_coverage_trend(values: list[float]) -> str:
    """Classify interest coverage trend (higher = better)."""
    if len(values) < 2:
        return "UNKNOWN"
    first = statistics.mean(values[: len(values) // 2])
    second = statistics.mean(values[len(values) // 2 :])
    if first == 0:
        return "STABLE"
    change = (second - first) / abs(first)
    if change > 0.05:
        return "IMPROVING"
    elif change < -0.05:
        return "DETERIORATING"
    return "STABLE"


def compute_leverage_trajectory(
    history: list[dict],
) -> LeverageTrajectory:
    """Compute leverage metrics with trend.

    Parameters
    ----------
    history : list[dict]
        Each period: {net_debt_ebitda, interest_coverage, debt_maturity_near,
                      debt_maturity_medium, debt_maturity_long}
    """
    if not history:
        return LeverageTrajectory()

    latest = history[-1]
    nd_ebitda = latest.get("net_debt_ebitda")
    int_cov = latest.get("interest_coverage")

    # Trends
    nd_values = [h.get("net_debt_ebitda") for h in history if h.get("net_debt_ebitda") is not None]
    ic_values = [h.get("interest_coverage") for h in history if h.get("interest_coverage") is not None]

    nd_trend = _classify_trend(nd_values) if nd_values else "UNKNOWN"
    ic_trend = _classify_coverage_trend(ic_values) if ic_values else "UNKNOWN"

    maturity = {
        "near_term": latest.get("debt_maturity_near", 0),
        "medium_term": latest.get("debt_maturity_medium", 0),
        "long_term": latest.get("debt_maturity_long", 0),
    }

    return LeverageTrajectory(
        net_debt_ebitda=nd_ebitda,
        net_debt_ebitda_trend=nd_trend,
        interest_coverage=int_cov,
        interest_coverage_trend=ic_trend,
        debt_maturity_profile=maturity,
    )


def assess_liquidity(data: dict) -> LiquidityAssessment:
    """Assess liquidity position.

    Parameters
    ----------
    data : dict
        Expected keys: cash, revolver_available, twelve_mo_obligations,
        monthly_fcf (negative if burning), revenue_growth_pct
    """
    cash = data.get("cash", 0)
    revolver = data.get("revolver_available", 0)
    obligations = data.get("twelve_mo_obligations", 0)

    ratio = None
    if obligations and obligations > 0:
        ratio = round((cash + revolver) / obligations, 4)

    burn_rate = None
    runway = None
    monthly_fcf = data.get("monthly_fcf")
    if monthly_fcf is not None and monthly_fcf < 0:
        burn_rate = round(abs(monthly_fcf), 2)
        if burn_rate > 0:
            runway = round((cash + revolver) / burn_rate, 1)

    # Working capital needs assessment
    rev_growth = data.get("revenue_growth_pct", 0)
    wc_needs = "LOW"
    if rev_growth and rev_growth > 0.15:
        wc_needs = "HIGH"  # Fast growth needs working capital
    elif rev_growth and rev_growth > 0.05:
        wc_needs = "MODERATE"

    return LiquidityAssessment(
        liquidity_ratio=ratio,
        cash_burn_rate=burn_rate,
        months_of_runway=runway,
        working_capital_needs=wc_needs,
    )


def compute_refinancing_risk(data: dict) -> RefinancingRisk:
    """Compute refinancing risk score (0-100, lower = lower risk).

    Components:
    - Maturity in 24 months / total debt (30 pts)
    - Coverage trend (25 pts)
    - Z-Score zone (25 pts)
    - Credit spread environment (20 pts)

    Parameters
    ----------
    data : dict
        Expected keys: maturity_24mo, total_debt, coverage_trend,
        z_score, credit_spread_bps
    """
    score = 0.0
    components = {}

    # Maturity wall (30 pts max)
    maturity_24mo = data.get("maturity_24mo", 0)
    total_debt = data.get("total_debt", 0)
    mat_pct = None
    if total_debt and total_debt > 0:
        mat_pct = maturity_24mo / total_debt
        mat_points = min(mat_pct * 100, 30.0)  # 30% maturing → 30 pts
        score += mat_points
        components["maturity_wall"] = round(mat_points, 1)
    else:
        components["maturity_wall"] = 0

    # Coverage trend (25 pts max)
    cov_trend = data.get("coverage_trend", "UNKNOWN")
    cov_points = {"DETERIORATING": 25, "STABLE": 10, "IMPROVING": 0, "UNKNOWN": 12.5}
    score += cov_points.get(cov_trend, 12.5)
    components["coverage"] = cov_points.get(cov_trend, 12.5)

    # Z-Score (25 pts max)
    z = data.get("z_score")
    if z is not None:
        if z < 1.81:
            score += 25.0  # Distress zone
        elif z < 2.99:
            score += 15.0  # Grey zone
        else:
            score += 0.0  # Safe zone
        components["z_score"] = z
    else:
        score += 12.5
        components["z_score"] = None

    # Credit spread (20 pts max)
    spread = data.get("credit_spread_bps")
    if spread is not None:
        if spread > 500:
            score += 20.0
        elif spread > 300:
            score += 15.0
        elif spread > 150:
            score += 8.0
        components["spread_bps"] = spread
    else:
        score += 10.0
        components["spread_bps"] = None

    score = max(0.0, min(100.0, round(score, 2)))

    # Classification
    if score < 25:
        classification = "LOW_RISK"
    elif score < 50:
        classification = "MODERATE_RISK"
    elif score < 75:
        classification = "ELEVATED_RISK"
    else:
        classification = "HIGH_RISK"

    return RefinancingRisk(
        score=score,
        classification=classification,
        maturity_24mo_pct=round(mat_pct, 4) if mat_pct is not None else None,
        coverage_trend=cov_trend,
        z_score=z,
        components=components,
    )


def build_fi_profile(bond_data: dict | None) -> FIProfile | None:
    """Build fixed income profile from Pillar 2 FI data.

    Parameters
    ----------
    bond_data : dict | None
        Expected keys: total_outstanding, weighted_avg_ytm, weighted_avg_spread,
        fixed_pct, floating_pct, is_investment_grade, credit_rating, credit_outlook,
        credit_momentum, interest_expense, avg_total_debt, maturity_wall
    """
    if not bond_data:
        return None

    # Market vs accounting cost of debt comparison
    market_cost = bond_data.get("weighted_avg_ytm")
    interest_expense = bond_data.get("interest_expense")
    avg_debt = bond_data.get("avg_total_debt")
    accounting_cost = None
    cost_gap = None

    if interest_expense and avg_debt and avg_debt > 0:
        accounting_cost = round(interest_expense / avg_debt, 4)
        if market_cost is not None:
            cost_gap = round((market_cost - accounting_cost) * 10000, 0)  # in bps

    return FIProfile(
        total_outstanding=bond_data.get("total_outstanding"),
        weighted_avg_ytm=market_cost,
        weighted_avg_spread=bond_data.get("weighted_avg_spread"),
        fixed_pct=bond_data.get("fixed_pct"),
        floating_pct=bond_data.get("floating_pct"),
        is_investment_grade=bond_data.get("is_investment_grade"),
        credit_rating=bond_data.get("credit_rating"),
        credit_outlook=bond_data.get("credit_outlook"),
        credit_momentum=bond_data.get("credit_momentum"),
        market_cost_of_debt=market_cost,
        accounting_cost_of_debt=accounting_cost,
        cost_gap_bps=cost_gap,
        maturity_wall=bond_data.get("maturity_wall", []),
    )


# ── Orchestrator ──────────────────────────────────────────────────────────


def assess_balance_sheet_risk(
    financials: dict,
    history: list[dict],
    bond_data: dict | None = None,
) -> BalanceSheetRiskResult:
    """Complete balance sheet risk assessment.

    Parameters
    ----------
    financials : dict
        Current period financial data.
    history : list[dict]
        Multi-period history (oldest→newest).
    bond_data : dict | None
        FI data from Pillar 2.
    """
    leverage = compute_leverage_trajectory(history)
    liquidity = assess_liquidity(financials)
    refi = compute_refinancing_risk(financials)
    fi = build_fi_profile(bond_data)

    return BalanceSheetRiskResult(
        leverage=leverage,
        liquidity=liquidity,
        refinancing_risk=refi,
        fi_profile=fi,
    )
