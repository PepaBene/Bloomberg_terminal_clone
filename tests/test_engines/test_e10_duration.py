"""Tests for E10 Duration & Convexity Engine."""

import pytest

from src.engines.bond_analytics import (
    compute_convexity,
    compute_modified_duration,
)
from src.engines.e10_duration import (
    KEY_RATE_TENORS,
    compute_dv01,
    compute_effective_convexity,
    compute_effective_duration,
    compute_key_rate_durations,
    compute_portfolio_duration,
    estimate_price_change,
    generate_rate_sensitivity_table,
)


# ── DV01 Tests ────────────────────────────────────────────────────────


def test_dv01_5y_bond():
    """DV01 of a 5Y par bond: mod_dur ~ 4.4, price=100 -> DV01 ~ 0.044."""
    mod_dur = compute_modified_duration(0.05, 0.05, 5.0, 2)
    dv01 = compute_dv01(mod_dur, 100.0)
    assert 0.03 < dv01 < 0.06
    # DV01 = mod_dur * 100 * 0.0001
    assert dv01 == pytest.approx(mod_dur * 100.0 * 0.0001, abs=1e-10)


def test_dv01_10y_bond():
    """DV01 of a 10Y par bond should be higher than a 5Y bond."""
    mod_dur_5 = compute_modified_duration(0.05, 0.05, 5.0, 2)
    mod_dur_10 = compute_modified_duration(0.05, 0.05, 10.0, 2)
    dv01_5 = compute_dv01(mod_dur_5, 100.0)
    dv01_10 = compute_dv01(mod_dur_10, 100.0)
    assert dv01_10 > dv01_5


def test_dv01_zero_coupon():
    """DV01 for a zero coupon 10Y bond: duration = maturity, DV01 = 10 * price * 0.0001."""
    # Zero coupon: modified duration = years_to_maturity for freq=0
    mod_dur = compute_modified_duration(0.05, 0.0, 10.0, frequency=0)
    price = 61.39  # approximate price of zero coupon 10Y at 5%
    dv01 = compute_dv01(mod_dur, price)
    assert dv01 == pytest.approx(mod_dur * price * 0.0001, abs=1e-10)
    assert dv01 > 0


# ── Key Rate Duration Tests ──────────────────────────────────────────


def _flat_zero_curve(rate: float = 0.05) -> list[dict]:
    """Build a flat zero curve at all 8 standard tenors."""
    from src.engines.e10_duration import KEY_RATE_YEARS

    return [{"tenor_years": t, "zero_rate": rate} for t in KEY_RATE_YEARS]


def test_krd_returns_8_tenors():
    """Key rate durations should return exactly 8 tenors."""
    curve = _flat_zero_curve(0.05)
    krds = compute_key_rate_durations(
        price=100.0,
        coupon_rate=0.05,
        face_value=100.0,
        years_to_maturity=10.0,
        frequency=2,
        zero_curve=curve,
    )
    assert set(krds.keys()) == set(KEY_RATE_TENORS)
    assert len(krds) == 8


def test_krd_sum_approximates_modified_duration():
    """Sum of KRDs should approximately equal modified duration."""
    curve = _flat_zero_curve(0.05)
    mod_dur = compute_modified_duration(0.05, 0.05, 10.0, 2)
    krds = compute_key_rate_durations(
        price=100.0,
        coupon_rate=0.05,
        face_value=100.0,
        years_to_maturity=10.0,
        frequency=2,
        zero_curve=curve,
    )
    krd_sum = sum(krds.values())
    # Sum of KRDs should be close to modified duration (within 15% for flat curve)
    assert abs(krd_sum - mod_dur) / mod_dur < 0.15


def test_krd_longest_tenor_highest_for_long_bond():
    """For a 30Y bond, the 30Y key rate duration should be the highest."""
    curve = _flat_zero_curve(0.04)
    krds = compute_key_rate_durations(
        price=100.0,
        coupon_rate=0.04,
        face_value=100.0,
        years_to_maturity=30.0,
        frequency=2,
        zero_curve=curve,
    )
    # The 30Y tenor should have a large KRD because that's where the principal repayment is
    assert krds["30Y"] == max(krds.values())


# ── Effective Duration Tests ─────────────────────────────────────────


