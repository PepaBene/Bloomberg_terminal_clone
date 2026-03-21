"""Tests for the default risk scoring engine (Pillar 2 Supplement – Part 2)."""

import math

import pytest

from src.engines.default_risk import (
    CompositeResult,
    MertonResult,
    _map_score_to_rating,
    _map_score_to_zone,
    _norm_cdf,
    _norm_pdf,
    compute_composite_score,
    detect_trend,
    merton_distance_to_default,
)


# ── Normal distribution helpers ──────────────────────────────────────


class TestNormCDF:
    def test_at_zero(self):
        assert abs(_norm_cdf(0.0) - 0.5) < 1e-8

    def test_positive(self):
        # N(1.0) ≈ 0.8413
        assert abs(_norm_cdf(1.0) - 0.8413) < 0.001

    def test_negative(self):
        # N(-1.0) ≈ 0.1587
        assert abs(_norm_cdf(-1.0) - 0.1587) < 0.001

    def test_extreme_positive(self):
        assert _norm_cdf(10.0) > 0.9999

    def test_extreme_negative(self):
        assert _norm_cdf(-10.0) < 0.0001


class TestNormPDF:
    def test_at_zero(self):
        expected = 1.0 / math.sqrt(2 * math.pi)
        assert abs(_norm_pdf(0.0) - expected) < 1e-8

    def test_symmetry(self):
        assert abs(_norm_pdf(1.0) - _norm_pdf(-1.0)) < 1e-10


# ── Merton Distance-to-Default ──────────────────────────────────────


class TestMertonDD:
    def test_healthy_company(self):
        """A company with high equity value relative to debt should have high DD."""
        result = merton_distance_to_default(
            equity_value=100_000,
            equity_volatility=0.25,
            total_debt=20_000,
            risk_free_rate=0.045,
        )
        assert isinstance(result, MertonResult)
        assert result.distance_to_default > 2.0
        assert result.probability_of_default < 0.10
        assert result.asset_value > 0
        assert result.asset_volatility > 0

    def test_distressed_company(self):
        """A company with high debt relative to equity should have low DD."""
        result = merton_distance_to_default(
            equity_value=10_000,
            equity_volatility=0.60,
            total_debt=80_000,
            risk_free_rate=0.045,
        )
        assert result.distance_to_default < 2.0
        assert result.probability_of_default > 0.01

    def test_high_volatility_increases_pd(self):
        """Higher equity volatility should increase probability of default."""
        result_low_vol = merton_distance_to_default(
            equity_value=50_000, equity_volatility=0.15,
            total_debt=30_000, risk_free_rate=0.04,
        )
        result_high_vol = merton_distance_to_default(
            equity_value=50_000, equity_volatility=0.50,
            total_debt=30_000, risk_free_rate=0.04,
        )
        assert result_high_vol.probability_of_default > result_low_vol.probability_of_default

    def test_higher_debt_increases_pd(self):
        """More debt should increase probability of default."""
        result_low_debt = merton_distance_to_default(
            equity_value=50_000, equity_volatility=0.30,
            total_debt=10_000, risk_free_rate=0.04,
        )
        result_high_debt = merton_distance_to_default(
            equity_value=50_000, equity_volatility=0.30,
            total_debt=60_000, risk_free_rate=0.04,
        )
        assert result_high_debt.probability_of_default > result_low_debt.probability_of_default

    def test_invalid_inputs_raise(self):
        with pytest.raises(ValueError, match="positive"):
            merton_distance_to_default(
                equity_value=-1, equity_volatility=0.30,
                total_debt=10_000, risk_free_rate=0.04,
            )
        with pytest.raises(ValueError, match="positive"):
            merton_distance_to_default(
                equity_value=50_000, equity_volatility=0,
                total_debt=10_000, risk_free_rate=0.04,
            )

    def test_pd_between_zero_and_one(self):
        """PD should always be between 0 and 1."""
        for eq, vol, debt in [(100_000, 0.1, 5_000), (5_000, 0.8, 100_000)]:
            result = merton_distance_to_default(
                equity_value=eq, equity_volatility=vol,
                total_debt=debt, risk_free_rate=0.04,
            )
            assert 0 <= result.probability_of_default <= 1

    def test_asset_value_exceeds_equity(self):
        """Asset value should be at least equity value."""
        result = merton_distance_to_default(
            equity_value=50_000, equity_volatility=0.30,
            total_debt=30_000, risk_free_rate=0.04,
        )
        assert result.asset_value >= 50_000


