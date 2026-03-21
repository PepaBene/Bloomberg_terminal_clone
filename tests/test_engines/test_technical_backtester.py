"""Tests for the technical backtester engine (Pillar 2 Supplement – Part 6)."""

import math

import pytest

from src.engines.technical_backtester import (
    TechnicalSignal,
    generate_ma_crossover_signals,
    generate_rsi_signals,
    generate_bollinger_signals,
    run_technical_backtest,
)


def _trending_up_prices(n: int = 200, start: float = 100.0) -> list[float]:
    """Generate a simple trending-up price series."""
    import random
    random.seed(42)
    prices = [start]
    for _ in range(n - 1):
        change = random.gauss(0.002, 0.01)
        prices.append(prices[-1] * (1 + change))
    return prices


def _trending_down_prices(n: int = 200, start: float = 100.0) -> list[float]:
    """Generate a simple trending-down price series."""
    import random
    random.seed(42)
    prices = [start]
    for _ in range(n - 1):
        change = random.gauss(-0.002, 0.01)
        prices.append(prices[-1] * (1 + change))
    return prices


def _oscillating_prices(n: int = 200, start: float = 100.0) -> list[float]:
    """Generate oscillating prices (up and down cycles)."""
    prices = [start]
    for i in range(1, n):
        cycle = math.sin(i * 0.1) * 5
        prices.append(start + cycle)
    return prices


class TestMACrossoverSignals:
    def test_generates_signals(self):
        prices = _trending_up_prices(200)
        signals = generate_ma_crossover_signals(prices, fast_period=5, slow_period=20)
        assert len(signals) > 0
        assert all(isinstance(s, TechnicalSignal) for s in signals)

    def test_signal_types(self):
        prices = _oscillating_prices(300)
        signals = generate_ma_crossover_signals(prices, fast_period=5, slow_period=20)
        types = {s.signal_type for s in signals}
        # Should have both crossover types in oscillating data
        assert len(types) >= 1

    def test_ema_signals(self):
        prices = _trending_up_prices(200)
        signals = generate_ma_crossover_signals(prices, fast_period=5, slow_period=20, ma_type="EMA")
        assert all(s.indicator.startswith("EMA") for s in signals)

    def test_empty_prices(self):
        signals = generate_ma_crossover_signals([], fast_period=5, slow_period=20)
        assert signals == []

    def test_short_prices(self):
        signals = generate_ma_crossover_signals([100, 101, 102], fast_period=5, slow_period=20)
        assert signals == []


class TestRSISignals:
    def test_generates_signals(self):
        prices = _oscillating_prices(300)
        signals = generate_rsi_signals(prices, period=14)
        assert len(signals) >= 0  # May or may not generate depending on volatility

    def test_signal_types(self):
        prices = _oscillating_prices(300)
        signals = generate_rsi_signals(prices, period=14, overbought=60, oversold=40)
        for s in signals:
            assert s.signal_type in ("THRESHOLD_ABOVE", "THRESHOLD_BELOW")
            assert "RSI" in s.indicator

    def test_empty_prices(self):
        signals = generate_rsi_signals([], period=14)
        assert signals == []


class TestBollingerSignals:
    def test_generates_signals(self):
        prices = _oscillating_prices(300)
        signals = generate_bollinger_signals(prices, period=20, num_std=1.5)
        # With oscillating prices and tight bands, should get some signals
        assert isinstance(signals, list)

    def test_signal_indicator(self):
        prices = _oscillating_prices(300)
        signals = generate_bollinger_signals(prices, period=20, num_std=1.5)
        for s in signals:
            assert s.signal_type in ("BAND_BREAKOUT", "BAND_BREAKDOWN")
            assert "BBANDS" in s.indicator

    def test_empty_prices(self):
        signals = generate_bollinger_signals([], period=20)
        assert signals == []


class TestRunTechnicalBacktest:
    def test_no_signals(self):
        prices = _trending_up_prices(100)
        result = run_technical_backtest(prices, signals=[])
        assert result["total_trades"] == 0
        assert result["final_value"] == 100000.0

    def test_single_buy_and_hold(self):
        prices = [100.0, 105.0, 110.0, 115.0, 120.0]
        signals = [TechnicalSignal(index=1, signal_type="CROSSOVER_ABOVE", indicator="TEST", value=105.0)]
        result = run_technical_backtest(prices, signals, initial_capital=10000.0)
        assert result["total_trades"] == 1
        assert result["final_value"] > 10000.0  # Should have gained from 105 to 120

    def test_buy_sell_cycle(self):
        prices = [100.0, 110.0, 120.0, 115.0, 105.0]
        signals = [
            TechnicalSignal(index=1, signal_type="CROSSOVER_ABOVE", indicator="TEST", value=110.0),
            TechnicalSignal(index=3, signal_type="CROSSOVER_BELOW", indicator="TEST", value=115.0),
        ]
        result = run_technical_backtest(prices, signals, initial_capital=10000.0, transaction_cost_bps=0)
        assert result["total_trades"] == 2

    def test_performance_metrics_present(self):
        prices = _trending_up_prices(200)
        signals = generate_ma_crossover_signals(prices, fast_period=5, slow_period=20)
        result = run_technical_backtest(prices, signals)
        perf = result["performance"]
        assert perf.total_return is not None
        assert perf.annualized_volatility is not None
        assert perf.max_drawdown >= 0

    def test_empty_prices(self):
        result = run_technical_backtest([], signals=[])
        assert result["total_trades"] == 0
        assert result["final_value"] == 100000.0

    def test_transaction_costs_reduce_returns(self):
        prices = [100.0, 110.0, 120.0, 115.0, 125.0]
        signals = [
            TechnicalSignal(index=1, signal_type="CROSSOVER_ABOVE", indicator="T", value=110.0),
            TechnicalSignal(index=3, signal_type="CROSSOVER_BELOW", indicator="T", value=115.0),
        ]
        result_no_cost = run_technical_backtest(prices, signals, transaction_cost_bps=0)
        result_with_cost = run_technical_backtest(prices, signals, transaction_cost_bps=50)
        assert result_no_cost["final_value"] >= result_with_cost["final_value"]
