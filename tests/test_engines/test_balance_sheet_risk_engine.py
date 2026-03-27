"""Tests for Pillar 3 Phase 2 — Part 7c: Balance Sheet Risk Analysis Engine."""

from src.engines.balance_sheet_risk_engine import (
    BalanceSheetRiskResult,
    FIProfile,
    LeverageTrajectory,
    LiquidityAssessment,
    RefinancingRisk,
    assess_balance_sheet_risk,
    assess_liquidity,
    build_fi_profile,
    compute_leverage_trajectory,
    compute_refinancing_risk,
)


# ── Leverage Trajectory Tests ────────────────────────────────────────────


class TestLeverageTrajectory:
    """Tests for compute_leverage_trajectory()."""

    def test_improving_leverage(self):
        """Net Debt/EBITDA declining over time -> IMPROVING."""
        history = [
            {"net_debt_ebitda": 4.5, "interest_coverage": 3.0, "debt_maturity_near": 500.0},
            {"net_debt_ebitda": 4.0, "interest_coverage": 3.5, "debt_maturity_near": 400.0},
            {"net_debt_ebitda": 3.2, "interest_coverage": 4.2, "debt_maturity_near": 350.0},
            {"net_debt_ebitda": 2.5, "interest_coverage": 5.0, "debt_maturity_near": 300.0},
        ]
        result = compute_leverage_trajectory(history)
        assert isinstance(result, LeverageTrajectory)
        assert result.net_debt_ebitda == 2.5
        assert result.net_debt_ebitda_trend == "IMPROVING"
        assert result.interest_coverage == 5.0
        assert result.interest_coverage_trend == "IMPROVING"

    def test_deteriorating_leverage(self):
        """Net Debt/EBITDA rising and interest coverage dropping."""
        history = [
            {"net_debt_ebitda": 2.0, "interest_coverage": 8.0},
            {"net_debt_ebitda": 2.5, "interest_coverage": 6.5},
            {"net_debt_ebitda": 3.5, "interest_coverage": 4.0},
            {"net_debt_ebitda": 4.8, "interest_coverage": 2.5},
        ]
        result = compute_leverage_trajectory(history)
        assert result.net_debt_ebitda == 4.8
        assert result.net_debt_ebitda_trend == "DETERIORATING"
        assert result.interest_coverage_trend == "DETERIORATING"

    def test_no_history(self):
        """Empty history returns defaults."""
        result = compute_leverage_trajectory([])
        assert result.net_debt_ebitda is None
        assert result.net_debt_ebitda_trend == "UNKNOWN"
        assert result.interest_coverage is None


# ── Liquidity Tests ──────────────────────────────────────────────────────


class TestLiquidity:
    """Tests for assess_liquidity()."""

    def test_healthy_liquidity(self):
        """Ample cash + revolver vs short-term obligations."""
        data = {
            "cash": 5_000.0,
            "revolver_available": 3_000.0,
            "twelve_mo_obligations": 4_000.0,
            "revenue_growth_pct": 0.08,
        }
        result = assess_liquidity(data)
        assert isinstance(result, LiquidityAssessment)
        assert result.liquidity_ratio == 2.0  # (5000+3000)/4000
        assert result.cash_burn_rate is None  # Not burning cash
        assert result.months_of_runway is None
        assert result.working_capital_needs == "MODERATE"

    def test_cash_burning(self):
        """Negative monthly FCF -> burn rate and runway computed."""
        data = {
            "cash": 2_400.0,
            "revolver_available": 600.0,
            "twelve_mo_obligations": 1_500.0,
            "monthly_fcf": -200.0,
            "revenue_growth_pct": 0.25,
        }
        result = assess_liquidity(data)
        assert result.cash_burn_rate == 200.0
        assert result.months_of_runway == 15.0  # (2400+600)/200
        assert result.working_capital_needs == "HIGH"

    def test_no_data(self):
        """Missing data returns safe defaults."""
        result = assess_liquidity({})
        assert result.liquidity_ratio is None
        assert result.cash_burn_rate is None
        assert result.working_capital_needs == "LOW"


# ── Refinancing Risk Tests ───────────────────────────────────────────────


