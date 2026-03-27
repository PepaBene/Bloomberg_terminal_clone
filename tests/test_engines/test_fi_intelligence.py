"""Tests for Pillar 3 Phase 3C — Part 15: FI Intelligence Engine."""

import pytest

from src.engines.fi_intelligence import (
    CreditMarketBriefing,
    IssuanceIntelligence,
    IssuerCreditProfile,
    YieldCurveBriefing,
    analyze_new_issuance,
    assess_auction_result,
    build_issuer_credit_profile,
    classify_credit_regime,
    classify_curve_shape,
    compute_spread_percentile,
    compute_weekly_issuance_volume,
    generate_credit_market_briefing,
    generate_equity_implications,
    generate_yield_curve_briefing,
)


# ── classify_curve_shape ──────────────────────────────────────────────────


class TestClassifyCurveShape:
    def test_steep(self):
        assert classify_curve_shape(150.0) == "STEEP"

    def test_steep_boundary(self):
        assert classify_curve_shape(101.0) == "STEEP"

    def test_normal(self):
        assert classify_curve_shape(50.0) == "NORMAL"

    def test_normal_boundary(self):
        assert classify_curve_shape(21.0) == "NORMAL"

    def test_flat(self):
        assert classify_curve_shape(0.0) == "FLAT"

    def test_flat_boundary_positive(self):
        assert classify_curve_shape(20.0) == "FLAT"

    def test_flat_boundary_negative(self):
        assert classify_curve_shape(-19.0) == "FLAT"

    def test_inverted(self):
        assert classify_curve_shape(-50.0) == "INVERTED"

    def test_inverted_boundary(self):
        assert classify_curve_shape(-20.0) == "INVERTED"


# ── compute_spread_percentile ─────────────────────────────────────────────


class TestComputeSpreadPercentile:
    def test_at_max(self):
        history = [50.0, 100.0, 150.0, 200.0]
        assert compute_spread_percentile(200.0, history) == 100.0

    def test_at_min(self):
        history = [50.0, 100.0, 150.0, 200.0]
        result = compute_spread_percentile(40.0, history)
        assert result == 0.0

    def test_middle(self):
        history = [50.0, 100.0, 150.0, 200.0]
        result = compute_spread_percentile(100.0, history)
        assert result == 50.0

    def test_empty_history(self):
        assert compute_spread_percentile(100.0, []) == 50.0

    def test_single_value(self):
        assert compute_spread_percentile(100.0, [100.0]) == 100.0

    def test_below_all(self):
        history = [100.0, 200.0, 300.0]
        assert compute_spread_percentile(50.0, history) == 0.0


# ── assess_auction_result ─────────────────────────────────────────────────


class TestAssessAuctionResult:
    def test_strong_demand(self):
        assert assess_auction_result(3.0, 2.0) == "STRONG"

    def test_weak_demand(self):
        assert assess_auction_result(1.5, 2.5) == "WEAK"

    def test_normal_demand(self):
        assert assess_auction_result(2.1, 2.0) == "NORMAL"

    def test_zero_average(self):
        assert assess_auction_result(2.0, 0.0) == "NORMAL"

    def test_boundary_strong(self):
        # Exactly at 1.2x → not strong (needs >)
        assert assess_auction_result(2.4, 2.0) == "NORMAL"

    def test_boundary_strong_above(self):
        assert assess_auction_result(2.41, 2.0) == "STRONG"


# ── generate_equity_implications ──────────────────────────────────────────


class TestGenerateEquityImplications:
    def test_steep_curve(self):
        result = generate_equity_implications("STEEP", None)
        assert any("financials" in s.lower() for s in result)

    def test_inverted_curve(self):
        result = generate_equity_implications("INVERTED", None)
        assert any("recession" in s.lower() for s in result)

    def test_flat_curve(self):
        result = generate_equity_implications("FLAT", None)
        assert len(result) >= 1

    def test_normal_curve(self):
        result = generate_equity_implications("NORMAL", None)
        assert any("broad" in s.lower() or "normal" in s.lower() for s in result)

    def test_rising_rates(self):
        result = generate_equity_implications("NORMAL", 15.0)
        assert any("rising" in s.lower() or "duration" in s.lower() for s in result)

    def test_falling_rates(self):
        result = generate_equity_implications("NORMAL", -15.0)
        assert any("falling" in s.lower() or "growth" in s.lower() for s in result)


# ── generate_yield_curve_briefing ─────────────────────────────────────────


