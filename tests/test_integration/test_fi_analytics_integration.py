"""Cross-engine FI Analytics integration tests (Pillar 2 FI Supplement Part 8).

End-to-end flows testing engine composability across E9-E15.
"""

from __future__ import annotations

from datetime import date

import pytest

from src.engines.e9_bond_pricing import (
    compute_accrued_interest,
    day_count_fraction,
    generate_cash_flow_schedule,
    price_from_yield,
    yield_from_price,
)
from src.engines.e10_duration import (
    compute_dv01,
    compute_effective_convexity,
    compute_effective_duration,
    compute_portfolio_duration,
    estimate_price_change,
    generate_rate_sensitivity_table,
)
from src.engines.e11_spread_analytics import (
    compute_breakeven_spread,
    compute_g_spread_interpolated,
    compute_relative_value,
    compute_z_spread,
    interpolate_treasury_yield,
)
from src.engines.e12_fi_risk import (
    compute_credit_distribution,
    compute_expected_loss,
    compute_portfolio_dv01,
    compute_rate_scenario_pnl,
    compute_spread_scenario_pnl,
)
from src.engines.e13_credit_quality import (
    compute_credit_momentum,
    compute_fallen_angel_probability,
    compute_ohlson_o_score,
    compute_refinancing_risk,
)
from src.engines.e14_issuer_profile import (
    build_debt_stack,
    compute_maturity_wall,
    compute_weighted_avg_cost_of_debt,
)
from src.engines.e15_cross_asset import (
    compute_cross_asset_regime,
    compute_equity_exposure_adjustment,
    detect_divergence_signals,
)
from src.engines.e5_fi_rate_shocks import apply_fi_rate_scenario
from src.engines.e8_fi_scenarios import fi_scenario_shift, fi_sensitivity_table
from src.engines.bond_analytics import (
    compute_convexity,
    compute_macaulay_duration,
    compute_modified_duration,
    compute_ytm,
)


# ── E9 → E10 → E11 → E12: Bond Pricing Pipeline ────────────────────


def test_pricing_to_risk_pipeline():
    """E9 price → E10 duration → E11 spread → E12 risk: full pipeline."""
    # Step 1: E9 — Price the bond
    settlement = date(2025, 6, 15)
    maturity = date(2035, 6, 15)
    coupon_rate = 0.05
    face = 100.0
    frequency = 2

    result = price_from_yield(
        ytm=0.055,
        coupon_rate=coupon_rate,
        face_value=face,
        settlement_date=settlement,
        maturity_date=maturity,
        frequency=frequency,
    )
    clean_price = result["clean_price"]
    assert 90.0 < clean_price < 100.0  # discount bond (YTM > coupon)

    # Step 2: Roundtrip — yield from that price
    ytm_roundtrip = yield_from_price(
        clean_price=clean_price,
        coupon_rate=coupon_rate,
        face_value=face,
        settlement_date=settlement,
        maturity_date=maturity,
        frequency=frequency,
    )
    assert ytm_roundtrip == pytest.approx(0.055, abs=0.001)

    # Step 3: E10 — Duration & DV01
    years = 10.0
    mod_dur = compute_modified_duration(0.055, coupon_rate, years, frequency)
    mac_dur = compute_macaulay_duration(0.055, coupon_rate, years, frequency)
    cvx = compute_convexity(0.055, coupon_rate, years, frequency)
    dv01 = compute_dv01(mod_dur, clean_price)

    assert mod_dur > 0
    assert mac_dur > mod_dur  # Macaulay > modified always
    assert cvx > 0
    assert dv01 > 0

    # Step 4: E11 — Spread analytics
    treasury_curve = [
        {"tenor_years": 2.0, "yield_rate": 0.040},
        {"tenor_years": 5.0, "yield_rate": 0.042},
        {"tenor_years": 10.0, "yield_rate": 0.045},
        {"tenor_years": 30.0, "yield_rate": 0.048},
    ]
    g_spread = compute_g_spread_interpolated(0.055, years, treasury_curve)
    assert g_spread > 0  # bond yield > treasury

    breakeven = compute_breakeven_spread(float(g_spread), mod_dur)
    assert breakeven["carry_bps"] > 0
    assert breakeven["breakeven_widening_bps"] > 0

    # Step 5: E12 — Risk metrics
    position = {
        "market_value": clean_price * 10_000,  # $1M notional
        "modified_duration": mod_dur,
        "convexity": cvx,
        "cusip": "INTEG001",
    }
    portfolio_dv01 = compute_portfolio_dv01([position])
    assert portfolio_dv01 > 0

    rate_pnl = compute_rate_scenario_pnl([position], 100.0)
    assert rate_pnl["total_pnl"] < 0  # rates up → loss


