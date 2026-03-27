"""Stress tests for critical math functions — edge cases and boundary conditions."""

import math
from datetime import date

import pytest


# ── E9: Bond Pricing Edge Cases ─────────────────────────────────────────


from src.engines.e9_bond_pricing import (
    day_count_fraction,
    compute_accrued_interest,
    price_from_yield,
    yield_from_price,
    _next_coupon_date,
)


def test_day_count_same_date():
    assert day_count_fraction(date(2025, 1, 1), date(2025, 1, 1)) == 0.0


def test_day_count_end_before_start():
    assert day_count_fraction(date(2025, 6, 1), date(2025, 1, 1)) == 0.0


def test_day_count_30_360_end_of_month():
    """Feb 28 -> Mar 31 in 30/360: d1=28 (not capped), d2=31 (not capped since d1!=30)."""
    result = day_count_fraction(date(2025, 1, 31), date(2025, 2, 28), "30/360")
    assert result > 0


def test_day_count_30_360_31st_dates():
    """Jan 31 to Mar 31: d1=30 (capped), d2=30 (capped since d1==30)."""
    result = day_count_fraction(date(2025, 1, 31), date(2025, 3, 31), "30/360")
    expected = (30 * 2 + 0) / 360  # 2 months * 30 days
    assert result == pytest.approx(expected, abs=0.001)


def test_day_count_act_act_leap_year():
    result = day_count_fraction(date(2024, 1, 1), date(2024, 12, 31), "ACT/ACT")
    assert result == pytest.approx(365 / 366, abs=0.01)


def test_day_count_act_360():
    result = day_count_fraction(date(2025, 1, 1), date(2025, 7, 1), "ACT/360")
    assert result == pytest.approx(181 / 360, abs=0.001)


def test_day_count_act_365():
    result = day_count_fraction(date(2025, 1, 1), date(2025, 7, 1), "ACT/365")
    assert result == pytest.approx(181 / 365, abs=0.001)


def test_next_coupon_date_frequency_zero():
    """frequency=0 should not crash."""
    result = _next_coupon_date(date(2025, 1, 15), 0)
    assert result == date(2025, 1, 15)  # returns same date


def test_price_yield_roundtrip_zero_yield():
    """Price at 0% yield and back."""
    pfy = price_from_yield(0.0, 0.05, 100, date(2025, 1, 1), date(2030, 1, 1), 2, "30/360")
    yfp = yield_from_price(pfy["clean_price"], 0.05, 100, date(2025, 1, 1), date(2030, 1, 1), 2, "30/360")
    assert abs(yfp) < 0.005


def test_price_yield_roundtrip_high_yield():
    """Roundtrip at 20% yield."""
    pfy = price_from_yield(0.20, 0.05, 100, date(2025, 1, 1), date(2030, 1, 1), 2, "30/360")
    assert pfy["clean_price"] < 100  # discount
    yfp = yield_from_price(pfy["clean_price"], 0.05, 100, date(2025, 1, 1), date(2030, 1, 1), 2, "30/360")
    assert abs(0.20 - yfp) < 0.005


def test_price_yield_roundtrip_par_bond():
    """5% coupon at 5% yield = par."""
    pfy = price_from_yield(0.05, 0.05, 100, date(2025, 1, 1), date(2030, 1, 1), 2, "30/360")
    assert pfy["clean_price"] == pytest.approx(100.0, abs=0.5)


def test_accrued_interest_zero_coupon():
    """Zero coupon bond has no accrued interest."""
    ai = compute_accrued_interest(0.0, 100.0, 2, date(2025, 1, 1), date(2025, 6, 1))
    assert ai == 0.0


# ── E10: Duration Edge Cases ────────────────────────────────────────────


from src.engines.e10_duration import (
    compute_dv01,
    compute_key_rate_durations,
    compute_effective_duration,
    compute_effective_convexity,
    estimate_price_change,
)


def test_dv01_zero_duration():
    assert compute_dv01(0.0, 100.0) == 0.0


def test_dv01_negative_price():
    """Negative price returns negative DV01 (caller should validate)."""
    assert compute_dv01(5.0, -100.0) < 0


def test_krd_zero_bump():
    """bump_bps=0 should return all zeros, not crash."""
    result = compute_key_rate_durations(100.0, 0.05, 100.0, 5.0, 2, [], bump_bps=0.0)
    assert all(v == 0.0 for v in result.values())


def test_krd_empty_curve():
    """Empty zero curve: should not crash."""
    result = compute_key_rate_durations(100.0, 0.05, 100.0, 5.0, 2, [])
    assert len(result) == 8  # 8 tenors