class TestGenerateYieldCurveBriefing:
    def test_basic_briefing(self):
        curve_data = {"spread_2s10s_bps": 50.0, "spread_3m10y_bps": 80.0}
        result = generate_yield_curve_briefing(curve_data)
        assert isinstance(result, YieldCurveBriefing)
        assert result.curve_shape == "NORMAL"
        assert result.spread_2s10s_bps == 50.0
        assert result.spread_3m10y_bps == 80.0
        assert result.daily_change_10y_bps is None

    def test_with_prior_data(self):
        curve_data = {"spread_2s10s_bps": 50.0, "yield_10y": 4.25}
        prior = {"yield_10y": 4.20}
        result = generate_yield_curve_briefing(curve_data, prior)
        assert result.daily_change_10y_bps == pytest.approx(5.0, abs=0.1)

    def test_with_history(self):
        curve_data = {
            "spread_2s10s_bps": 50.0,
            "history_5y": [30.0, 40.0, 50.0, 60.0, 70.0],
        }
        result = generate_yield_curve_briefing(curve_data)
        assert result.spread_percentile_5y is not None

    def test_inverted_briefing(self):
        curve_data = {"spread_2s10s_bps": -50.0}
        result = generate_yield_curve_briefing(curve_data)
        assert result.curve_shape == "INVERTED"

    def test_key_metrics_populated(self):
        curve_data = {"spread_2s10s_bps": 120.0, "spread_3m10y_bps": 150.0}
        result = generate_yield_curve_briefing(curve_data)
        assert "spread_2s10s_bps" in result.key_metrics
        assert "spread_3m10y_bps" in result.key_metrics


# ── classify_credit_regime ────────────────────────────────────────────────


class TestClassifyCreditRegime:
    def test_risk_on(self):
        assert classify_credit_regime(60.0, 300.0) == "RISK_ON"

    def test_normal(self):
        assert classify_credit_regime(100.0, 400.0) == "NORMAL"

    def test_risk_off(self):
        assert classify_credit_regime(200.0, 600.0) == "RISK_OFF"

    def test_stress(self):
        assert classify_credit_regime(300.0, 800.0) == "STRESS"

    def test_boundary_risk_on(self):
        assert classify_credit_regime(79.0, 300.0) == "RISK_ON"

    def test_boundary_normal(self):
        assert classify_credit_regime(80.0, 300.0) == "NORMAL"


# ── generate_credit_market_briefing ───────────────────────────────────────


class TestGenerateCreditMarketBriefing:
    def test_basic_briefing(self):
        result = generate_credit_market_briefing(100.0, 400.0, 95.0, 390.0)
        assert isinstance(result, CreditMarketBriefing)
        assert result.ig_oas_bps == 100.0
        assert result.hy_oas_bps == 400.0
        assert result.ig_change_1w == 5.0
        assert result.hy_change_1w == 10.0
        assert result.credit_regime == "NORMAL"

    def test_with_history(self):
        history = [
            {"ig_oas": 80.0, "hy_oas": 350.0},
            {"ig_oas": 120.0, "hy_oas": 450.0},
        ]
        result = generate_credit_market_briefing(100.0, 400.0, 95.0, 390.0, history=history)
        assert result.ig_percentile_1y is not None
        assert result.hy_percentile_1y is not None

    def test_with_events(self):
        events = [
            {"entity": "FordCo", "from_rating": "BBB-", "to_rating": "BB+", "type": "fallen_angel"},
            {"entity": "StarCo", "from_rating": "BB+", "to_rating": "BBB-", "type": "rising_star"},
        ]
        result = generate_credit_market_briefing(100.0, 400.0, 95.0, 390.0, events=events)
        assert len(result.fallen_angels) == 1
        assert len(result.rising_stars) == 1

    def test_stress_regime(self):
        result = generate_credit_market_briefing(300.0, 800.0, 250.0, 700.0)
        assert result.credit_regime == "STRESS"


# ── analyze_new_issuance ──────────────────────────────────────────────────