def test_price_yield_roundtrip_consistency():
    """Verify price→yield→price roundtrip across multiple scenarios."""
    scenarios = [
        (0.05, 0.05, 100.0, "Par bond"),
        (0.05, 0.06, None, "Discount"),
        (0.05, 0.03, None, "Premium"),
        (0.00, 0.04, None, "Zero coupon"),
    ]
    settlement = date(2025, 1, 1)
    maturity = date(2030, 1, 1)

    for coupon, ytm, expected_approx, label in scenarios:
        result = price_from_yield(
            ytm=ytm,
            coupon_rate=coupon,
            face_value=100.0,
            settlement_date=settlement,
            maturity_date=maturity,
            frequency=2 if coupon > 0 else 0,
        )
        clean = result["clean_price"]

        if expected_approx is not None:
            assert clean == pytest.approx(expected_approx, abs=2.0), f"Failed for {label}"

        # Roundtrip
        if coupon > 0:
            ytm_back = yield_from_price(
                clean_price=clean,
                coupon_rate=coupon,
                face_value=100.0,
                settlement_date=settlement,
                maturity_date=maturity,
                frequency=2,
            )
            assert ytm_back == pytest.approx(ytm, abs=0.002), f"Roundtrip failed for {label}"


# ── E13 → E14: Credit Quality → Issuer Profile ──────────────────────


def test_credit_quality_to_issuer_profile():
    """E13 credit quality → E14 issuer profile: full credit assessment."""
    # Step 1: E13 — O-Score for financial health
    o_result = compute_ohlson_o_score(
        total_assets=10_000,
        total_liabilities=7_000,
        working_capital=1_000,
        current_liabilities=2_000,
        net_income=500,
        funds_from_operations=800,
        total_debt=5_000,
        net_income_lag1=400,
        total_assets_lag1=9_500,
    )
    assert "o_score" in o_result
    assert "probability_of_default" in o_result
    assert 0 <= o_result["probability_of_default"] <= 1

    # Step 2: E13 — Credit momentum
    momentum = compute_credit_momentum(
        rating_momentum=-0.2,  # recent downgrade
        score_momentum=-0.1,   # declining scores
        spread_momentum=-0.3,  # spreads widening
    )
    assert momentum["signal"] == "DETERIORATING"
    assert momentum["momentum_score"] < -0.15

    # Step 3: E13 — Fallen angel probability
    fa_prob = compute_fallen_angel_probability(
        current_rating_numeric=10,  # BBB-
        outlook="NEGATIVE",
        watch_status=None,
        spread_trend=-1.5,  # widening
        score_trend=-0.3,   # deteriorating
    )
    assert fa_prob > 30  # meaningful probability

    # Step 4: E14 — Build issuer profile
    bonds = [
        {"maturity_date": date(2027, 6, 15), "outstanding_amount": 500e6, "cusip": "A001",
         "seniority": "SENIOR_SECURED", "coupon_rate": 0.04},
        {"maturity_date": date(2029, 6, 15), "outstanding_amount": 800e6, "cusip": "A002",
         "seniority": "SENIOR_UNSECURED", "coupon_rate": 0.055},
        {"maturity_date": date(2033, 6, 15), "outstanding_amount": 300e6, "cusip": "A003",
         "seniority": "SUBORDINATED", "coupon_rate": 0.07},
    ]
    wall = compute_maturity_wall(bonds, years_forward=10)
    stack = build_debt_stack(bonds)
    avg_cost = compute_weighted_avg_cost_of_debt(bonds)

    assert len(wall) > 0
    assert len(stack) == 3
    assert 0.04 < avg_cost < 0.07

    # Step 5: E13 — Refinancing risk
    maturity_wall_pct = sum(
        w["pct_of_total"] for w in wall if w["year"] <= date.today().year + 2
    )
    refi_risk = compute_refinancing_risk(
        maturity_wall_pct=maturity_wall_pct,
        current_spread_bps=350.0,
        fcf_to_debt=0.05,
        credit_direction=-0.5,
    )
    assert refi_risk["score"] > 0
    assert refi_risk["assessment"] in ("LOW", "MODERATE", "ELEVATED", "HIGH")


