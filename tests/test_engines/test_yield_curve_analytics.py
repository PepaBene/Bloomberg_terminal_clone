"""Tests for the yield curve analytics pure-computation engine."""

import math

import pytest

from src.engines.yield_curve_analytics import (
    STANDARD_TENORS,
    _compute_slope,
    _cubic_spline_interp,
    _nelson_siegel_rate,
    _ols_3x3,
    compute_breakeven_inflation,
    compute_curve_analytics,
    interpolate_rate,
    nelson_siegel_fit,
    shift_curve,
)

# ── Sample data ──────────────────────────────────────────────────────

# Normal upward-sloping curve (approx US Treasury mid-2024)
SAMPLE_TENORS = [0.25, 0.5, 1.0, 2.0, 3.0, 5.0, 7.0, 10.0, 20.0, 30.0]
SAMPLE_RATES = [0.0530, 0.0525, 0.0505, 0.0465, 0.0445, 0.0425, 0.0420, 0.0415, 0.0440, 0.0445]

# Inverted short-end curve
INVERTED_TENORS = [0.25, 1.0, 2.0, 5.0, 10.0, 30.0]
INVERTED_RATES = [0.055, 0.053, 0.050, 0.045, 0.042, 0.044]

# Real (TIPS) tenors/rates for breakeven tests
REAL_TENORS = [2.0, 5.0, 7.0, 10.0, 20.0, 30.0]
REAL_RATES = [0.0210, 0.0200, 0.0195, 0.0190, 0.0200, 0.0205]


# ── Nelson-Siegel model evaluation ──────────────────────────────────


class TestNelsonSiegelRate:
    def test_at_zero_tenor_returns_beta0_plus_beta1(self):
        """When t→0, NS rate should approach β0 + β1."""
        rate = _nelson_siegel_rate(0.0, beta0=0.05, beta1=-0.02, beta2=0.01, tau=2.0)
        assert abs(rate - 0.03) < 1e-8

    def test_at_long_tenor_approaches_beta0(self):
        """As t→∞, NS rate approaches β0."""
        rate = _nelson_siegel_rate(100.0, beta0=0.05, beta1=-0.02, beta2=0.01, tau=2.0)
        assert abs(rate - 0.05) < 0.001

    def test_positive_tenor(self):
        """NS rate at a normal tenor should be within reasonable range."""
        rate = _nelson_siegel_rate(5.0, beta0=0.05, beta1=-0.02, beta2=0.01, tau=2.0)
        assert 0.0 < rate < 0.10

    def test_negative_tau_returns_short_rate(self):
        rate = _nelson_siegel_rate(5.0, beta0=0.05, beta1=-0.02, beta2=0.01, tau=-1.0)
        assert abs(rate - 0.03) < 1e-8


# ── OLS 3x3 solver ──────────────────────────────────────────────────


class TestOLS3x3:
    def test_simple_system(self):
        """Verify OLS on a known system: y = 2 + 3*x1 - 1*x2."""
        X = [[1.0, 1.0, 0.0], [1.0, 0.0, 1.0], [1.0, 2.0, 1.0], [1.0, 1.0, 2.0]]
        y = [5.0, 1.0, 7.0, 3.0]
        betas = _ols_3x3(X, y)
        assert betas is not None
        # Expected: b0=2, b1=3, b2=-1
        assert abs(betas[0] - 2.0) < 0.01
        assert abs(betas[1] - 3.0) < 0.01
        assert abs(betas[2] - (-1.0)) < 0.01

    def test_singular_matrix_returns_none(self):
        """Collinear design matrix should return None."""
        X = [[1.0, 2.0, 4.0], [1.0, 3.0, 6.0], [1.0, 4.0, 8.0]]
        y = [1.0, 2.0, 3.0]
        result = _ols_3x3(X, y)
        assert result is None


# ── Nelson-Siegel fit ────────────────────────────────────────────────