def test_effective_duration_symmetric():
    """Symmetric price changes: effective duration equals finite-difference duration."""
    # For a bullet bond, P_down > P_base > P_up when rates rise
    price_base = 100.0
    price_up = 92.0   # rates up -> price down
    price_down = 108.5  # rates down -> price up
    shock = 100.0

    ed = compute_effective_duration(price_up, price_down, price_base, shock)
    # ED = (108.5 - 92.0) / (2 * 100 * 0.01) = 16.5 / 2.0 = 8.25
    assert ed == pytest.approx(8.25, abs=0.01)


def test_effective_duration_asymmetric_callable():
    """Callable bond: price upside is capped, so asymmetric response."""
    price_base = 102.0
    # Callable: when rates drop, price doesn't rise as much (call caps the upside)
    price_up = 94.0    # rates up -> price falls
    price_down = 104.0  # rates down -> price barely rises (call caps it)
    shock = 100.0

    ed = compute_effective_duration(price_up, price_down, price_base, shock)
    # ED = (104 - 94) / (2 * 102 * 0.01) = 10 / 2.04 = 4.902
    assert ed == pytest.approx(4.902, abs=0.01)
    # This should be lower than a bullet bond with similar characteristics
    assert ed < 8.0


def test_effective_duration_zero_base():
    """Edge case: zero base price should return 0."""
    assert compute_effective_duration(90.0, 110.0, 0.0, 100.0) == 0.0


# ── Effective Convexity Tests ────────────────────────────────────────


def test_effective_convexity_positive_bullet():
    """Bullet bond: positive convexity (P_up + P_down > 2*P_base)."""
    price_base = 100.0
    price_up = 92.0
    price_down = 108.5
    shock = 100.0

    ec = compute_effective_convexity(price_up, price_down, price_base, shock)
    # EC = (92.0 + 108.5 - 200) / (100 * 0.01^2) = 0.5 / 0.01 = 50.0
    assert ec == pytest.approx(50.0, abs=0.01)
    assert ec > 0


def test_effective_convexity_negative_callable():
    """Callable bond can have negative convexity when near the call price."""
    price_base = 102.0
    # When near the call price, convexity turns negative
    price_up = 94.0
    price_down = 103.5  # barely rises
    shock = 100.0

    ec = compute_effective_convexity(price_up, price_down, price_base, shock)
    # EC = (94 + 103.5 - 204) / (102 * 0.0001) = -6.5 / 0.0102 = -637.25
    assert ec < 0


# ── Portfolio Duration Tests ─────────────────────────────────────────


def test_portfolio_duration_single_bond():
    """Single-bond portfolio: weighted average = bond's own values."""
    positions = [
        {
            "weight": 1.0,
            "modified_duration": 7.5,
            "dv01": 0.075,
            "convexity": 80.0,
        }
    ]
    result = compute_portfolio_duration(positions)
    assert result["weighted_avg_duration"] == pytest.approx(7.5, abs=0.01)
    assert result["portfolio_dv01"] == pytest.approx(0.075, abs=0.001)
    assert result["weighted_avg_convexity"] == pytest.approx(80.0, abs=0.01)


def test_portfolio_duration_two_bonds():
    """Two-bond portfolio: 60/40 split."""
    positions = [
        {
            "weight": 0.6,
            "modified_duration": 5.0,
            "dv01": 0.05,
            "convexity": 30.0,
        },
        {
            "weight": 0.4,
            "modified_duration": 10.0,
            "dv01": 0.10,
            "convexity": 120.0,
        },
    ]
    result = compute_portfolio_duration(positions)
    # Weighted avg duration: (0.6*5 + 0.4*10) / 1.0 = 7.0
    assert result["weighted_avg_duration"] == pytest.approx(7.0, abs=0.01)
    # Portfolio DV01: 0.05*0.6 + 0.10*0.4 = 0.07
    assert result["portfolio_dv01"] == pytest.approx(0.07, abs=0.001)
    # Weighted convexity: (0.6*30 + 0.4*120) / 1.0 = 66.0
    assert result["weighted_avg_convexity"] == pytest.approx(66.0, abs=0.01)


def test_portfolio_duration_five_bonds():
    """Five-bond equal-weight portfolio."""
    durations = [3.0, 5.0, 7.0, 10.0, 15.0]
    dv01s = [0.03, 0.05, 0.07, 0.10, 0.15]
    convexities = [10.0, 30.0, 60.0, 120.0, 250.0]

    positions = [
        {
            "weight": 0.2,
            "modified_duration": d,
            "dv01": v,
            "convexity": c,
        }
        for d, v, c in zip(durations, dv01s, convexities)
    ]
    result = compute_portfolio_duration(positions)
    # Equal weight: average of durations = (3+5+7+10+15)/5 = 8.0
    assert result["weighted_avg_duration"] == pytest.approx(8.0, abs=0.01)
    # Portfolio DV01: sum of weight * dv01 = 0.2*(0.03+0.05+0.07+0.10+0.15) = 0.08
    assert result["portfolio_dv01"] == pytest.approx(0.08, abs=0.001)