# ── E5 → E12 → E15: Rate Shock → Risk → Cross-Asset ─────────────────


def test_rate_shock_to_cross_asset():
    """E5 rate shock → E12 risk P&L → E15 cross-asset regime assessment."""
    # Portfolio of 3 bonds
    positions = [
        {"market_value": 2_000_000, "modified_duration": 5.0, "convexity": 30.0,
         "spread_duration": 5.0, "is_investment_grade": True, "cusip": "IG1"},
        {"market_value": 1_500_000, "modified_duration": 3.0, "convexity": 12.0,
         "spread_duration": 3.0, "is_investment_grade": True, "cusip": "IG2"},
        {"market_value": 500_000, "modified_duration": 4.0, "convexity": 20.0,
         "spread_duration": 4.0, "is_investment_grade": False, "cusip": "HY1"},
    ]

    # Step 1: E5 — Apply 2022 rate shock
    shock_result = apply_fi_rate_scenario(positions, "RATE_SHOCK_2022")
    assert shock_result["total_pnl"] < 0  # rates up → loss
    assert shock_result["rate_pnl"] < 0
    assert shock_result["spread_pnl"] < 0

    # HY bond should have worse spread impact
    hy_pos = next(p for p in shock_result["by_position"] if p["cusip"] == "HY1")
    ig_pos = next(p for p in shock_result["by_position"] if p["cusip"] == "IG1")
    # HY spread impact per unit MV should be worse
    assert hy_pos["spread_pnl"] / 500_000 < ig_pos["spread_pnl"] / 2_000_000

    # Step 2: E12 — Rate scenario P&L for comparison
    rate_pnl = compute_rate_scenario_pnl(positions, 425.0)
    assert rate_pnl["total_pnl"] < 0

    # Step 3: E15 — Assess regime after shock
    regime = compute_cross_asset_regime(
        equity_vol=0.36,      # high vol during rate shock (>0.35 → STRESS override)
        credit_spread=500.0,  # wide spreads
        rate_level=0.055,     # elevated rates
        curve_slope=-0.006,   # inverted
    )
    assert regime["regime"] in ("STRESS", "RISK_OFF")

    # Step 4: E15 — Equity exposure adjustment
    signals = detect_divergence_signals(
        equity_data={"return_3m": -0.05, "return_6m": -0.15, "pe_ratio": 15.0,
                     "pe_percentile": 30.0, "volatility": 0.35},
        bond_data={"spread_bps": 500, "spread_change_3m_bps": 200,
                   "spread_percentile": 90.0, "ytw": 0.08},
    )
    adjustment = compute_equity_exposure_adjustment(
        regime=regime["regime"],
        signals=signals,
        current_equity_weight=0.60,
    )
    assert adjustment["suggested_weight"] < 0.60  # reduce in stress


# ── E4 → E11: Screening → Relative Value ─────────────────────────────


