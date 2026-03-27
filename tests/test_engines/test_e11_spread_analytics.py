"""Tests for E11 Spread Analytics Engine (Pillar 2 FI Supplement Part 3)."""

import pytest

from src.engines.e11_spread_analytics import (
    compute_breakeven_spread,
    compute_g_spread_interpolated,
    compute_oas_simplified,
    compute_relative_value,
    compute_spread_duration,
    compute_z_spread,
    interpolate_treasury_yield,
)


# ── Treasury Curve fixture ───────────────────────────────────────────


TREASURY_CURVE = [
    {"tenor_years": 0.25, "yield_rate": 0.045},
    {"tenor_years": 0.5, "yield_rate": 0.046},
    {"tenor_years": 1.0, "yield_rate": 0.047},
    {"tenor_years": 2.0, "yield_rate": 0.044},
    {"tenor_years": 3.0, "yield_rate": 0.042},
    {"tenor_years": 5.0, "yield_rate": 0.040},
    {"tenor_years": 7.0, "yield_rate": 0.041},
    {"tenor_years": 10.0, "yield_rate": 0.043},
    {"tenor_years": 20.0, "yield_rate": 0.046},
    {"tenor_years": 30.0, "yield_rate": 0.047},
]

ZERO_CURVE = [
    {"tenor_years": 0.5, "zero_rate": 0.045},
    {"tenor_years": 1.0, "zero_rate": 0.046},
    {"tenor_years": 2.0, "zero_rate": 0.044},
    {"tenor_years": 3.0, "zero_rate": 0.042},
    {"tenor_years": 5.0, "zero_rate": 0.040},
    {"tenor_years": 7.0, "zero_rate": 0.041},
    {"tenor_years": 10.0, "zero_rate": 0.043},
]


# ── interpolate_treasury_yield ───────────────────────────────────────


def test_interpolate_exact_tenor():
    """Exact tenor match returns the yield at that point."""
    result = interpolate_treasury_yield(5.0, TREASURY_CURVE)
    assert result == pytest.approx(0.040, abs=1e-6)


def test_interpolate_between_tenors():
    """Interpolation between 5Y (4.0%) and 7Y (4.1%) at 6Y -> 4.05%."""
    result = interpolate_treasury_yield(6.0, TREASURY_CURVE)
    assert result == pytest.approx(0.0405, abs=1e-6)


def test_interpolate_before_first_tenor():
    """Before first tenor: flat extrapolation at first yield."""
    result = interpolate_treasury_yield(0.1, TREASURY_CURVE)
    assert result == pytest.approx(0.045, abs=1e-6)


def test_interpolate_after_last_tenor():
    """After last tenor: flat extrapolation at last yield."""
    result = interpolate_treasury_yield(40.0, TREASURY_CURVE)
    assert result == pytest.approx(0.047, abs=1e-6)


# ── compute_g_spread_interpolated ────────────────────────────────────


def test_g_spread_interpolated_known():
    """Bond YTM=5.5%, 10Y maturity, treasury 10Y=4.3% -> ~120 bps."""
    spread = compute_g_spread_interpolated(0.055, 10.0, TREASURY_CURVE)
    assert spread == 120


def test_g_spread_interpolated_between_tenors():
    """Bond at 6Y maturity: treasury ~ 4.05%, YTM 5.05% -> 100 bps."""
    spread = compute_g_spread_interpolated(0.0505, 6.0, TREASURY_CURVE)
    assert spread == 100


# ── compute_z_spread ─────────────────────────────────────────────────