class TestNelsonSiegelFit:
    def test_basic_fit(self):
        result = nelson_siegel_fit(SAMPLE_TENORS, SAMPLE_RATES)
        assert "beta0" in result
        assert "beta1" in result
        assert "beta2" in result
        assert "tau" in result
        assert "fit_error" in result
        assert "fitted_rates" in result
        # RMSE should be small for a reasonable curve
        assert result["fit_error"] < 0.005

    def test_fitted_rates_cover_standard_tenors(self):
        result = nelson_siegel_fit(SAMPLE_TENORS, SAMPLE_RATES)
        fitted = result["fitted_rates"]
        for tenor in STANDARD_TENORS:
            assert tenor in fitted, f"Missing standard tenor {tenor}"

    def test_fitted_rates_cover_input_tenors(self):
        result = nelson_siegel_fit(SAMPLE_TENORS, SAMPLE_RATES)
        fitted = result["fitted_rates"]
        for tenor in SAMPLE_TENORS:
            assert tenor in fitted, f"Missing input tenor {tenor}"

    def test_insufficient_data_raises(self):
        with pytest.raises(ValueError, match="at least 3"):
            nelson_siegel_fit([1.0, 2.0], [0.03, 0.04])

    def test_mismatched_lengths_raises(self):
        with pytest.raises(ValueError, match="equal length"):
            nelson_siegel_fit([1.0, 2.0, 3.0], [0.03, 0.04])


# ── Interpolation ───────────────────────────────────────────────────


class TestInterpolation:
    def test_linear_exact_match(self):
        """Interpolation at an exact tenor should return that rate."""
        rate = interpolate_rate(SAMPLE_TENORS, SAMPLE_RATES, 5.0)
        assert abs(rate - 0.0425) < 1e-10

    def test_linear_between_tenors(self):
        """Interpolation between tenors should be between the bounding rates."""
        rate = interpolate_rate(SAMPLE_TENORS, SAMPLE_RATES, 4.0)
        assert 0.0425 <= rate <= 0.0445

    def test_below_first_tenor(self):
        """Below shortest tenor → return first rate."""
        rate = interpolate_rate(SAMPLE_TENORS, SAMPLE_RATES, 0.01)
        assert abs(rate - SAMPLE_RATES[0]) < 1e-10

    def test_above_last_tenor(self):
        """Above longest tenor → return last rate."""
        rate = interpolate_rate(SAMPLE_TENORS, SAMPLE_RATES, 50.0)
        assert abs(rate - SAMPLE_RATES[-1]) < 1e-10

    def test_cubic_spline_at_knot(self):
        """Cubic spline should exactly match at knot points."""
        rate = interpolate_rate(SAMPLE_TENORS, SAMPLE_RATES, 5.0, method="CUBIC_SPLINE")
        assert abs(rate - 0.0425) < 1e-6

    def test_cubic_spline_between(self):
        rate = interpolate_rate(SAMPLE_TENORS, SAMPLE_RATES, 4.0, method="CUBIC_SPLINE")
        assert 0.040 < rate < 0.050

    def test_empty_tenors_raises(self):
        with pytest.raises(ValueError):
            interpolate_rate([], [], 5.0)


# ── Curve analytics ─────────────────────────────────────────────────


class TestCurveAnalytics:
    def test_normal_curve_not_inverted(self):
        # This sample has 10Y > 2Y but 3M > 10Y (partial inversion)
        analytics = compute_curve_analytics(SAMPLE_TENORS, SAMPLE_RATES)
        assert analytics["spread_2s10s"] is not None
        assert analytics["spread_3m10y"] is not None

    def test_inverted_curve_detected(self):
        analytics = compute_curve_analytics(INVERTED_TENORS, INVERTED_RATES)
        assert analytics["is_inverted"] is True
        assert analytics["spread_2s10s"] < 0

    def test_steepness_computed(self):
        analytics = compute_curve_analytics(SAMPLE_TENORS, SAMPLE_RATES)
        assert analytics["steepness"] is not None

    def test_curvature_butterfly(self):
        analytics = compute_curve_analytics(SAMPLE_TENORS, SAMPLE_RATES)
        assert analytics["curvature"] is not None

    def test_breakeven_with_real_rates(self):
        analytics = compute_curve_analytics(
            SAMPLE_TENORS, SAMPLE_RATES,
            real_tenors=REAL_TENORS, real_rates=REAL_RATES,
        )
        assert analytics["breakeven_5y"] is not None
        assert analytics["breakeven_10y"] is not None
        # Breakeven should be positive (nominal > real)
        assert analytics["breakeven_5y"] > 0
        assert analytics["breakeven_10y"] > 0