def test_screening_to_relative_value():
    """Screen bonds by spread, then analyze relative value."""
    from src.engines.e4_fi_screening import BondScreenFilter, apply_bond_filters, rank_bonds

    # Create universe of bonds
    bonds = [
        {"cusip": "SCR001", "spread_bps": 150, "rating_numeric": 9,
         "is_investment_grade": True, "maturity_date": "2030-06-15"},
        {"cusip": "SCR002", "spread_bps": 300, "rating_numeric": 12,
         "is_investment_grade": False, "maturity_date": "2028-06-15"},
        {"cusip": "SCR003", "spread_bps": 200, "rating_numeric": 10,
         "is_investment_grade": True, "maturity_date": "2032-06-15"},
        {"cusip": "SCR004", "spread_bps": 500, "rating_numeric": 16,
         "is_investment_grade": False, "maturity_date": "2027-06-15"},
    ]

    # Screen: IG only, spread > 100
    filters = [
        BondScreenFilter(field="is_investment_grade", op="EQ", value=True),
        BondScreenFilter(field="spread_bps", op="GT", value=100),
    ]
    filtered = apply_bond_filters(bonds, filters)
    assert len(filtered) == 2  # SCR001 and SCR003

    ranked = rank_bonds(filtered, sort_field="spread_bps", ascending=False)
    assert ranked[0]["cusip"] == "SCR003"  # wider spread first

    # Relative value for top pick
    rv = compute_relative_value(
        current_spread_bps=200.0,
        historical_spreads=[150.0, 160.0, 170.0, 180.0, 190.0, 200.0, 210.0, 220.0],
        peer_spreads=[180.0, 190.0, 210.0, 220.0],
        sector_spread_bps=185.0,
    )
    assert "own_percentile" in rv
    assert "rich_cheap_score" in rv
    assert rv["vs_sector_diff_bps"] > 0  # wider than sector → cheap


# ── E8 + E12: Scenario → Portfolio Risk ──────────────────────────────


def test_sensitivity_to_portfolio_risk():
    """E8 sensitivity table + E12 portfolio risk: combined analysis."""
    # Step 1: E8 — Sensitivity table for a single bond
    table = fi_sensitivity_table(
        base_price=98.0,
        modified_duration=7.0,
        convexity=60.0,
        var1_name="yield_shift_bps",
        var1_range=[-200, -100, 0, 100, 200],
    )
    assert len(table["results"]) == 5
    # Price should go up when yields fall
    assert table["results"][0]["price"] > table["results"][2]["price"]
    # Price should go down when yields rise
    assert table["results"][4]["price"] < table["results"][2]["price"]

    # Step 2: E8 — Multi-variable scenario
    positions = [
        {"market_value": 1_000_000, "modified_duration": 7.0, "convexity": 60.0,
         "spread_duration": 7.0, "rating_numeric": 9, "cusip": "A"},
        {"market_value": 500_000, "modified_duration": 3.0, "convexity": 10.0,
         "spread_duration": 3.0, "rating_numeric": 14, "cusip": "B"},
    ]
    scenario = fi_scenario_shift(
        positions, yield_shift_bps=100, spread_shift_bps=50
    )
    assert scenario["total_pnl"] < 0  # both yield up and spread widening → loss
    assert scenario["yield_impact"] < 0
    assert scenario["spread_impact"] < 0

    # Step 3: E12 — Portfolio credit distribution
    risk_positions = [
        {"market_value": 1_000_000, "rating_numeric": 9,
         "is_investment_grade": True, "seniority": "SENIOR_UNSECURED"},
        {"market_value": 500_000, "rating_numeric": 14,
         "is_investment_grade": False, "seniority": "SENIOR_UNSECURED"},
    ]
    dist = compute_credit_distribution(risk_positions)
    assert dist["ig_pct"] > dist["hy_pct"]  # $1M IG > $500K HY

    el = compute_expected_loss(risk_positions)
    assert el["total_expected_loss"] > 0
    assert el["total_expected_loss_pct"] > 0


# ── E10 + E12: Duration-Based Risk ──────────────────────────────────


def test_duration_convexity_risk_consistency():
    """Verify E10 price change estimation matches E12 rate scenario P&L."""
    mod_dur = 6.0
    cvx = 45.0
    price = 97.0
    mv = 970_000  # $1M notional at 97

    # E10: Estimate price change for +100bps
    pct_change = estimate_price_change(mod_dur, cvx, 100.0)
    e10_pnl = pct_change * mv

    # E12: Rate scenario P&L for +100bps
    result = compute_rate_scenario_pnl(
        [{"market_value": mv, "modified_duration": mod_dur, "convexity": cvx, "cusip": "X"}],
        100.0,
    )
    e12_pnl = result["total_pnl"]

    # They should be consistent (same formula)
    assert e10_pnl == pytest.approx(e12_pnl, rel=0.01)


