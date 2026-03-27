"""Tests for E12 FI Risk Engine (Pillar 2 FI Supplement – Part 5)."""

import pytest

from src.engines.e12_fi_risk import (
    PD_BY_RATING,
    RECOVERY_RATES,
    compute_credit_distribution,
    compute_credit_var,
    compute_expected_loss,
    compute_portfolio_dv01,
    compute_rate_scenario_pnl,
    compute_single_bond_risk,
    compute_spread_scenario_pnl,
)


# ── compute_portfolio_dv01 ─────────────────────────────────────────────


def test_portfolio_dv01_single_position():
    """Single 1M MV, duration 7 -> DV01 = 1_000_000 * 7 * 0.0001 = 700."""
    positions = [{"market_value": 1_000_000, "modified_duration": 7.0}]
    dv01 = compute_portfolio_dv01(positions)
    assert dv01 == pytest.approx(700.0, abs=0.01)


def test_portfolio_dv01_multi_position():
    """Two positions: DV01 should sum."""
    positions = [
        {"market_value": 1_000_000, "modified_duration": 5.0},
        {"market_value": 2_000_000, "modified_duration": 10.0},
    ]
    # 1M*5*0.0001 + 2M*10*0.0001 = 500 + 2000 = 2500
    dv01 = compute_portfolio_dv01(positions)
    assert dv01 == pytest.approx(2500.0, abs=0.01)


def test_portfolio_dv01_zero_duration():
    """Zero duration position contributes zero DV01."""
    positions = [{"market_value": 5_000_000, "modified_duration": 0.0}]
    assert compute_portfolio_dv01(positions) == pytest.approx(0.0)


def test_portfolio_dv01_precomputed():
    """Positions with pre-computed DV01 and weights."""
    positions = [
        {"dv01": 500.0, "weight": 0.5},
        {"dv01": 1000.0, "weight": 0.3},
    ]
    # 500*0.5 + 1000*0.3 = 250 + 300 = 550
    assert compute_portfolio_dv01(positions) == pytest.approx(550.0)


# ── compute_rate_scenario_pnl ─────────────────────────────────────────


def test_rate_scenario_positive_shift():
    """+100 bps should produce negative P&L for a long-duration bond."""
    positions = [
        {"market_value": 1_000_000, "modified_duration": 7.0, "convexity": 60.0, "cusip": "AAA111"}
    ]
    result = compute_rate_scenario_pnl(positions, rate_shift_bps=100.0)
    assert result["total_pnl"] < 0
    assert len(result["by_position"]) == 1
    assert result["by_position"][0]["cusip"] == "AAA111"


def test_rate_scenario_negative_shift():
    """-100 bps should produce positive P&L."""
    positions = [
        {"market_value": 1_000_000, "modified_duration": 7.0, "convexity": 60.0, "cusip": "AAA111"}
    ]
    result = compute_rate_scenario_pnl(positions, rate_shift_bps=-100.0)
    assert result["total_pnl"] > 0


def test_rate_scenario_convexity_adjustment():
    """Convexity adjustment should make losses smaller than pure duration estimate.

    Pure duration P&L for +100 bps: -7 * 0.01 * 1M = -70,000
    With convexity: -70,000 + 0.5 * 60 * 0.01^2 * 1M = -70,000 + 3,000 = -67,000
    """
    positions = [
        {"market_value": 1_000_000, "modified_duration": 7.0, "convexity": 60.0}
    ]
    result = compute_rate_scenario_pnl(positions, rate_shift_bps=100.0)

    # Pure duration loss: -70,000
    # With convexity: -67,000
    assert result["total_pnl"] == pytest.approx(-67_000.0, abs=1.0)


# ── compute_spread_scenario_pnl ───────────────────────────────────────


def test_spread_widening():
    """+50 bps spread widening should produce a loss."""
    positions = [
        {"market_value": 1_000_000, "spread_duration": 5.0, "cusip": "BBB222"}
    ]
    result = compute_spread_scenario_pnl(positions, spread_shift_bps=50.0)
    # -5 * 0.005 * 1M = -25,000
    assert result["total_pnl"] == pytest.approx(-25_000.0, abs=1.0)
    assert result["total_pnl"] < 0


def test_spread_tightening():
    """-50 bps spread tightening should produce a gain."""
    positions = [
        {"market_value": 1_000_000, "spread_duration": 5.0, "cusip": "BBB222"}
    ]
    result = compute_spread_scenario_pnl(positions, spread_shift_bps=-50.0)
    assert result["total_pnl"] > 0
    assert result["total_pnl"] == pytest.approx(25_000.0, abs=1.0)


# ── compute_credit_distribution ───────────────────────────────────────


def test_credit_distribution_all_ig():
    """All investment-grade positions -> ig_pct = 100%."""
    positions = [
        {"market_value": 500_000, "rating_numeric": 1, "is_investment_grade": True},
        {"market_value": 500_000, "rating_numeric": 9, "is_investment_grade": True},
    ]
    dist = compute_credit_distribution(positions)
    assert dist["ig_pct"] == pytest.approx(100.0)
    assert dist["hy_pct"] == pytest.approx(0.0)
    assert dist["nr_pct"] == pytest.approx(0.0)


def test_credit_distribution_all_hy():
    """All high-yield positions -> hy_pct = 100%."""
    positions = [
        {"market_value": 1_000_000, "rating_numeric": 15, "is_investment_grade": False},
    ]
    dist = compute_credit_distribution(positions)
    assert dist["hy_pct"] == pytest.approx(100.0)
    assert dist["ig_pct"] == pytest.approx(0.0)


