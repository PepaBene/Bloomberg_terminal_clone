"""Tests for the technical studies computation engine."""

import math

import pytest

from src.engines.technical_studies import (
    atr,
    bollinger_bands,
    ema,
    macd,
    obv,
    rsi,
    sma,
    stochastic,
    vwap,
)


class TestSMA:
    def test_basic(self):
        prices = [1, 2, 3, 4, 5]
        result = sma(prices, 3)
        assert result[0] is None
        assert result[1] is None
        assert result[2] == pytest.approx(2.0)
        assert result[4] == pytest.approx(4.0)

    def test_period_equals_length(self):
        prices = [10, 20, 30]
        result = sma(prices, 3)
        assert result[2] == pytest.approx(20.0)

    def test_insufficient_data(self):
        result = sma([1, 2], 5)
        assert all(v is None for v in result)


class TestEMA:
    def test_basic(self):
        prices = [22, 22.27, 22.19, 22.08, 22.17, 22.18, 22.13, 22.23, 22.43, 22.24]
        result = ema(prices, 5)
        assert result[3] is None
        assert result[4] is not None  # First EMA = SMA seed
        assert result[4] == pytest.approx(sum(prices[:5]) / 5)

    def test_insufficient_data(self):
        result = ema([1, 2], 5)
        assert all(v is None for v in result)


class TestRSI:
    def test_overbought(self):
        # Monotonically rising prices → RSI near 100
        prices = list(range(1, 20))
        result = rsi(prices, 14)
        last_val = result[-1]
        assert last_val is not None
        assert last_val > 90

    def test_oversold(self):
        # Monotonically falling prices → RSI near 0
        prices = list(range(20, 1, -1))
        result = rsi(prices, 14)
        last_val = result[-1]
        assert last_val is not None
        assert last_val < 10

    def test_insufficient_data(self):
        result = rsi([1, 2, 3], 14)
        assert all(v is None for v in result)


class TestMACD:
    def test_basic_structure(self):
        # 40 data points should produce some MACD values
        prices = [100 + i * 0.5 for i in range(40)]
        result = macd(prices, fast=12, slow=26, signal_period=9)
        assert "macd" in result
        assert "signal" in result
        assert "histogram" in result
        assert len(result["macd"]) == 40

    def test_trend_detection(self):
        # Uptrend → MACD should be positive after convergence
        prices = [100 + i for i in range(50)]
        result = macd(prices)
        # After slow EMA kicks in (index 25), MACD should be positive
        late_values = [v for v in result["macd"][30:] if v is not None]
        assert all(v > 0 for v in late_values)


class TestBollingerBands:
    def test_basic(self):
        prices = [20 + i * 0.1 for i in range(30)]
        result = bollinger_bands(prices, period=20, num_std=2.0)
        assert result["upper"][19] is not None
        assert result["middle"][19] is not None
        assert result["lower"][19] is not None
        # Upper > middle > lower
        assert result["upper"][19] > result["middle"][19] > result["lower"][19]

    def test_constant_prices(self):
        prices = [100.0] * 25
        result = bollinger_bands(prices, period=20, num_std=2.0)
        # All bands should equal the constant price (std dev = 0)
        assert result["upper"][24] == pytest.approx(100.0)
        assert result["lower"][24] == pytest.approx(100.0)


class TestStochastic:
    def test_basic(self):
        highs = [50 + i for i in range(20)]
        lows = [48 + i for i in range(20)]
        closes = [49 + i for i in range(20)]
        result = stochastic(highs, lows, closes, k_period=14, d_period=3)
        assert result["k"][13] is not None
        # Close is near the top of the range in an uptrend → high %K
        assert result["k"][-1] > 50


class TestATR:
    def test_basic(self):
        highs = [10 + i * 0.1 for i in range(20)]
        lows = [9 + i * 0.1 for i in range(20)]
        closes = [9.5 + i * 0.1 for i in range(20)]
        result = atr(highs, lows, closes, period=14)
        assert result[13] is not None
        # ATR should be roughly 1.0 (high - low)
        assert result[13] == pytest.approx(1.0, abs=0.2)


class TestOBV:
    def test_basic(self):
        closes = [10, 11, 10.5, 11.5, 12]
        volumes = [100, 200, 150, 300, 250]
        result = obv(closes, volumes)
        assert len(result) == 5
        assert result[0] == 100  # First volume
        assert result[1] == 300  # Up day: 100 + 200
        assert result[2] == 150  # Down day: 300 - 150

    def test_empty(self):
        assert obv([], []) == []


class TestVWAP:
    def test_basic(self):
        highs = [10, 11, 12]
        lows = [9, 10, 11]
        closes = [9.5, 10.5, 11.5]
        volumes = [100, 200, 300]
        result = vwap(highs, lows, closes, volumes)
        assert len(result) == 3
        # First VWAP = typical price of first bar
        tp0 = (10 + 9 + 9.5) / 3
        assert result[0] == pytest.approx(tp0)