def test_z_spread_par_bond():
    """Par bond priced at 100 with cash flows matching zero curve -> ~0 spread."""
    # 5Y bond, 4% coupon semi-annual, priced at par
    # If zero rates are ~4%, a par bond priced at 100 should have near-zero spread
    flat_curve = [
        {"tenor_years": 0.5, "zero_rate": 0.04},
        {"tenor_years": 1.0, "zero_rate": 0.04},
        {"tenor_years": 1.5, "zero_rate": 0.04},
        {"tenor_years": 2.0, "zero_rate": 0.04},
        {"tenor_years": 2.5, "zero_rate": 0.04},
        {"tenor_years": 3.0, "zero_rate": 0.04},
        {"tenor_years": 3.5, "zero_rate": 0.04},
        {"tenor_years": 4.0, "zero_rate": 0.04},
        {"tenor_years": 4.5, "zero_rate": 0.04},
        {"tenor_years": 5.0, "zero_rate": 0.04},
    ]
    # Build cash flows for 4% semi-annual bond
    cash_flows = []
    for i in range(1, 11):
        t = i * 0.5
        amt = 2.0  # 4% / 2 * 100
        if i == 10:
            amt += 100.0  # final principal
        cash_flows.append({"years": t, "amount": amt})

    z = compute_z_spread(cash_flows, 100.0, flat_curve)
    # Should be close to 0 (within a few bps tolerance)
    assert abs(z) <= 5


def test_z_spread_discount_bond():
    """Discount bond (price < par) should have positive Z-spread."""
    flat_curve = [
        {"tenor_years": 0.5, "zero_rate": 0.04},
        {"tenor_years": 1.0, "zero_rate": 0.04},
        {"tenor_years": 2.0, "zero_rate": 0.04},
        {"tenor_years": 3.0, "zero_rate": 0.04},
        {"tenor_years": 5.0, "zero_rate": 0.04},
    ]
    # 5Y bond, 4% annual coupon, priced at 95 (discount)
    cash_flows = [
        {"years": 1.0, "amount": 4.0},
        {"years": 2.0, "amount": 4.0},
        {"years": 3.0, "amount": 4.0},
        {"years": 4.0, "amount": 4.0},
        {"years": 5.0, "amount": 104.0},
    ]
    z = compute_z_spread(cash_flows, 95.0, flat_curve)
    assert z > 0


def test_z_spread_premium_bond():
    """Premium bond (price > par) should have negative Z-spread."""
    flat_curve = [
        {"tenor_years": 0.5, "zero_rate": 0.04},
        {"tenor_years": 1.0, "zero_rate": 0.04},
        {"tenor_years": 2.0, "zero_rate": 0.04},
        {"tenor_years": 3.0, "zero_rate": 0.04},
        {"tenor_years": 5.0, "zero_rate": 0.04},
    ]
    # 5Y bond, 4% annual coupon, priced at 105 (premium)
    cash_flows = [
        {"years": 1.0, "amount": 4.0},
        {"years": 2.0, "amount": 4.0},
        {"years": 3.0, "amount": 4.0},
        {"years": 4.0, "amount": 4.0},
        {"years": 5.0, "amount": 104.0},
    ]
    z = compute_z_spread(cash_flows, 105.0, flat_curve)
    assert z < 0


def test_z_spread_convergence():
    """Z-spread should converge for a well-formed problem: discount bond with known spread."""
    # We know that a 100bps spread over a flat 3% curve should produce a specific price.
    # Let's test the reverse: given that price, recover ~100 bps.
    flat_curve = [
        {"tenor_years": 1.0, "zero_rate": 0.03},
        {"tenor_years": 2.0, "zero_rate": 0.03},
        {"tenor_years": 3.0, "zero_rate": 0.03},
    ]
    # 3Y bond, 5% annual coupon
    # PV with spread=100bps (0.01):
    # CF1=5 / (1.04)^1 + CF2=5 / (1.04)^2 + CF3=105 / (1.04)^3
    pv = 5 / 1.04 + 5 / 1.04**2 + 105 / 1.04**3
    z = compute_z_spread(
        [
            {"years": 1.0, "amount": 5.0},
            {"years": 2.0, "amount": 5.0},
            {"years": 3.0, "amount": 105.0},
        ],
        pv,
        flat_curve,
    )
    assert z == pytest.approx(100, abs=2)


