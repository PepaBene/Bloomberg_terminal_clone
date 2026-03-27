"""Tests for E9 Bond Pricing Engine (Pillar 2 FI Supplement -- Part 1)."""

from datetime import date

import pytest

from src.engines.e9_bond_pricing import (
    compute_accrued_interest,
    compute_ytw_full,
    day_count_fraction,
    generate_cash_flow_schedule,
    price_from_yield,
    yield_from_price,
)


# ── day_count_fraction Tests ────────────────────────────────────────


def test_dcf_30_360_six_months():
    """30/360: Jan 15 to Jul 15 = exactly 0.5 years."""
    start = date(2025, 1, 15)
    end = date(2025, 7, 15)
    dcf = day_count_fraction(start, end, "30/360")
    assert dcf == pytest.approx(0.5, abs=1e-9)


def test_dcf_30_360_90_days():
    """30/360: Jan 15 to Apr 15 = 90/360 = 0.25."""
    start = date(2025, 1, 15)
    end = date(2025, 4, 15)
    dcf = day_count_fraction(start, end, "30/360")
    assert dcf == pytest.approx(0.25, abs=1e-9)


def test_dcf_act_act_non_leap():
    """ACT/ACT: 90 actual days in 2025 (non-leap) -> 90/365."""
    start = date(2025, 1, 1)
    end = date(2025, 4, 1)
    dcf = day_count_fraction(start, end, "ACT/ACT")
    assert dcf == pytest.approx(90 / 365.0, abs=1e-6)


def test_dcf_act_act_leap_year():
    """ACT/ACT: 91 actual days in 2024 (leap year) -> 91/366."""
    start = date(2024, 1, 1)
    end = date(2024, 4, 1)
    dcf = day_count_fraction(start, end, "ACT/ACT")
    assert dcf == pytest.approx(91 / 366.0, abs=1e-6)


def test_dcf_act_360():
    """ACT/360: 90 actual days -> 90/360 = 0.25."""
    start = date(2025, 1, 1)
    end = date(2025, 4, 1)
    dcf = day_count_fraction(start, end, "ACT/360")
    assert dcf == pytest.approx(90 / 360.0, abs=1e-6)


def test_dcf_act_365():
    """ACT/365: 90 actual days -> 90/365."""
    start = date(2025, 1, 1)
    end = date(2025, 4, 1)
    dcf = day_count_fraction(start, end, "ACT/365")
    assert dcf == pytest.approx(90 / 365.0, abs=1e-6)


def test_dcf_same_date():
    """Same start and end date -> 0.0."""
    d = date(2025, 6, 15)
    assert day_count_fraction(d, d, "30/360") == 0.0


def test_dcf_end_before_start():
    """End before start -> 0.0."""
    assert day_count_fraction(date(2025, 7, 1), date(2025, 1, 1), "30/360") == 0.0


# ── compute_accrued_interest Tests ──────────────────────────────────


def test_accrued_interest_mid_period():
    """5% semi-annual, half-way through period -> ~1.25."""
    last_coupon = date(2025, 1, 15)
    settlement = date(2025, 4, 15)
    ai = compute_accrued_interest(0.05, 100.0, 2, last_coupon, settlement, "30/360")
    # Coupon per period = 2.50, 3 months / 6 months = 0.5 -> AI = 1.25
    assert ai == pytest.approx(1.25, abs=0.05)


def test_accrued_interest_at_coupon_date():
    """At coupon date, accrued interest should be zero."""
    coupon_date = date(2025, 7, 15)
    ai = compute_accrued_interest(0.05, 100.0, 2, coupon_date, coupon_date, "30/360")
    assert ai == 0.0


def test_accrued_interest_zero_coupon():
    """Zero coupon bond has no accrued interest."""
    ai = compute_accrued_interest(0.0, 100.0, 2, date(2025, 1, 15), date(2025, 4, 15), "30/360")
    assert ai == 0.0


# ── generate_cash_flow_schedule Tests ───────────────────────────────


def test_cash_flows_5y_semi_annual():
    """5Y semi-annual 5% bond: 10 coupons + 1 principal."""
    settlement = date(2025, 6, 15)
    maturity = date(2030, 6, 15)
    flows = generate_cash_flow_schedule(0.05, 100.0, 2, maturity, settlement)

    coupons = [f for f in flows if f["type"] == "COUPON"]
    principals = [f for f in flows if f["type"] == "PRINCIPAL"]

    assert len(coupons) == 10
    assert len(principals) == 1
    assert principals[0]["amount"] == 100.0
    # Each coupon = 100 * 0.05 / 2 = 2.50
    for c in coupons:
        assert c["amount"] == pytest.approx(2.5, abs=0.01)


def test_cash_flows_zero_coupon():
    """Zero coupon bond: only principal at maturity."""
    settlement = date(2025, 6, 15)
    maturity = date(2030, 6, 15)
    flows = generate_cash_flow_schedule(0.0, 100.0, 0, maturity, settlement)

    assert len(flows) == 1
    assert flows[0]["type"] == "PRINCIPAL"
    assert flows[0]["amount"] == 100.0