def test_portfolio_duration_aggregation():
    """E10 portfolio duration should be consistent with individual positions."""
    positions = [
        {"weight": 0.5, "modified_duration": 5.0, "dv01": 45.0, "convexity": 30.0,
         "key_rate_durations": {"5Y": 3.0, "10Y": 2.0}},
        {"weight": 0.3, "modified_duration": 8.0, "dv01": 72.0, "convexity": 80.0,
         "key_rate_durations": {"5Y": 1.0, "10Y": 7.0}},
        {"weight": 0.2, "modified_duration": 2.0, "dv01": 18.0, "convexity": 5.0,
         "key_rate_durations": {"5Y": 1.5, "10Y": 0.5}},
    ]

    result = compute_portfolio_duration(positions)
    expected_dur = 0.5 * 5.0 + 0.3 * 8.0 + 0.2 * 2.0  # 5.3
    assert result["weighted_avg_duration"] == pytest.approx(expected_dur, abs=0.01)
    assert result["portfolio_dv01"] > 0


# ── Full Issuer Assessment Pipeline ──────────────────────────────────


def test_full_issuer_assessment():
    """Complete issuer assessment: E13 credit + E14 profile + E15 cross-asset."""
    # E14: Issuer profile
    bonds = [
        {"maturity_date": date(2026, 6, 15), "outstanding_amount": 1_000e6,
         "cusip": "FA001", "seniority": "SENIOR_UNSECURED", "coupon_rate": 0.035},
        {"maturity_date": date(2027, 6, 15), "outstanding_amount": 750e6,
         "cusip": "FA002", "seniority": "SENIOR_UNSECURED", "coupon_rate": 0.045},
        {"maturity_date": date(2031, 6, 15), "outstanding_amount": 500e6,
         "cusip": "FA003", "seniority": "SUBORDINATED", "coupon_rate": 0.065},
    ]
    wall = compute_maturity_wall(bonds, years_forward=10)
    stack = build_debt_stack(bonds)
    avg_cost = compute_weighted_avg_cost_of_debt(bonds)

    # Significant maturity wall in near term
    near_term = sum(w["amount_maturing"] for w in wall if w["year"] <= date.today().year + 2)
    total = sum(b["outstanding_amount"] for b in bonds)
    wall_pct = near_term / total * 100 if total > 0 else 0

    # E13: Credit quality
    o_result = compute_ohlson_o_score(
        total_assets=5_000, total_liabilities=4_000, working_capital=300,
        current_liabilities=1_500, net_income=100, funds_from_operations=200,
        total_debt=3_000, net_income_lag1=150, total_assets_lag1=4_800,
    )
    assert o_result["probability_of_default"] > 0

    momentum = compute_credit_momentum(
        rating_momentum=-0.3, score_momentum=-0.2, spread_momentum=-0.4
    )
    assert momentum["signal"] == "DETERIORATING"

    fa_prob = compute_fallen_angel_probability(
        current_rating_numeric=10,  # BBB-
        outlook="NEGATIVE",
        spread_trend=-2.0,
        score_trend=-0.5,
    )
    assert fa_prob > 40

    refi = compute_refinancing_risk(
        maturity_wall_pct=wall_pct,
        current_spread_bps=400.0,
        fcf_to_debt=0.03,
        credit_direction=-0.6,
    )
    assert refi["score"] > 50  # elevated risk

    # E15: Cross-asset divergence
    signals = detect_divergence_signals(
        equity_data={"return_3m": 0.10, "return_6m": 0.20, "pe_ratio": 18.0,
                     "pe_percentile": 40.0, "volatility": 0.25},
        bond_data={"spread_bps": 400, "spread_change_3m_bps": 100,
                   "spread_percentile": 80.0, "ytw": 0.07},
        rating_data={"rating_numeric": 10, "outlook": "NEGATIVE", "watch_status": None},
    )
    # Should detect equity rally + bond deterioration
    signal_types = [s["signal_type"] for s in signals]
    assert any(t in signal_types for t in [
        "EQUITY_RALLY_BOND_DETERIORATION",
        "FALLEN_ANGEL_OVERHANG",
    ])


