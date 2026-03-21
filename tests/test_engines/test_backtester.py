"""Tests for the backtester engine (Pillar 2 Supplement – Part 3)."""

import math

import pytest

from src.engines.backtester import (
    BacktestConfig,
    PerformanceMetrics,
    compute_performance_metrics,
    equal_weight_portfolio,
    market_cap_weight_portfolio,
    parse_strategy,
    score_based_weight_portfolio,
)


# ── Sample data ──────────────────────────────────────────────────────

# Simulate 252 daily returns (1 year) with slight positive drift
POSITIVE_RETURNS = [0.001 + 0.002 * math.sin(i / 10) for i in range(252)]
# A losing period
NEGATIVE_RETURNS = [-0.002 + 0.001 * math.cos(i / 8) for i in range(252)]
# Benchmark returns
BENCHMARK_RETURNS = [0.0005 + 0.001 * math.sin(i / 12) for i in range(252)]


# ── Performance Metrics ──────────────────────────────────────────────


class TestPerformanceMetrics:
    def test_basic_positive_returns(self):
        metrics = compute_performance_metrics(POSITIVE_RETURNS)
        assert isinstance(metrics, PerformanceMetrics)
        assert metrics.total_return > 0
        assert metrics.annualized_return > 0
        assert metrics.annualized_volatility > 0
        assert metrics.max_drawdown >= 0
        assert 0 < metrics.win_rate <= 1

    def test_sharpe_ratio_positive(self):
        metrics = compute_performance_metrics(POSITIVE_RETURNS)
        assert metrics.sharpe_ratio is not None
        assert metrics.sharpe_ratio > 0

    def test_sortino_ratio(self):
        metrics = compute_performance_metrics(POSITIVE_RETURNS)
        assert metrics.sortino_ratio is not None
        # Sortino should typically be >= Sharpe for positive returns with limited downside
        assert metrics.sortino_ratio > 0

    def test_with_benchmark(self):
        metrics = compute_performance_metrics(
            POSITIVE_RETURNS, benchmark_returns=BENCHMARK_RETURNS,
        )
        assert metrics.beta is not None
        assert metrics.tracking_error is not None
        assert metrics.information_ratio is not None

    def test_beta_range(self):
        metrics = compute_performance_metrics(
            POSITIVE_RETURNS, benchmark_returns=BENCHMARK_RETURNS,
        )
        # Beta should be reasonable (not extreme)
        assert metrics.beta is not None
        assert -5 < metrics.beta < 5

    def test_max_drawdown_bounds(self):
        metrics = compute_performance_metrics(POSITIVE_RETURNS)
        assert 0 <= metrics.max_drawdown <= 1.0
        assert metrics.max_drawdown_duration_days >= 0

    def test_negative_returns_metrics(self):
        metrics = compute_performance_metrics(NEGATIVE_RETURNS)
        assert metrics.total_return < 0
        assert metrics.sharpe_ratio is not None
        assert metrics.sharpe_ratio < 0

    def test_empty_returns(self):
        metrics = compute_performance_metrics([])
        assert metrics.total_return == 0.0
        assert metrics.annualized_return == 0.0
        assert metrics.sharpe_ratio is None

    def test_single_return(self):
        metrics = compute_performance_metrics([0.05])
        assert metrics.total_return == pytest.approx(0.05, abs=0.001)

    def test_win_rate_all_positive(self):
        metrics = compute_performance_metrics([0.01, 0.02, 0.03])
        assert metrics.win_rate == pytest.approx(1.0, abs=0.001)

    def test_win_rate_all_negative(self):
        metrics = compute_performance_metrics([-0.01, -0.02, -0.03])
        assert metrics.win_rate == pytest.approx(0.0, abs=0.001)

    def test_avg_win_and_loss(self):
        returns = [0.02, -0.01, 0.03, -0.02, 0.01]
        metrics = compute_performance_metrics(returns)
        assert metrics.avg_win > 0
        assert metrics.avg_loss < 0

    def test_zero_volatility(self):
        """Constant returns should have zero vol and no Sharpe."""
        metrics = compute_performance_metrics([0.001] * 100)
        assert metrics.annualized_volatility == pytest.approx(0.0, abs=1e-6)
        assert metrics.sharpe_ratio is None  # division by zero guard

    def test_risk_free_rate(self):
        """Non-zero risk-free rate should lower Sharpe."""
        metrics_no_rf = compute_performance_metrics(POSITIVE_RETURNS, risk_free_rate=0.0)
        metrics_with_rf = compute_performance_metrics(POSITIVE_RETURNS, risk_free_rate=0.05)
        if metrics_no_rf.sharpe_ratio is not None and metrics_with_rf.sharpe_ratio is not None:
            assert metrics_with_rf.sharpe_ratio < metrics_no_rf.sharpe_ratio


# ── Portfolio Weighting ──────────────────────────────────────────────


class TestEqualWeightPortfolio:
    def test_basic(self):
        result = equal_weight_portfolio(["A", "B", "C", "D"])
        assert len(result) == 4
        assert all(abs(w - 0.25) < 0.001 for w in result.values())

    def test_max_positions(self):
        result = equal_weight_portfolio(["A", "B", "C", "D", "E"], max_positions=3)
        assert len(result) == 3

    def test_empty(self):
        result = equal_weight_portfolio([])
        assert result == {}

    def test_single(self):
        result = equal_weight_portfolio(["A"])
        assert result == {"A": 1.0}


class TestMarketCapWeightPortfolio:
    def test_basic(self):
        result = market_cap_weight_portfolio(
            ["A", "B", "C"], [100, 200, 300],
        )
        assert len(result) == 3
        assert result["C"] > result["B"] > result["A"]
        total = sum(result.values())
        assert abs(total - 1.0) < 0.01

    def test_max_positions(self):
        result = market_cap_weight_portfolio(
            ["A", "B", "C", "D"], [100, 400, 200, 300], max_positions=2,
        )
        assert len(result) == 2
        assert "B" in result  # largest
        assert "D" in result  # second largest

    def test_mismatched_lengths(self):
        result = market_cap_weight_portfolio(["A", "B"], [100])
        assert result == {}


class TestScoreBasedWeightPortfolio:
    def test_basic(self):
        result = score_based_weight_portfolio(
            ["A", "B", "C"], [10, 20, 30],
        )
        assert len(result) == 3
        assert result["C"] > result["B"] > result["A"]

    def test_all_zero_scores_equal_weight(self):
        result = score_based_weight_portfolio(
            ["A", "B", "C"], [0, 0, 0],
        )
        assert len(result) == 3
        # Should fall back to equal weight
        assert all(abs(w - 1/3) < 0.01 for w in result.values())


# ── Strategy Parsing ─────────────────────────────────────────────────


class TestParseStrategy:
    def test_basic(self):
        config = parse_strategy({
            "name": "Value Strategy",
            "start_date": "2020-01-01",
            "end_date": "2023-12-31",
            "benchmark": "SP500",
            "weighting_method": "EQUAL",
            "max_positions": 50,
        })
        assert isinstance(config, BacktestConfig)
        assert config.name == "Value Strategy"
        assert config.max_positions == 50

    def test_defaults(self):
        config = parse_strategy({})
        assert config.name == "Unnamed Strategy"
        assert config.benchmark == "SP500"
        assert config.weighting_method == "EQUAL"
        assert config.rebalance_frequency == "QUARTERLY"
        assert config.max_positions == 30
        assert config.transaction_cost_bps == 10.0