# ── compute_oas_simplified ───────────────────────────────────────────


def test_oas_non_callable():
    """Non-callable bond: OAS = Z-spread (option cost = 0)."""
    assert compute_oas_simplified(150, option_cost_bps=0) == 150


def test_oas_callable():
    """Callable bond: OAS = Z-spread - option cost, should be less than Z."""
    oas = compute_oas_simplified(150, option_cost_bps=30)
    assert oas == 120
    assert oas < 150


# ── compute_relative_value ───────────────────────────────────────────


def test_relative_value_at_median():
    """Current spread at the median of history: percentile ~50, score ~0."""
    hist = [100.0, 120.0, 140.0, 160.0, 180.0]
    rv = compute_relative_value(140.0, hist)
    assert rv["own_percentile"] == pytest.approx(60.0, abs=1.0)
    # Score should be near 0 (neutral) at percentile ~50
    assert abs(rv["rich_cheap_score"]) < 30


def test_relative_value_at_extremes_cheap():
    """Current spread at the highest -> near 100th percentile, positive (cheap) score."""
    hist = [100.0, 110.0, 120.0, 130.0, 140.0]
    rv = compute_relative_value(200.0, hist)
    assert rv["own_percentile"] == 100.0
    assert rv["rich_cheap_score"] == 100.0  # (100-50)*2 = 100


def test_relative_value_at_extremes_rich():
    """Current spread below all history -> 0th percentile, rich score."""
    hist = [100.0, 110.0, 120.0, 130.0, 140.0]
    rv = compute_relative_value(50.0, hist)
    assert rv["own_percentile"] == 0.0
    assert rv["rich_cheap_score"] == -100.0  # (0-50)*2 = -100


def test_relative_value_with_peers():
    """With peer spreads provided, vs_peers_percentile should be computed."""
    hist = [100.0, 120.0, 140.0]
    peers = [90.0, 110.0, 130.0, 150.0]
    rv = compute_relative_value(120.0, hist, peer_spreads=peers)
    assert rv["vs_peers_percentile"] is not None
    # 120 is <= 120, 130, 150 among [90, 110, 120, 130, 150] => 3/5 = 60%
    assert rv["vs_peers_percentile"] == pytest.approx(60.0, abs=1.0)


def test_relative_value_without_peers():
    """Without peer spreads, vs_peers_percentile should be None."""
    rv = compute_relative_value(120.0, [100.0, 120.0, 140.0])
    assert rv["vs_peers_percentile"] is None


# ── compute_breakeven_spread ─────────────────────────────────────────


def test_breakeven_typical_ig_bond():
    """Typical IG bond: 150 bps spread, 7Y duration -> breakeven ~21 bps/yr."""
    be = compute_breakeven_spread(150.0, 7.0, 1.0)
    assert be["carry_bps"] == pytest.approx(150.0, abs=0.1)
    assert be["breakeven_widening_bps"] == pytest.approx(150.0 / 7.0, abs=0.1)
    assert be["horizon_years"] == 1.0


def test_breakeven_short_duration():
    """Short duration (2Y) with 100 bps -> higher breakeven widening = 50 bps."""
    be = compute_breakeven_spread(100.0, 2.0, 1.0)
    assert be["breakeven_widening_bps"] == pytest.approx(50.0, abs=0.1)


def test_breakeven_long_duration():
    """Long duration (15Y) with 200 bps -> lower breakeven widening ~13 bps."""
    be = compute_breakeven_spread(200.0, 15.0, 1.0)
    assert be["breakeven_widening_bps"] == pytest.approx(200.0 / 15.0, abs=0.1)


# ── compute_spread_duration ──────────────────────────────────────────


def test_spread_duration_equals_mod_duration():
    """For fixed-rate bonds, spread duration = modified duration."""
    assert compute_spread_duration(7.5) == 7.5
    assert compute_spread_duration(0.0) == 0.0
    assert compute_spread_duration(12.3) == 12.3