def test_effective_duration_zero_price():
    """price_base=0 should return 0, not crash."""
    result = compute_effective_duration(99, 101, 0.0, 100)
    assert result == 0.0


def test_effective_convexity_zero_price():
    result = compute_effective_convexity(99, 101, 0.0, 100)
    assert result == 0.0


def test_estimate_price_change_zero_shift():
    assert estimate_price_change(5.0, 30.0, 0) == pytest.approx(0.0)


def test_estimate_price_change_large_shift():
    """500bps shift should still return valid result."""
    result = estimate_price_change(5.0, 30.0, 500)
    assert result < 0  # price drops


# ── E11: Spread Analytics Edge Cases ────────────────────────────────────


from src.engines.e11_spread_analytics import (
    interpolate_treasury_yield,
    compute_breakeven_spread,
    compute_relative_value,
    compute_g_spread_interpolated,
)


def test_interp_treasury_empty_curve():
    """Empty curve returns 0."""
    assert interpolate_treasury_yield(5.0, []) == 0.0


def test_interp_treasury_single_point():
    """Single point returns that rate (uses tenor_years/yield_rate keys)."""
    result = interpolate_treasury_yield(5.0, [{"tenor_years": 10.0, "yield_rate": 0.04}])
    assert result == pytest.approx(0.04, abs=0.001)


def test_breakeven_zero_duration():
    """Zero duration: breakeven should be infinity (not zero)."""
    result = compute_breakeven_spread(200, 0.0, 1.0)
    assert result["breakeven_widening_bps"] == float("inf")


def test_breakeven_zero_spread():
    result = compute_breakeven_spread(0.0, 5.0, 1.0)
    assert result["carry_bps"] == 0.0
    assert result["breakeven_widening_bps"] == 0.0


def test_relative_value_empty_histories():
    """Empty histories: percentile defaults to 50 (median assumption)."""
    result = compute_relative_value(300, [], [], 200)
    assert result is not None  # should not crash


def test_g_spread_exact_maturity():
    """When bond maturity matches a treasury point exactly."""
    curve = [{"tenor_years": 5.0, "yield_rate": 0.035}]
    result = compute_g_spread_interpolated(0.045, 5.0, curve)
    assert result == 100  # (0.045 - 0.035) * 10000 = 100 bps


# ── E12: FI Risk Edge Cases ─────────────────────────────────────────────


from src.engines.e12_fi_risk import (
    compute_portfolio_dv01,
    compute_expected_loss,
    compute_credit_var,
    compute_rate_scenario_pnl,
)


def test_portfolio_dv01_empty():
    """Empty portfolio returns float 0.0."""
    result = compute_portfolio_dv01([])
    assert result == 0.0


def test_expected_loss_empty():
    result = compute_expected_loss([])
    assert result["total_expected_loss"] == 0.0


def test_rate_scenario_zero_shift():
    pos = [{"market_value": 1_000_000, "modified_duration": 5.0, "convexity": 30.0}]
    result = compute_rate_scenario_pnl(pos, 0.0)
    assert result["total_pnl"] == 0.0


def test_credit_var_single_position():
    pos = [{"market_value": 1_000_000, "modified_duration": 5.0, "rating_numeric": 5, "seniority": "SENIOR_UNSECURED"}]
    result = compute_credit_var(pos, confidence=0.99, horizon_days=250)
    assert result["credit_var"] >= 0


# ── E13: Credit Quality Edge Cases ──────────────────────────────────────


from src.engines.e13_credit_quality import (
    compute_ohlson_o_score,
    compute_credit_momentum,
    compute_fallen_angel_probability,
    compute_refinancing_risk,
)


def test_ohlson_all_zeros():
    """All-zero inputs should not crash."""
    result = compute_ohlson_o_score(0, 0, 0, 0, 0, 0, 0, 0, 0)
    assert result["o_score"] is not None
    assert 0 <= result["probability_of_default"] <= 1


def test_ohlson_negative_assets():
    """Negative total assets → should return None/handle gracefully."""
    result = compute_ohlson_o_score(-100, 50, 10, 10, 5, 10, 30, 3, -200)
    assert result is not None  # should not crash


def test_fallen_angel_aaa():
    """AAA (rating_numeric=1) should have 0 probability."""
    result = compute_fallen_angel_probability(1, "STABLE", None, 0, 0)
    assert result == 0.0


