"""Tests for Credit Spread Analytics Engine (D11 FI Supplement P6)."""

import pytest

from src.engines.credit_spread_analytics import (
    BAML_SERIES,
    compute_ig_hy_differential,
    compute_spread_percentile,
    detect_spread_regime,
)


def test_percentile_at_median():
    """Value at median of evenly distributed data -> ~50th percentile."""
    values = list(range(1, 101))  # 1..100
    result = compute_spread_percentile(values, 50.0)
    assert result["percentile"] == pytest.approx(50.0, abs=1.0)


def test_percentile_at_min():
    """Value at min -> low percentile (1% since min is <= itself)."""
    values = list(range(1, 101))
    result = compute_spread_percentile(values, 1.0)
    assert result["percentile"] == pytest.approx(1.0, abs=1.0)


def test_percentile_at_max():
    """Value at max -> 100th percentile."""
    values = list(range(1, 101))
    result = compute_spread_percentile(values, 100.0)
    assert result["percentile"] == pytest.approx(100.0, abs=1.0)


def test_z_score():
    """Z-score for known distribution properties."""
    values = [100.0, 200.0, 300.0, 400.0, 500.0]
    result = compute_spread_percentile(values, 300.0)
    # Mean = 300, current = 300 -> z-score should be ~0
    assert result["z_score"] == pytest.approx(0.0, abs=0.01)
    assert result["mean_val"] == pytest.approx(300.0, abs=0.01)
    assert result["min_val"] == pytest.approx(100.0, abs=0.01)
    assert result["max_val"] == pytest.approx(500.0, abs=0.01)
    assert result["std_dev"] > 0


def test_regime_tight():
    """Percentile 15 -> TIGHT."""
    assert detect_spread_regime(15.0) == "TIGHT"


def test_regime_normal():
    """Percentile 50 -> NORMAL."""
    assert detect_spread_regime(50.0) == "NORMAL"


def test_regime_wide():
    """Percentile 80 -> WIDE."""
    assert detect_spread_regime(80.0) == "WIDE"


def test_regime_crisis():
    """Percentile 95 -> CRISIS."""
    assert detect_spread_regime(95.0) == "CRISIS"


def test_ig_hy_differential():
    """ig=120, hy=450 -> ratio ~3.75, spread=330."""
    result = compute_ig_hy_differential(120.0, 450.0)
    assert result["ratio"] == pytest.approx(3.75, abs=0.01)
    assert result["spread"] == pytest.approx(330.0, abs=0.01)


def test_baml_series_count():
    """BAML_SERIES should have 11 entries."""
    assert len(BAML_SERIES) == 11