# ── Composite Score ──────────────────────────────────────────────────


class TestCompositeScore:
    def test_investment_grade(self):
        """Strong inputs should yield high score and IG zone."""
        result = compute_composite_score(
            altman_z=3.5, altman_zone="SAFE",
            merton_dd=4.5, merton_pd=0.001,
            leverage_ratio=0.25, interest_coverage=12.0, cash_ratio=0.8,
        )
        assert isinstance(result, CompositeResult)
        assert result.score >= 70
        assert result.credit_zone == "INVESTMENT_GRADE"
        assert result.implied_rating in ("AAA", "AA+", "AA", "AA-", "A+", "A", "A-")

    def test_distressed(self):
        """Weak inputs should yield low score and DISTRESSED zone."""
        result = compute_composite_score(
            altman_z=0.5, altman_zone="DISTRESS",
            merton_dd=0.3, merton_pd=0.40,
            leverage_ratio=0.90, interest_coverage=0.5, cash_ratio=0.05,
        )
        assert result.score < 25
        assert result.credit_zone in ("HIGH_YIELD", "DISTRESSED")

    def test_partial_inputs(self):
        """Should work with only some inputs available."""
        result = compute_composite_score(altman_z=2.5, altman_zone="GREY")
        assert result.score > 0
        assert len(result.drivers) == 1
        assert result.drivers[0]["driver"] == "altman_z"

    def test_no_inputs(self):
        """No inputs should return minimum score."""
        result = compute_composite_score()
        assert result.score == 0.0
        assert result.implied_rating == "D"
        assert result.credit_zone == "DISTRESSED"

    def test_drivers_sum_approximately_to_score(self):
        """Driver contributions should sum to approximately the composite score."""
        result = compute_composite_score(
            altman_z=2.8, altman_zone="SAFE",
            merton_dd=3.0, merton_pd=0.01,
            leverage_ratio=0.35, interest_coverage=8.0, cash_ratio=0.6,
        )
        driver_sum = sum(d["contribution"] for d in result.drivers)
        assert abs(driver_sum - result.score) < 2.0  # allow rounding

    def test_drivers_ordered_by_contribution(self):
        """Drivers should be sorted descending by contribution."""
        result = compute_composite_score(
            altman_z=2.5, merton_dd=3.0,
            leverage_ratio=0.40, interest_coverage=6.0, cash_ratio=0.5,
        )
        contribs = [d["contribution"] for d in result.drivers]
        assert contribs == sorted(contribs, reverse=True)

    def test_crossover_zone(self):
        """Mid-range score should be in crossover zone."""
        result = compute_composite_score(
            altman_z=1.8, altman_zone="GREY",
            merton_dd=1.5, merton_pd=0.10,
        )
        assert 30 <= result.score <= 55


# ── Rating mapping ───────────────────────────────────────────────────


class TestRatingMapping:
    def test_top_score(self):
        assert _map_score_to_rating(99) == "AAA"

    def test_mid_score(self):
        rating = _map_score_to_rating(55)
        assert rating == "BBB"

    def test_low_score(self):
        rating = _map_score_to_rating(10)
        assert rating == "CC"

    def test_very_low_score(self):
        rating = _map_score_to_rating(3)
        assert rating == "D"

    def test_zone_investment_grade(self):
        assert _map_score_to_zone(75) == "INVESTMENT_GRADE"

    def test_zone_high_yield(self):
        assert _map_score_to_zone(25) == "HIGH_YIELD"

    def test_zone_distressed(self):
        assert _map_score_to_zone(10) == "DISTRESSED"


# ── Trend detection ──────────────────────────────────────────────────


class TestTrend:
    def test_improving(self):
        change, trend = detect_trend(70.0, 60.0)
        assert change == 10.0
        assert trend == "IMPROVING"

    def test_deteriorating(self):
        change, trend = detect_trend(40.0, 55.0)
        assert change == -15.0
        assert trend == "DETERIORATING"

    def test_stable(self):
        change, trend = detect_trend(65.0, 63.0)
        assert change == 2.0
        assert trend == "STABLE"

    def test_no_prior(self):
        change, trend = detect_trend(65.0, None)
        assert change is None
        assert trend == "STABLE"
