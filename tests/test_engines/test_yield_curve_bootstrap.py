"""Tests for the yield curve bootstrapping engine."""

import math

import pytest

from src.engines.yield_curve_bootstrap import bootstrap_zero_curve, compute_spread


def test_bootstrap_single_tenor():
    """Test bootstrap with a single short tenor."""
    result = bootstrap_zero_curve([1.0], [0.05])
    assert len(result) == 1
    assert result[0]["tenor_years"] == 1.0
    assert result[0]["zero_rate"] == pytest.approx(0.05, abs=0.001)
    assert result[0]["discount_factor"] > 0
    assert result[0]["discount_factor"] < 1


def test_bootstrap_short_tenors():
    """Test that short tenors (≤1yr) use simple zero rate = par rate."""
    tenors = [0.25, 0.5, 1.0]
    par_rates = [0.053, 0.052, 0.048]
    results = bootstrap_zero_curve(tenors, par_rates)
    assert len(results) == 3
    # For short tenors, zero_rate should equal par_rate
    for r, p in zip(results, par_rates):
        assert r["zero_rate"] == pytest.approx(p, abs=0.001)


def test_bootstrap_multiple_tenors():
    """Test bootstrap with a full curve."""
    tenors = [0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0]
    par_rates = [0.053, 0.052, 0.048, 0.0445, 0.042, 0.0435, 0.046]
    results = bootstrap_zero_curve(tenors, par_rates)

    assert len(results) == 7

    # All discount factors should be positive and ≤ 1
    for r in results:
        assert r["discount_factor"] > 0
        assert r["discount_factor"] <= 1.0

    # Discount factors should be monotonically decreasing with tenor
    dfs = [r["discount_factor"] for r in results]
    for i in range(1, len(dfs)):
        assert dfs[i] <= dfs[i - 1]


def test_bootstrap_forward_rates_positive():
    """Test that forward rates are computed and positive for normal curve."""
    tenors = [1.0, 2.0, 5.0]
    par_rates = [0.04, 0.042, 0.045]
    results = bootstrap_zero_curve(tenors, par_rates)

    for r in results:
        assert r["forward_rate"] > 0


def test_bootstrap_empty():
    """Test bootstrap with empty inputs."""
    result = bootstrap_zero_curve([], [])
    assert result == []


def test_bootstrap_mismatched_lengths():
    """Test that mismatched lengths raise ValueError."""
    with pytest.raises(ValueError, match="same length"):
        bootstrap_zero_curve([1.0, 2.0], [0.05])


def test_discount_factor_formula():
    """Verify discount factor from zero rate: DF = 1 / (1 + r*t) for short tenors."""
    tenors = [0.5]
    par_rates = [0.06]
    results = bootstrap_zero_curve(tenors, par_rates)
    expected_df = 1.0 / (1.0 + 0.06 * 0.5)
    assert results[0]["discount_factor"] == pytest.approx(expected_df, abs=0.0001)


def test_compute_spread():
    """Test spread computation."""
    assert compute_spread(0.04, 0.05) == pytest.approx(0.01)
    assert compute_spread(0.05, 0.04) == pytest.approx(-0.01)
    assert compute_spread(None, 0.05) is None
    assert compute_spread(0.04, None) is None