class TestAnalyzeNewIssuance:
    def test_basic_issuance(self):
        issue = {
            "issue_date": "2026-03-20",
            "issuer": "TestCorp",
            "size_mm": 500.0,
            "coupon": 5.25,
            "spread_at_issue_bps": 150.0,
            "use_of_proceeds": "GENERAL",
        }
        result = analyze_new_issuance(issue)
        assert isinstance(result, IssuanceIntelligence)
        assert result.issuer == "TestCorp"
        assert result.demand_assessment == "NORMAL"

    def test_tighter_than_talk(self):
        issue = {
            "issue_date": "2026-03-20",
            "issuer": "TestCorp",
            "size_mm": 500.0,
            "coupon": 5.25,
            "spread_at_issue_bps": 130.0,
            "initial_talk_bps": 150.0,
            "use_of_proceeds": "GENERAL",
        }
        result = analyze_new_issuance(issue)
        assert result.demand_assessment == "STRONG"

    def test_vs_existing_bonds(self):
        issue = {
            "issue_date": "2026-03-20",
            "issuer": "TestCorp",
            "size_mm": 500.0,
            "coupon": 5.25,
            "spread_at_issue_bps": 130.0,
            "use_of_proceeds": "GENERAL",
        }
        existing = [{"spread_bps": 150.0}, {"spread_bps": 160.0}]
        result = analyze_new_issuance(issue, existing)
        assert result.spread_vs_existing is not None
        assert result.spread_vs_existing < 0  # tighter

    def test_large_benchmark(self):
        issue = {
            "issue_date": "2026-03-20",
            "issuer": "BigCorp",
            "size_mm": 1500.0,
            "coupon": 4.5,
            "spread_at_issue_bps": 100.0,
            "use_of_proceeds": "REFINANCING",
        }
        result = analyze_new_issuance(issue)
        assert any("benchmark" in s.lower() for s in result.implications)
        assert any("refinanc" in s.lower() for s in result.implications)


# ── compute_weekly_issuance_volume ────────────────────────────────────────


class TestComputeWeeklyIssuanceVolume:
    def test_mixed_issuance(self):
        issues = [
            {"size_mm": 500.0, "rating": "A", "use_of_proceeds": "REFINANCING"},
            {"size_mm": 300.0, "rating": "BB+", "use_of_proceeds": "ACQUISITION"},
            {"size_mm": 200.0, "rating": "BBB", "use_of_proceeds": "GENERAL"},
        ]
        result = compute_weekly_issuance_volume(issues)
        assert result["ig_volume"] == 700.0
        assert result["hy_volume"] == 300.0
        assert result["total"] == 1000.0
        assert result["refinancing_pct"] == pytest.approx(33.33, abs=0.01)
        assert result["acquisition_pct"] == pytest.approx(33.33, abs=0.01)

    def test_empty_issuance(self):
        result = compute_weekly_issuance_volume([])
        assert result["total"] == 0.0
        assert result["refinancing_pct"] == 0.0

    def test_all_ig(self):
        issues = [
            {"size_mm": 400.0, "rating": "AAA", "use_of_proceeds": "GENERAL"},
            {"size_mm": 600.0, "rating": "BBB-", "use_of_proceeds": "GENERAL"},
        ]
        result = compute_weekly_issuance_volume(issues)
        assert result["ig_volume"] == 1000.0
        assert result["hy_volume"] == 0.0


# ── build_issuer_credit_profile ───────────────────────────────────────────


class TestBuildIssuerCreditProfile:
    def test_basic_profile(self):
        bonds = [
            {"amount_mm": 500.0, "ytm": 0.055, "spread_bps": 150.0, "maturity_year": 2028},
            {"amount_mm": 300.0, "ytm": 0.065, "spread_bps": 200.0, "maturity_year": 2031},
        ]
        ratings = [{"agency": "S&P", "rating": "BBB", "outlook": "STABLE", "momentum": "STABLE"}]
        result = build_issuer_credit_profile(bonds, ratings)
        assert isinstance(result, IssuerCreditProfile)
        assert result.total_debt_outstanding_mm == 800.0
        assert result.credit_rating == "BBB"
        assert result.credit_momentum == "STABLE"
        assert result.weighted_avg_ytm is not None
        assert len(result.maturity_wall) == 2

    def test_with_financials(self):
        bonds = [
            {"amount_mm": 1000.0, "ytm": 0.06, "spread_bps": 180.0, "maturity_year": 2029},
        ]
        financials = {"accounting_cost_of_debt": 0.04}
        result = build_issuer_credit_profile(bonds, financials=financials)
        assert result.market_cost_of_debt == pytest.approx(0.06, abs=0.001)
        assert result.accounting_cost_of_debt == 0.04
        assert result.cost_gap_bps is not None
        assert result.cost_gap_bps > 0  # market > accounting

    def test_empty_bonds(self):
        result = build_issuer_credit_profile([])
        assert result.total_debt_outstanding_mm is None
        assert result.weighted_avg_ytm is None

    def test_maturity_wall_sorted(self):
        bonds = [
            {"amount_mm": 200.0, "ytm": 0.05, "spread_bps": 100.0, "maturity_year": 2031},
            {"amount_mm": 300.0, "ytm": 0.06, "spread_bps": 120.0, "maturity_year": 2028},
            {"amount_mm": 100.0, "ytm": 0.045, "spread_bps": 90.0, "maturity_year": 2028},
        ]
        result = build_issuer_credit_profile(bonds)
        assert result.maturity_wall[0]["year"] == 2028
        assert result.maturity_wall[0]["amount_mm"] == 400.0
        assert result.maturity_wall[1]["year"] == 2031
