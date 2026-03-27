"""Tests for bond analytics engine (D11 FI Supplement P4)."""

import pytest

from src.engines.bond_analytics import (
    compute_convexity,
    compute_g_spread,
    compute_liquidity_score,
    compute_macaulay_duration,
    compute_modified_duration,
    compute_vwap,
    compute_ytm,
    compute_ytw,
)


# ── YTM Tests ────────────────────────────────────────────────────────


def test_ytm_par_bond():
    """At par (price=100), YTM should equal the coupon rate."""
    ytm = compute_ytm(price=100.0, coupon_rate=0.05, face_value=100.0,
                       years_to_maturity=10.0, frequency=2)
    assert ytm == pytest.approx(0.05, abs=0.001)


def test_ytm_premium():
    """Premium bond (price>100): YTM should be less than coupon rate."""
    ytm = compute_ytm(price=105.0, coupon_rate=0.05, face_value=100.0,
                       years_to_maturity=10.0, frequency=2)
    assert ytm < 0.05


def test_ytm_discount():
    """Discount bond (price<100): YTM should be greater than coupon rate."""
    ytm = compute_ytm(price=95.0, coupon_rate=0.05, face_value=100.0,
                       years_to_maturity=10.0, frequency=2)
    assert ytm > 0.05


def test_ytm_zero_coupon():
    """Zero coupon bond: frequency=0, price=80, 10Y -> ytm ~2.3%."""
    ytm = compute_ytm(price=80.0, coupon_rate=0.0, face_value=100.0,
                       years_to_maturity=10.0, frequency=0)
    # (100/80)^(1/10) - 1 ≈ 0.02256
    assert ytm == pytest.approx(0.02256, abs=0.001)


# ── YTW Tests ────────────────────────────────────────────────────────


def test_ytw_no_calls():
    """Without call schedule, YTW = YTM."""
    ytm = compute_ytm(price=100.0, coupon_rate=0.05, face_value=100.0,
                       years_to_maturity=10.0, frequency=2)
    ytw = compute_ytw(price=100.0, coupon_rate=0.05, face_value=100.0,
                       years_to_maturity=10.0, call_schedule=None, frequency=2)
    assert ytw == pytest.approx(ytm, abs=1e-8)


def test_ytw_with_calls():
    """Callable in 3Y at 101 -> YTW should be less than YTM for premium bond."""
    # Premium bond: buyer pays 105, callable in 3Y at 101
    ytm = compute_ytm(price=105.0, coupon_rate=0.06, face_value=100.0,
                       years_to_maturity=10.0, frequency=2)
    ytw = compute_ytw(
        price=105.0, coupon_rate=0.06, face_value=100.0,
        years_to_maturity=10.0,
        call_schedule=[{"years_to_call": 3.0, "call_price": 101.0}],
        frequency=2,
    )
    assert ytw <= ytm


# ── Duration Tests ───────────────────────────────────────────────────


def test_modified_duration_par():
    """10Y 5% at par: modified duration ~7.8-8.1."""
    ytm = 0.05
    mod_dur = compute_modified_duration(ytm, 0.05, 10.0, 2)
    assert 7.5 <= mod_dur <= 8.5


def test_macaulay_duration():
    """Macaulay duration should be > modified duration."""
    ytm = 0.05
    mod_dur = compute_modified_duration(ytm, 0.05, 10.0, 2)
    mac_dur = compute_macaulay_duration(ytm, 0.05, 10.0, 2)
    assert mac_dur > mod_dur


def test_duration_zero_coupon():
    """Zero coupon bond: duration = maturity."""
    mod_dur = compute_modified_duration(0.05, 0.0, 10.0, frequency=0)
    assert mod_dur == pytest.approx(10.0, abs=0.01)


# ── Convexity Tests ──────────────────────────────────────────────────


def test_convexity_positive():
    """Convexity should always be positive for a standard bond."""
    conv = compute_convexity(0.05, 0.05, 10.0, 2)
    assert conv > 0


# ── G-Spread Tests ───────────────────────────────────────────────────


def test_g_spread():
    """YTM=0.06, treasury=0.04 -> 200 bps."""
    spread = compute_g_spread(0.06, 0.04)
    assert spread == 200


# ── VWAP Tests ───────────────────────────────────────────────────────


def test_vwap():
    """3 trades should produce correct weighted average."""
    trades = [
        {"price": 100.0, "quantity": 1_000_000},
        {"price": 99.0, "quantity": 2_000_000},
        {"price": 101.0, "quantity": 1_000_000},
    ]
    vwap = compute_vwap(trades)
    # (100*1M + 99*2M + 101*1M) / 4M = (100M + 198M + 101M) / 4M = 399M/4M = 99.75
    assert vwap == pytest.approx(99.75, abs=0.01)


def test_vwap_empty():
    """Empty trades list -> 0.0."""
    assert compute_vwap([]) == 0.0


# ── Liquidity Score Tests ────────────────────────────────────────────


def test_liquidity_high():
    """15 trades, $20M volume -> score 80+."""
    score = compute_liquidity_score(15, 20_000_000)
    assert score >= 80


def test_liquidity_low():
    """1 trade -> score ~30."""
    score = compute_liquidity_score(1, 100_000)
    assert score == 30
