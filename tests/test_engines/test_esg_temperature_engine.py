"""Tests for the ESG temperature scoring engine."""

import pytest

from src.engines.esg_temperature import (
    classify_alignment,
    compute_emissions_trend,
    score_temperature,
)


class TestClassifyAlignment:
    def test_below_1_5(self):
        assert classify_alignment(1.3) == "BELOW_1_5C"

    def test_between_1_5_and_2(self):
        assert classify_alignment(1.8) == "BETWEEN_1_5_AND_2C"

    def test_between_2_and_3(self):
        assert classify_alignment(2.5) == "BETWEEN_2_AND_3C"

    def test_above_3(self):
        assert classify_alignment(3.5) == "ABOVE_3C"

    def test_boundary_1_5(self):
        assert classify_alignment(1.5) == "BELOW_1_5C"

    def test_boundary_2_0(self):
        assert classify_alignment(2.0) == "BETWEEN_1_5_AND_2C"


class TestComputeEmissionsTrend:
    def test_flat(self):
        result = compute_emissions_trend([100, 100, 100])
        assert result == pytest.approx(0.0, abs=0.01)

    def test_increasing(self):
        result = compute_emissions_trend([100, 110])
        assert result is not None
        assert result > 0

    def test_decreasing(self):
        result = compute_emissions_trend([100, 90])
        assert result is not None
        assert result < 0

    def test_insufficient_data(self):
        assert compute_emissions_trend([100]) is None
        assert compute_emissions_trend([]) is None

    def test_zero_start(self):
        assert compute_emissions_trend([0, 100]) is None


class TestScoreTemperature:
    def test_insufficient_data(self):
        result = score_temperature(1000, emissions_trend_pct=None)
        assert result.alignment == "INSUFFICIENT_DATA"
        assert result.data_quality_flag == "INSUFFICIENT"

    def test_declining_emissions(self):
        result = score_temperature(100, emissions_trend_pct=-5.0, has_scope3=True)
        assert result.implied_temperature > 0
        assert result.data_quality_flag == "FULL"
        # Strongly declining → should be lower temperature
        assert result.implied_temperature < 3.0

    def test_growing_emissions(self):
        result = score_temperature(500, emissions_trend_pct=5.0)
        assert result.implied_temperature > 1.0
        assert result.data_quality_flag == "PARTIAL"

    def test_scope3_flag(self):
        r1 = score_temperature(100, emissions_trend_pct=0.0, has_scope3=False)
        r2 = score_temperature(100, emissions_trend_pct=0.0, has_scope3=True)
        assert r1.data_quality_flag == "PARTIAL"
        assert r2.data_quality_flag == "FULL"