def test_portfolio_duration_empty():
    """Empty positions list returns zeros."""
    result = compute_portfolio_duration([])
    assert result["weighted_avg_duration"] == 0.0
    assert result["portfolio_dv01"] == 0.0


def test_portfolio_duration_with_krds():
    """Portfolio with key rate durations should aggregate them."""
    positions = [
        {
            "weight": 0.5,
            "modified_duration": 5.0,
            "dv01": 0.05,
            "convexity": 30.0,
            "key_rate_durations": {"1Y": 0.1, "5Y": 2.0, "10Y": 2.9},
        },
        {
            "weight": 0.5,
            "modified_duration": 10.0,
            "dv01": 0.10,
            "convexity": 100.0,
            "key_rate_durations": {"1Y": 0.05, "5Y": 1.0, "10Y": 8.95},
        },
    ]
    result = compute_portfolio_duration(positions)
    krds = result["portfolio_key_rate_durations"]
    assert krds is not None
    # Weighted: 0.5*0.1 + 0.5*0.05 = 0.075 for 1Y
    assert krds["1Y"] == pytest.approx(0.075, abs=0.01)


# ── Price Change Estimation Tests ────────────────────────────────────


def test_estimate_price_change_positive_shift():
    """+100bps shift: price should decrease."""
    pct = estimate_price_change(modified_duration=7.5, convexity=80.0, yield_change_bps=100.0)
    # -7.5 * 0.01 + 0.5 * 80 * 0.01^2 = -0.075 + 0.004 = -0.071
    assert pct == pytest.approx(-0.071, abs=0.001)
    assert pct < 0  # price goes down when yields go up


def test_estimate_price_change_negative_shift():
    """-100bps shift: price should increase."""
    pct = estimate_price_change(modified_duration=7.5, convexity=80.0, yield_change_bps=-100.0)
    # -7.5 * (-0.01) + 0.5 * 80 * 0.01^2 = 0.075 + 0.004 = 0.079
    assert pct == pytest.approx(0.079, abs=0.001)
    assert pct > 0  # price goes up when yields go down


def test_convexity_adjustment_improves_accuracy():
    """Convexity adjustment: for both up and down shifts,
    |change_down| > |change_up| (convexity benefit)."""
    dur = 7.5
    conv = 80.0
    pct_up = estimate_price_change(dur, conv, 100.0)
    pct_down = estimate_price_change(dur, conv, -100.0)
    # Due to convexity, downward shift gains more than upward shift losses
    assert abs(pct_down) > abs(pct_up)


# ── Rate Sensitivity Table Tests ─────────────────────────────────────


def test_sensitivity_table_default_10_rows():
    """Default table should have 10 rows."""
    table = generate_rate_sensitivity_table(
        modified_duration=7.5,
        convexity=80.0,
        base_price=100.0,
    )
    assert len(table) == 10


def test_sensitivity_table_correct_signs():
    """Positive shift -> negative price change, negative shift -> positive."""
    table = generate_rate_sensitivity_table(
        modified_duration=7.5,
        convexity=80.0,
        base_price=100.0,
    )
    for row in table:
        if row["shift_bps"] > 0:
            assert row["price_change_pct"] < 0, f"shift={row['shift_bps']}: expected negative change"
        elif row["shift_bps"] < 0:
            assert row["price_change_pct"] > 0, f"shift={row['shift_bps']}: expected positive change"


def test_sensitivity_table_custom_shifts():
    """Custom shifts list should produce correct number of rows."""
    table = generate_rate_sensitivity_table(
        modified_duration=5.0,
        convexity=40.0,
        base_price=98.0,
        shifts_bps=[-50, -25, 25, 50],
    )
    assert len(table) == 4
    assert table[0]["shift_bps"] == -50
    assert table[-1]["shift_bps"] == 50


def test_sensitivity_table_estimated_prices():
    """Estimated new prices should be consistent with base_price and pct changes."""
    base = 100.0
    table = generate_rate_sensitivity_table(
        modified_duration=7.5,
        convexity=80.0,
        base_price=base,
    )
    for row in table:
        expected = base * (1.0 + row["price_change_pct"])
        assert row["estimated_new_price"] == pytest.approx(expected, abs=0.01)