class TestRefinancingRisk:
    """Tests for compute_refinancing_risk()."""

    def test_low_risk(self):
        """Safe z-score, low maturity wall, improving coverage, tight spread."""
        data = {
            "maturity_24mo": 200.0,
            "total_debt": 5_000.0,
            "coverage_trend": "IMPROVING",
            "z_score": 3.5,
            "credit_spread_bps": 100,
        }
        result = compute_refinancing_risk(data)
        assert isinstance(result, RefinancingRisk)
        assert result.classification == "LOW_RISK"
        assert result.score < 25.0
        assert result.maturity_24mo_pct is not None
        assert result.maturity_24mo_pct < 0.05
        assert result.z_score == 3.5

    def test_high_risk(self):
        """Distress z-score, heavy maturities, deteriorating coverage, wide spread."""
        data = {
            "maturity_24mo": 3_000.0,
            "total_debt": 5_000.0,
            "coverage_trend": "DETERIORATING",
            "z_score": 1.2,
            "credit_spread_bps": 650,
        }
        result = compute_refinancing_risk(data)
        assert result.classification == "HIGH_RISK"
        assert result.score >= 75.0

    def test_moderate_risk(self):
        """Grey-zone z-score, moderate maturity, stable coverage."""
        data = {
            "maturity_24mo": 500.0,
            "total_debt": 5_000.0,
            "coverage_trend": "STABLE",
            "z_score": 2.5,
            "credit_spread_bps": 200,
        }
        result = compute_refinancing_risk(data)
        assert result.classification in ("MODERATE_RISK", "ELEVATED_RISK")
        assert 25.0 <= result.score < 75.0

    def test_elevated_risk(self):
        """No z-score, heavy maturity wall, deteriorating coverage."""
        data = {
            "maturity_24mo": 2_500.0,
            "total_debt": 5_000.0,
            "coverage_trend": "DETERIORATING",
            "z_score": None,
            "credit_spread_bps": 400,
        }
        result = compute_refinancing_risk(data)
        assert result.classification in ("ELEVATED_RISK", "HIGH_RISK")
        assert result.score >= 50.0


# ── FI Profile Tests ─────────────────────────────────────────────────────


class TestFIProfile:
    """Tests for build_fi_profile()."""

    def test_with_bond_data(self):
        """Full bond data produces cost-of-debt gap analysis."""
        bond_data = {
            "total_outstanding": 10_000.0,
            "weighted_avg_ytm": 0.065,
            "weighted_avg_spread": 0.025,
            "fixed_pct": 0.75,
            "floating_pct": 0.25,
            "is_investment_grade": True,
            "credit_rating": "BBB+",
            "credit_outlook": "STABLE",
            "credit_momentum": "NEUTRAL",
            "interest_expense": 400.0,
            "avg_total_debt": 10_000.0,
            "maturity_wall": [
                {"year": 2025, "amount": 1_000.0, "pct": 0.10},
                {"year": 2026, "amount": 2_000.0, "pct": 0.20},
            ],
        }
        result = build_fi_profile(bond_data)
        assert isinstance(result, FIProfile)
        assert result.total_outstanding == 10_000.0
        assert result.credit_rating == "BBB+"
        assert result.is_investment_grade is True
        # Accounting cost = 400/10000 = 0.04
        assert result.accounting_cost_of_debt == 0.04
        # Market cost = 0.065
        assert result.market_cost_of_debt == 0.065
        # Gap = (0.065 - 0.04) * 10000 = 250 bps
        assert result.cost_gap_bps == 250.0
        assert len(result.maturity_wall) == 2

    def test_without_bond_data(self):
        """None bond_data returns None profile."""
        result = build_fi_profile(None)
        assert result is None


# ── Orchestrator Tests ───────────────────────────────────────────────────


class TestAssessBalanceSheetRisk:
    """Tests for assess_balance_sheet_risk() orchestrator."""

    def test_full_orchestration(self):
        """Full data produces complete BalanceSheetRiskResult."""
        financials = {
            "cash": 8_000.0,
            "revolver_available": 2_000.0,
            "twelve_mo_obligations": 5_000.0,
            "monthly_fcf": 250.0,
            "revenue_growth_pct": 0.10,
            "maturity_24mo": 1_500.0,
            "total_debt": 15_000.0,
            "coverage_trend": "STABLE",
            "z_score": 2.8,
            "credit_spread_bps": 180,
        }
        history = [
            {"net_debt_ebitda": 3.0, "interest_coverage": 5.5},
            {"net_debt_ebitda": 2.8, "interest_coverage": 6.0},
            {"net_debt_ebitda": 2.5, "interest_coverage": 6.5},
            {"net_debt_ebitda": 2.3, "interest_coverage": 7.0},
        ]
        bond_data = {
            "total_outstanding": 15_000.0,
            "weighted_avg_ytm": 0.055,
            "weighted_avg_spread": 0.018,
            "fixed_pct": 0.80,
            "floating_pct": 0.20,
            "is_investment_grade": True,
            "credit_rating": "A-",
            "credit_outlook": "POSITIVE",
            "credit_momentum": "IMPROVING",
            "interest_expense": 600.0,
            "avg_total_debt": 15_000.0,
            "maturity_wall": [],
        }
        result = assess_balance_sheet_risk(financials, history, bond_data)
        assert isinstance(result, BalanceSheetRiskResult)
        assert result.leverage.net_debt_ebitda == 2.3
        assert result.leverage.net_debt_ebitda_trend == "IMPROVING"
        assert result.liquidity.liquidity_ratio == 2.0
        assert result.refinancing_risk.classification in ("LOW_RISK", "MODERATE_RISK")
        assert result.fi_profile is not None
        assert result.fi_profile.credit_rating == "A-"
