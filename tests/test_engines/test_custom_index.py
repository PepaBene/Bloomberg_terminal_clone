"""Tests for the custom index engine (Pillar 2 Supplement – Part 4)."""

import pytest

from src.engines.custom_index import (
    compute_index_performance,
    compute_index_weights,
    rebalance_index,
)


class TestComputeIndexWeights:
    def test_equal_weight(self):
        result = compute_index_weights(["A", "B", "C", "D"], method="EQUAL")
        assert len(result) == 4
        assert all(abs(w - 0.25) < 0.001 for w in result.values())

    def test_market_cap_weight(self):
        result = compute_index_weights(
            ["A", "B", "C"], method="MARKET_CAP",
            market_caps=[100, 200, 300],
        )
        assert result["C"] > result["B"] > result["A"]
        assert abs(sum(result.values()) - 1.0) < 0.01

    def test_score_based_weight(self):
        result = compute_index_weights(
            ["A", "B", "C"], method="SCORE_BASED",
            scores=[10, 30, 60],
        )
        assert result["C"] > result["B"] > result["A"]

    def test_max_constituents(self):
        result = compute_index_weights(
            ["A", "B", "C", "D", "E"], method="EQUAL",
            max_constituents=3,
        )
        assert len(result) == 3

    def test_empty(self):
        assert compute_index_weights([]) == {}

    def test_market_cap_no_caps_falls_to_equal(self):
        result = compute_index_weights(["A", "B"], method="MARKET_CAP")
        assert len(result) == 2


class TestComputeIndexPerformance:
    def test_basic_positive(self):
        returns = [0.01, 0.02, -0.005, 0.015]
        result = compute_index_performance(returns, base_level=1000.0)
        assert len(result) == 4
        assert result[0]["index_level"] > 1000.0
        assert result[0]["daily_return"] == pytest.approx(0.01, abs=1e-6)

    def test_cumulative_return(self):
        returns = [0.10]  # 10% gain
        result = compute_index_performance(returns, base_level=1000.0)
        assert result[0]["cumulative_return"] == pytest.approx(0.10, abs=0.001)

    def test_empty_returns(self):
        assert compute_index_performance([]) == []


class TestRebalanceIndex:
    def test_basic_rebalance(self):
        current = {"A": 0.5, "B": 0.5}
        target = {"A": 0.3, "B": 0.4, "C": 0.3}
        result = rebalance_index(current, target)
        assert len(result["trades"]) == 3
        assert result["total_turnover"] > 0

    def test_no_rebalance_needed(self):
        weights = {"A": 0.5, "B": 0.5}
        result = rebalance_index(weights, weights)
        assert len(result["trades"]) == 0
        assert result["total_turnover"] == 0.0

    def test_full_replacement(self):
        current = {"A": 0.5, "B": 0.5}
        target = {"C": 0.5, "D": 0.5}
        result = rebalance_index(current, target)
        assert len(result["trades"]) == 4  # sell A, B; buy C, D
        assert result["total_turnover"] == pytest.approx(2.0, abs=0.01)

    def test_transaction_cost(self):
        current = {"A": 0.5, "B": 0.5}
        target = {"A": 0.3, "B": 0.7}
        result = rebalance_index(current, target, transaction_cost_bps=10.0)
        assert result["cost_bps"] > 0