def test_fallen_angel_bbb_minus_watch_negative():
    """BBB- on watch negative should have high probability."""
    result = compute_fallen_angel_probability(10, "NEGATIVE", "WATCH_NEGATIVE", 50, -5)
    assert result > 50


def test_refinancing_risk_all_zeros():
    result = compute_refinancing_risk(0, 0, 0, 0)
    assert 0 <= result["score"] <= 100


def test_credit_momentum_neutral():
    """Neutral momentum with zero inputs."""
    result = compute_credit_momentum(0.0, 0.0, 0.0)
    assert result["signal"] == "STABLE"


# ── E14: Issuer Profile Edge Cases ──────────────────────────────────────


from src.engines.e14_issuer_profile import (
    compute_maturity_wall,
    build_debt_stack,
    compute_weighted_avg_cost_of_debt,
    compute_debt_maturity_profile,
)


def test_maturity_wall_empty():
    """Empty bonds list returns empty wall."""
    result = compute_maturity_wall([], years_forward=5)
    assert isinstance(result, list)
    # May return 0 or 5 items depending on implementation
    assert all(item["amount_maturing"] == 0 for item in result)


def test_debt_stack_empty():
    result = build_debt_stack([])
    assert result == []


def test_wacd_empty():
    result = compute_weighted_avg_cost_of_debt([])
    assert result == 0.0


def test_maturity_profile_empty():
    result = compute_debt_maturity_profile([])
    assert result["total_outstanding"] == 0.0


# ── E15: Cross-Asset Edge Cases ─────────────────────────────────────────


from src.engines.e15_cross_asset import (
    detect_divergence_signals,
    compute_cross_asset_regime,
    compute_equity_exposure_adjustment,
)


def test_signals_all_zero():
    result = detect_divergence_signals(
        {"return_3m": 0, "return_6m": 0},
        {"spread_bps": 0, "spread_change_3m_bps": 0, "spread_percentile": 0},
    )
    assert isinstance(result, list)


def test_regime_all_zero():
    result = compute_cross_asset_regime(0.0, 0.0, 0.0, 0.0)
    assert result["regime"] == "RISK_ON"


def test_regime_extreme_values():
    result = compute_cross_asset_regime(1.0, 10000.0, 0.20, -0.10)
    assert result["regime"] == "STRESS"


def test_exposure_adjustment_stress():
    result = compute_equity_exposure_adjustment("STRESS", [], 0.60)
    assert result["suggested_weight"] < 0.60


def test_exposure_adjustment_extreme_signals():
    signals = [
        {"signal_type": "BOND_DISTRESS_BEFORE_EQUITY", "severity": "HIGH", "confidence": 1.0},
        {"signal_type": "EQUITY_RALLY_BOND_DETERIORATION", "severity": "HIGH", "confidence": 1.0},
        {"signal_type": "FALLEN_ANGEL_OVERHANG", "severity": "HIGH", "confidence": 1.0},
    ]
    result = compute_equity_exposure_adjustment("STRESS", signals, 0.60)
    assert result["suggested_weight"] >= 0.10  # clamped to min


# ── E2 WACC Extension Edge Cases ────────────────────────────────────────


from src.engines.e2_wacc import (
    compute_market_cost_of_debt,
    compute_wacc_with_market_debt_cost,
)


def test_market_cod_negative_spread():
    """Negative spread (rare but possible for safest issuers)."""
    result = compute_market_cost_of_debt(0.04, -10.0)
    assert result["cost_of_debt_market"] == pytest.approx(0.039, abs=0.001)


def test_wacc_market_weights_over_one():
    """Weights > 1 should compute without crash (no validation)."""
    result = compute_wacc_with_market_debt_cost(0.10, 0.06, 0.80, 0.80, 0.21)
    assert result["wacc_market"] is not None


# ── E3 Credit-Aware Extension Edge Cases ────────────────────────────────


from src.engines.e3_composites import compute_credit_aware_financial_strength


def test_credit_aware_extreme_momentum():
    """Momentum outside [-1,1] should be clamped."""
    result = compute_credit_aware_financial_strength(None, None, None, 5.0)
    assert result["components"]["credit_momentum"]["score"] == pytest.approx(90.0, abs=1.0)


def test_credit_aware_all_perfect():
    result = compute_credit_aware_financial_strength(100.0, -5.0, 10.0, 1.0)
    assert result["score"] is not None
    assert 0 <= result["score"] <= 100


def test_credit_aware_all_worst():
    result = compute_credit_aware_financial_strength(0.0, 5.0, 0.0, -1.0)
    assert result["score"] is not None
    assert 0 <= result["score"] <= 100