def test_credit_distribution_mixed():
    """Mixed IG/HY portfolio."""
    positions = [
        {"market_value": 600_000, "rating_numeric": 6, "is_investment_grade": True},
        {"market_value": 400_000, "rating_numeric": 14, "is_investment_grade": False},
    ]
    dist = compute_credit_distribution(positions)
    assert dist["ig_pct"] == pytest.approx(60.0)
    assert dist["hy_pct"] == pytest.approx(40.0)
    assert "A" in dist["by_rating"]
    assert "B+" in dist["by_rating"]


def test_credit_distribution_single_bond():
    """Single bond: bucket should have count=1 and weight_pct=100%."""
    positions = [
        {"market_value": 100_000, "rating_numeric": 9},
    ]
    dist = compute_credit_distribution(positions)
    assert "BBB" in dist["by_rating"]
    assert dist["by_rating"]["BBB"]["count"] == 1
    assert dist["by_rating"]["BBB"]["weight_pct"] == pytest.approx(100.0)
    assert dist["avg_rating_numeric"] == pytest.approx(9.0)


# ── compute_expected_loss ────────────────────────────────────────────


def test_expected_loss_aaa_bond():
    """AAA bond should have very low expected loss."""
    positions = [
        {"market_value": 1_000_000, "rating_numeric": 1, "seniority": "SENIOR_UNSECURED"}
    ]
    result = compute_expected_loss(positions)
    # EL = 1M * 0.0001 * 0.60 = 60
    assert result["total_expected_loss"] == pytest.approx(60.0, abs=1.0)
    assert result["total_expected_loss_pct"] < 0.001


def test_expected_loss_ccc_bond():
    """CCC bond should have high expected loss."""
    positions = [
        {"market_value": 1_000_000, "rating_numeric": 18, "seniority": "SENIOR_UNSECURED"}
    ]
    result = compute_expected_loss(positions)
    # EL = 1M * 0.20 * 0.60 = 120,000
    assert result["total_expected_loss"] == pytest.approx(120_000.0, abs=1.0)
    assert result["total_expected_loss_pct"] > 0.10


def test_expected_loss_portfolio_sum():
    """Portfolio expected loss should be the sum of individual positions."""
    positions = [
        {"market_value": 500_000, "rating_numeric": 1, "seniority": "SENIOR_UNSECURED", "cusip": "A"},
        {"market_value": 500_000, "rating_numeric": 18, "seniority": "SENIOR_UNSECURED", "cusip": "B"},
    ]
    result = compute_expected_loss(positions)
    # AAA: 500k * 0.0001 * 0.60 = 30
    # CCC: 500k * 0.20 * 0.60 = 60,000
    assert result["total_expected_loss"] == pytest.approx(60_030.0, abs=1.0)
    assert len(result["by_position"]) == 2


# ── compute_credit_var ───────────────────────────────────────────────


def test_credit_var_high_quality():
    """High quality (AAA) portfolio should have low VaR."""
    positions = [
        {"market_value": 1_000_000, "rating_numeric": 1, "seniority": "SENIOR_UNSECURED"},
    ]
    result = compute_credit_var(positions, confidence=0.99)
    assert result["credit_var"] > 0
    # AAA VaR should be small relative to portfolio size
    assert result["credit_var"] < 50_000


def test_credit_var_low_quality():
    """Low quality (CCC) portfolio should have much higher VaR."""
    positions = [
        {"market_value": 1_000_000, "rating_numeric": 18, "seniority": "SENIOR_UNSECURED"},
    ]
    result = compute_credit_var(positions, confidence=0.99)
    assert result["credit_var"] > 100_000
    assert result["confidence"] == 0.99
    assert result["horizon_days"] == 250


def test_credit_var_confidence_levels():
    """Higher confidence should produce larger VaR."""
    positions = [
        {"market_value": 1_000_000, "rating_numeric": 12, "seniority": "SENIOR_UNSECURED"},
    ]
    var_95 = compute_credit_var(positions, confidence=0.95)
    var_99 = compute_credit_var(positions, confidence=0.99)
    assert var_99["credit_var"] > var_95["credit_var"]


# ── compute_single_bond_risk ─────────────────────────────────────────


def test_single_bond_risk_all_metrics():
    """Verify all metrics are returned with correct types."""
    result = compute_single_bond_risk(
        market_value=100.0,
        modified_duration=7.5,
        convexity=65.0,
        spread_duration=7.5,
        rating_numeric=9,
        seniority="SENIOR_UNSECURED",
    )
    assert "dv01" in result
    assert "rate_pnl_100bps" in result
    assert "spread_pnl_100bps" in result
    assert "expected_loss" in result
    assert "pd_1y" in result
    assert "lgd" in result

    # DV01 = 100 * 7.5 * 0.0001 = 0.075
    assert result["dv01"] == pytest.approx(0.075, abs=0.001)

    # Rate P&L for +100 bps should be negative (long bond loses on rate rise)
    assert result["rate_pnl_100bps"] < 0

    # Spread P&L for +100 bps should be negative
    assert result["spread_pnl_100bps"] < 0

    # PD and LGD should be reasonable for BBB
    assert result["pd_1y"] == PD_BY_RATING[9]
    assert result["lgd"] == 1.0 - RECOVERY_RATES["SENIOR_UNSECURED"]


def test_single_bond_risk_seniority_matters():
    """Senior secured bonds should have lower LGD than subordinated."""
    secured = compute_single_bond_risk(
        market_value=100.0, modified_duration=5.0, convexity=30.0,
        spread_duration=5.0, rating_numeric=9, seniority="SENIOR_SECURED",
    )
    subordinated = compute_single_bond_risk(
        market_value=100.0, modified_duration=5.0, convexity=30.0,
        spread_duration=5.0, rating_numeric=9, seniority="SUBORDINATED",
    )
    assert secured["lgd"] < subordinated["lgd"]
    assert secured["expected_loss"] < subordinated["expected_loss"]
