"""Tests for the Treasury Analytics engine (D11 FI Supplement P2)."""

from datetime import date, timedelta

import pytest

from src.engines.treasury_analytics import (
    classify_treasury,
    compute_duration_convexity,
    compute_treasury_ytm,
    identify_on_the_run,
)


# ── classify_treasury ───────────────────────────────────────────────


class TestClassifyTreasury:
    def test_classify_bill(self):
        """coupon=0, maturity=0.25 -> BILL."""
        assert classify_treasury(coupon_rate=0, maturity_years=0.25) == "BILL"

    def test_classify_note(self):
        """coupon=4.5, maturity=5 -> NOTE."""
        assert classify_treasury(coupon_rate=4.5, maturity_years=5) == "NOTE"

    def test_classify_bond(self):
        """coupon=4.0, maturity=25 -> BOND."""
        assert classify_treasury(coupon_rate=4.0, maturity_years=25) == "BOND"

    def test_classify_tips(self):
        """is_inflation_indexed=True -> TIPS regardless of other params."""
        assert classify_treasury(coupon_rate=1.75, maturity_years=10, is_inflation_indexed=True) == "TIPS"


# ── compute_treasury_ytm ────────────────────────────────────────────


class TestComputeYTM:
    def test_ytm_par_bond(self):
        """Price=100, coupon=5%, 10Y -> ytm ~5%."""
        ytm = compute_treasury_ytm(
            coupon_rate=5.0, face_value=100.0, price=100.0,
            years_to_maturity=10.0, frequency=2,
        )
        assert abs(ytm - 5.0) < 0.1

    def test_ytm_premium_bond(self):
        """Price=105 -> ytm < coupon."""
        ytm = compute_treasury_ytm(
            coupon_rate=5.0, face_value=100.0, price=105.0,
            years_to_maturity=10.0, frequency=2,
        )
        assert ytm < 5.0

    def test_ytm_discount_bond(self):
        """Price=95 -> ytm > coupon."""
        ytm = compute_treasury_ytm(
            coupon_rate=5.0, face_value=100.0, price=95.0,
            years_to_maturity=10.0, frequency=2,
        )
        assert ytm > 5.0

    def test_ytm_zero_coupon(self):
        """T-Bill: price=99.5, maturity=0.25 -> compute discount yield."""
        ytm = compute_treasury_ytm(
            coupon_rate=0, face_value=100.0, price=99.5,
            years_to_maturity=0.25, frequency=0,
        )
        # discount yield = (0.5/100) * (1/0.25) * 100 = 2.0%
        assert abs(ytm - 2.0) < 0.01


# ── compute_duration_convexity ──────────────────────────────────────


class TestDurationConvexity:
    def test_duration_convexity_10y(self):
        """10Y 5% note at par -> modified_duration ~7.8-8.1, convexity ~70-80."""
        result = compute_duration_convexity(
            ytm=5.0, coupon_rate=5.0, years_to_maturity=10.0, frequency=2,
        )
        assert 7.5 <= result["modified_duration"] <= 8.5
        assert 60.0 <= result["convexity"] <= 90.0
        assert result["macaulay_duration"] > result["modified_duration"]

    def test_duration_zero_coupon(self):
        """Zero coupon -> Macaulay duration = maturity."""
        result = compute_duration_convexity(
            ytm=4.0, coupon_rate=0, years_to_maturity=10.0, frequency=2,
        )
        assert abs(result["macaulay_duration"] - 10.0) < 0.01


# ── identify_on_the_run ────────────────────────────────────────────


class TestIdentifyOnTheRun:
    def test_on_the_run(self):
        """List of securities with different issue dates -> most recent per tenor."""
        today = date.today()
        securities = [
            {
                "cusip": "OLD10Y",
                "issue_date": today - timedelta(days=180),
                "maturity_date": today + timedelta(days=int(10 * 365.25)),
            },
            {
                "cusip": "NEW10Y",
                "issue_date": today - timedelta(days=30),
                "maturity_date": today + timedelta(days=int(10 * 365.25) - 30),
            },
        ]
        result = identify_on_the_run(securities)
        # Both should map to the 10Y bucket; the newer one should win
        assert len(result) >= 1
        # Find the 10Y bucket entry
        ten_y = result.get("10Y")
        assert ten_y is not None
        assert ten_y["cusip"] == "NEW10Y"

    def test_on_the_run_empty(self):
        """Empty list -> empty dict."""
        assert identify_on_the_run([]) == {}