# ── Curve shifts ─────────────────────────────────────────────────────


class TestShiftCurve:
    def test_parallel_shift(self):
        shifted = shift_curve(SAMPLE_TENORS, SAMPLE_RATES, "PARALLEL", 100.0)
        assert len(shifted) == len(SAMPLE_TENORS)
        for pt in shifted:
            assert abs(pt["shift_bps"] - 100.0) < 0.01
            assert abs(pt["shifted_rate"] - pt["original_rate"] - 0.01) < 1e-8

    def test_steepener_shift(self):
        shifted = shift_curve(SAMPLE_TENORS, SAMPLE_RATES, "STEEPENER", 100.0)
        # Short end should be shifted down, long end up
        short_pt = shifted[0]  # 3M
        long_pt = shifted[-1]  # 30Y
        assert short_pt["shift_bps"] < 0
        assert long_pt["shift_bps"] > 0

    def test_flattener_shift(self):
        shifted = shift_curve(SAMPLE_TENORS, SAMPLE_RATES, "FLATTENER", 100.0)
        short_pt = shifted[0]
        long_pt = shifted[-1]
        assert short_pt["shift_bps"] > 0
        assert long_pt["shift_bps"] < 0

    def test_custom_shift(self):
        custom = {2.0: 50.0, 10.0: -25.0}
        shifted = shift_curve(SAMPLE_TENORS, SAMPLE_RATES, "CUSTOM", custom_shifts=custom)
        # Find the 2Y and 10Y points
        pt_2y = next(p for p in shifted if p["tenor_years"] == 2.0)
        pt_10y = next(p for p in shifted if p["tenor_years"] == 10.0)
        assert abs(pt_2y["shift_bps"] - 50.0) < 0.01
        assert abs(pt_10y["shift_bps"] - (-25.0)) < 0.01

    def test_unknown_shift_type_no_shift(self):
        shifted = shift_curve(SAMPLE_TENORS, SAMPLE_RATES, "UNKNOWN", 100.0)
        for pt in shifted:
            assert pt["shift_bps"] == 0.0


# ── Breakeven inflation ─────────────────────────────────────────────


class TestBreakevenInflation:
    def test_basic_breakeven(self):
        result = compute_breakeven_inflation(
            SAMPLE_TENORS, SAMPLE_RATES,
            REAL_TENORS, REAL_RATES,
        )
        # Should have entries for each real tenor
        assert len(result) == len(REAL_TENORS)
        # All breakevens should be positive (nominal > real)
        for t, be in result.items():
            assert be > 0, f"Breakeven at {t}Y should be positive"

    def test_matching_tenor_breakeven(self):
        """At a tenor present in both curves, breakeven = nominal - real."""
        nominal_tenors = [2.0, 5.0, 10.0]
        nominal_rates = [0.045, 0.042, 0.041]
        real_tenors = [5.0, 10.0]
        real_rates = [0.020, 0.019]
        result = compute_breakeven_inflation(
            nominal_tenors, nominal_rates, real_tenors, real_rates,
        )
        assert abs(result[5.0] - 0.022) < 1e-4
        assert abs(result[10.0] - 0.022) < 1e-4


# ── Slope helper ─────────────────────────────────────────────────────


class TestComputeSlope:
    def test_flat_curve(self):
        slope = _compute_slope([1.0, 5.0, 10.0], [0.04, 0.04, 0.04])
        assert slope is not None
        assert abs(slope) < 1e-8

    def test_upward_sloping(self):
        slope = _compute_slope([1.0, 5.0, 10.0], [0.03, 0.04, 0.05])
        assert slope is not None
        assert slope > 0

    def test_single_point_returns_none(self):
        slope = _compute_slope([5.0], [0.04])
        assert slope is None
