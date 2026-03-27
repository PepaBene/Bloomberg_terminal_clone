"""Tests for the D11 FI Supplement yield curve engine functions."""

import math

import pytest

from src.engines.yield_curve_bootstrap import enhanced_bootstrap
from src.engines.yield_curve_analytics import (
    compute_butterfly_spread,
    compute_spread_5s30s,
    nelson_siegel_svensson_evaluate,
    nelson_siegel_svensson_fit,
)


# ── Sample data ──────────────────────────────────────────────────────

FULL_PAR_RATES = {
    "1M": 0.0535, "3M": 0.0530, "6M": 0.0525,
    "1Y": 0.0505, "2Y": 0.0465, "3Y": 0.0445,
    "5Y": 0.0425, "7Y": 0.0420, "10Y": 0.0415,
    "20Y": 0.0440, "30Y": 0.0445,
}

REALISTIC_TENORS = [0.083, 0.25, 0.5, 1.0, 2.0, 3.0, 5.0, 7.0, 10.0, 20.0, 30.0]
REALISTIC_RATES = [0.0535, 0.0530, 0.0525, 0.0505, 0.0465, 0.0445, 0.0425, 0.0420, 0.0415, 0.0440, 0.0445]


# ── Enhanced bootstrap tests ─────────────────────────────────────────


class TestEnhancedBootstrap:
    def test_enhanced_bootstrap(self):
        """Supply full par rates, verify zero/df/fwd outputs are non-empty."""
        result = enhanced_bootstrap(FULL_PAR_RATES)
        assert "par" in result
        assert "zero" in result
        assert "discount_factors" in result
        assert "forwards" in result
        assert len(result["zero"]) > 0
        assert len(result["discount_factors"]) > 0
        assert len(result["forwards"]) > 0
        # Zero rates should be positive
        for tenor, rate in result["zero"].items():
            assert rate is not None
            assert rate > 0, f"Zero rate at {tenor} should be positive"

    def test_enhanced_bootstrap_empty(self):
        """Empty dict should return empty outputs."""
        result = enhanced_bootstrap({})
        assert result["par"] == {}
        assert result["zero"] == {}
        assert result["discount_factors"] == {}
        assert result["forwards"] == {}

    def test_enhanced_bootstrap_partial(self):
        """Only 3 tenors should still work."""
        partial = {"1Y": 0.05, "5Y": 0.045, "10Y": 0.042}
        result = enhanced_bootstrap(partial)
        assert len(result["zero"]) == 3
        assert len(result["discount_factors"]) == 3
        assert len(result["forwards"]) == 3


# ── Butterfly and 5s30s spread tests ─────────────────────────────────


class TestButterflySpread:
    def test_butterfly_spread(self):
        """2Y=4.0, 5Y=4.2, 10Y=4.5 → 2*4.2 - 4.0 - 4.5 = -0.1"""
        result = compute_butterfly_spread(4.0, 4.2, 4.5)
        assert abs(result - (-0.1)) < 1e-10

    def test_butterfly_spread_positive(self):
        """When 5Y is high relative to wings → positive butterfly."""
        result = compute_butterfly_spread(3.0, 5.0, 4.0)
        assert result > 0
        assert abs(result - 3.0) < 1e-10  # 2*5 - 3 - 4 = 3


class TestSpread5s30s:
    def test_spread_5s30s(self):
        """5Y=4.0, 30Y=4.8 → 0.8"""
        result = compute_spread_5s30s(4.0, 4.8)
        assert abs(result - 0.8) < 1e-10


# ── Nelson-Siegel-Svensson tests ─────────────────────────────────────


class TestNSVEvaluate:
    def test_nsv_evaluate_short_end(self):
        """At t→0, NSV should approach beta0 + beta1."""
        rate = nelson_siegel_svensson_evaluate(
            0.0, beta0=0.05, beta1=-0.02, beta2=0.01, beta3=0.005,
            lambda1=1.5, lambda2=5.0,
        )
        assert abs(rate - 0.03) < 1e-8

    def test_nsv_evaluate_long_end(self):
        """At t→∞, NSV should approach beta0."""
        rate = nelson_siegel_svensson_evaluate(
            200.0, beta0=0.05, beta1=-0.02, beta2=0.01, beta3=0.005,
            lambda1=1.5, lambda2=5.0,
        )
        assert abs(rate - 0.05) < 0.001

    def test_nsv_evaluate_mid_curve(self):
        """Evaluate at t=5 with known params, should be within range."""
        rate = nelson_siegel_svensson_evaluate(
            5.0, beta0=0.05, beta1=-0.02, beta2=0.01, beta3=0.005,
            lambda1=1.5, lambda2=5.0,
        )
        # Rate should be between beta0+beta1 (0.03) and beta0 (0.05)
        assert 0.02 < rate < 0.06


class TestNSVFit:
    def test_nsv_fit_realistic(self):
        """Fit to realistic US Treasury rates, verify fit_error < 0.005."""
        result = nelson_siegel_svensson_fit(REALISTIC_TENORS, REALISTIC_RATES)
        assert result["fit_error"] < 0.005
        assert "beta0" in result
        assert "beta1" in result
        assert "beta2" in result
        assert "beta3" in result
        assert "lambda1" in result
        assert "lambda2" in result

    def test_nsv_fit_insufficient_data(self):
        """Fewer than 4 points should return inf error."""
        result = nelson_siegel_svensson_fit([1.0, 2.0, 5.0], [0.04, 0.042, 0.043])
        assert result["fit_error"] == float("inf")

    def test_nsv_fit_roundtrip(self):
        """Fit, then evaluate at original tenors, verify residuals are small."""
        result = nelson_siegel_svensson_fit(REALISTIC_TENORS, REALISTIC_RATES)
        if result["fit_error"] == float("inf"):
            pytest.skip("NSV fit did not converge")

        max_residual = 0.0
        for t, r in zip(REALISTIC_TENORS, REALISTIC_RATES):
            fitted = nelson_siegel_svensson_evaluate(
                t, result["beta0"], result["beta1"], result["beta2"],
                result["beta3"], result["lambda1"], result["lambda2"],
            )
            residual = abs(fitted - r)
            max_residual = max(max_residual, residual)

        assert max_residual < 0.01, f"Max residual {max_residual} too large"