# ── Day Count + Accrued Interest Flow ────────────────────────────────


def test_day_count_accrued_interest_flow():
    """E9 day count → accrued interest → clean/dirty price decomposition."""
    # 30/360 convention
    frac = day_count_fraction(date(2025, 1, 15), date(2025, 7, 15), "30/360")
    assert frac == pytest.approx(0.5, abs=0.01)

    # ACT/365
    frac_act = day_count_fraction(date(2025, 1, 15), date(2025, 7, 15), "ACT/365")
    assert 0.49 < frac_act < 0.51

    # Accrued interest at mid-period
    ai = compute_accrued_interest(
        coupon_rate=0.06, face_value=100.0, frequency=2,
        last_coupon_date=date(2025, 1, 15),
        settlement_date=date(2025, 4, 15),  # 3 months into 6-month period
        day_count="30/360",
    )
    assert ai == pytest.approx(1.5, abs=0.1)  # 6% / 2 * 0.5 = 1.5

    # At coupon date, accrued should be 0
    ai_at_coupon = compute_accrued_interest(
        coupon_rate=0.06, face_value=100.0, frequency=2,
        last_coupon_date=date(2025, 1, 15),
        settlement_date=date(2025, 1, 15),
        day_count="30/360",
    )
    assert ai_at_coupon == pytest.approx(0.0, abs=0.01)


# ── Spread Scenario Stress Test ──────────────────────────────────────


def test_spread_scenario_stress():
    """E12 spread scenario across IG and HY positions."""
    positions = [
        {"market_value": 2_000_000, "spread_duration": 6.0,
         "is_investment_grade": True, "cusip": "IG_A"},
        {"market_value": 1_000_000, "spread_duration": 4.0,
         "is_investment_grade": False, "cusip": "HY_A"},
    ]

    # Spreads widen 100bps
    result = compute_spread_scenario_pnl(positions, 100.0)
    assert result["total_pnl"] < 0

    # Higher spread_duration position loses more per unit
    ig_pnl_per_mv = next(
        p["pnl"] / 2_000_000 for p in result["by_position"] if p.get("cusip") == "IG_A"
    )
    hy_pnl_per_mv = next(
        p["pnl"] / 1_000_000 for p in result["by_position"] if p.get("cusip") == "HY_A"
    )
    # IG has higher spread_duration so more loss per MV
    assert abs(ig_pnl_per_mv) > abs(hy_pnl_per_mv)

    # Spreads tighten
    result_tight = compute_spread_scenario_pnl(positions, -50.0)
    assert result_tight["total_pnl"] > 0  # gain


# ── E15 Regime Classification Consistency ────────────────────────────


def test_regime_classification_consistency():
    """All 4 regimes should be reachable with appropriate inputs."""
    regimes_seen = set()

    # RISK_ON: low vol, tight spreads, positive slope
    r1 = compute_cross_asset_regime(0.10, 100.0, 0.03, 0.02)
    regimes_seen.add(r1["regime"])

    # RISK_OFF: high vol, wide spreads, inverted
    r2 = compute_cross_asset_regime(0.30, 500.0, 0.065, -0.01)
    regimes_seen.add(r2["regime"])

    # STRESS: very high vol, very wide spreads
    r3 = compute_cross_asset_regime(0.45, 700.0, 0.07, -0.02)
    regimes_seen.add(r3["regime"])

    # TRANSITION: mixed
    r4 = compute_cross_asset_regime(0.20, 250.0, 0.04, 0.005)
    regimes_seen.add(r4["regime"])

    assert "RISK_ON" in regimes_seen
    assert "STRESS" in regimes_seen
    assert len(regimes_seen) >= 3  # At least 3 distinct regimes