def test_cash_flows_callable_bond():
    """Callable bond includes CALL entries in schedule."""
    settlement = date(2025, 6, 15)
    maturity = date(2030, 6, 15)
    call_schedule = [
        {"call_date": date(2027, 6, 15), "call_price": 101.0},
        {"call_date": date(2028, 6, 15), "call_price": 100.5},
    ]
    flows = generate_cash_flow_schedule(0.05, 100.0, 2, maturity, settlement, call_schedule)

    call_flows = [f for f in flows if f["type"] == "CALL"]
    assert len(call_flows) == 2
    assert call_flows[0]["amount"] == 101.0
    assert call_flows[1]["amount"] == 100.5


# ── price_from_yield Tests ──────────────────────────────────────────


def test_price_from_yield_par_bond():
    """When ytm = coupon rate, clean price should be approximately 100 (par)."""
    result = price_from_yield(
        ytm=0.05,
        coupon_rate=0.05,
        face_value=100.0,
        settlement_date=date(2025, 6, 15),
        maturity_date=date(2035, 6, 15),
        frequency=2,
        day_count="30/360",
    )
    # At a coupon date, clean price ~ par
    assert result["clean_price"] == pytest.approx(100.0, abs=0.5)


def test_price_from_yield_premium():
    """Lower yield than coupon -> premium (price > 100)."""
    result = price_from_yield(
        ytm=0.03,
        coupon_rate=0.05,
        face_value=100.0,
        settlement_date=date(2025, 6, 15),
        maturity_date=date(2035, 6, 15),
        frequency=2,
        day_count="30/360",
    )
    assert result["clean_price"] > 100.0


def test_price_from_yield_discount():
    """Higher yield than coupon -> discount (price < 100)."""
    result = price_from_yield(
        ytm=0.07,
        coupon_rate=0.05,
        face_value=100.0,
        settlement_date=date(2025, 6, 15),
        maturity_date=date(2035, 6, 15),
        frequency=2,
        day_count="30/360",
    )
    assert result["clean_price"] < 100.0


# ── yield_from_price / round-trip Tests ─────────────────────────────


def test_yield_from_price_round_trip():
    """price -> yield -> price should produce consistent result."""
    settlement = date(2025, 6, 15)
    maturity = date(2035, 6, 15)
    original_price = 95.0

    ytm = yield_from_price(original_price, 0.05, 100.0, settlement, maturity, 2, "30/360")
    result = price_from_yield(ytm, 0.05, 100.0, settlement, maturity, 2, "30/360")

    assert result["clean_price"] == pytest.approx(original_price, abs=0.1)


def test_yield_from_price_par():
    """At par price, yield should equal coupon rate."""
    settlement = date(2025, 6, 15)
    maturity = date(2035, 6, 15)
    ytm = yield_from_price(100.0, 0.05, 100.0, settlement, maturity, 2, "30/360")
    assert ytm == pytest.approx(0.05, abs=0.002)


# ── compute_ytw_full Tests ──────────────────────────────────────────


def test_ytw_full_non_callable():
    """Non-callable bond: ytw == ytm, yield_to == MATURITY."""
    settlement = date(2025, 6, 15)
    maturity = date(2035, 6, 15)
    result = compute_ytw_full(
        clean_price=100.0,
        coupon_rate=0.05,
        face_value=100.0,
        settlement_date=settlement,
        maturity_date=maturity,
    )
    assert result["yield_to"] == "MATURITY"
    assert result["exercise_date"] is None
    assert result["call_yields"] is None
    assert result["ytw"] == pytest.approx(result["ytm"], abs=1e-8)


def test_ytw_full_callable_near_par():
    """Callable bond trading at premium: ytw should be <= ytm."""
    settlement = date(2025, 6, 15)
    maturity = date(2035, 6, 15)
    call_schedule = [
        {"call_date": date(2028, 6, 15), "call_price": 100.0},
    ]
    result = compute_ytw_full(
        clean_price=105.0,
        coupon_rate=0.06,
        face_value=100.0,
        settlement_date=settlement,
        maturity_date=maturity,
        call_schedule=call_schedule,
    )
    assert result["ytw"] <= result["ytm"]
    assert result["call_yields"] is not None
    assert len(result["call_yields"]) == 1


def test_ytw_full_callable_discount():
    """Callable bond at discount: ytw should typically equal ytm (call is irrelevant)."""
    settlement = date(2025, 6, 15)
    maturity = date(2035, 6, 15)
    call_schedule = [
        {"call_date": date(2028, 6, 15), "call_price": 100.0},
    ]
    result = compute_ytw_full(
        clean_price=90.0,
        coupon_rate=0.04,
        face_value=100.0,
        settlement_date=settlement,
        maturity_date=maturity,
        call_schedule=call_schedule,
    )
    # At a discount, call yields are typically higher than ytm, so ytw = ytm
    assert result["yield_to"] == "MATURITY"
    assert result["ytw"] == pytest.approx(result["ytm"], abs=1e-8)
