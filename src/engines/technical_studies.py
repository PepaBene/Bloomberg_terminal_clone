"""Technical indicator computation engine.

Computes standard technical indicators from OHLCV price data.
All functions accept lists/arrays of floats and return lists of floats.
NaN-safe: leading periods without enough data produce None values.
"""

from __future__ import annotations

import math


# ---------------------------------------------------------------------------
# Moving averages
# ---------------------------------------------------------------------------

def sma(prices: list[float], period: int) -> list[float | None]:
    """Simple Moving Average."""
    result: list[float | None] = [None] * len(prices)
    for i in range(period - 1, len(prices)):
        result[i] = sum(prices[i - period + 1 : i + 1]) / period
    return result


def ema(prices: list[float], period: int) -> list[float | None]:
    """Exponential Moving Average."""
    result: list[float | None] = [None] * len(prices)
    if len(prices) < period:
        return result
    # Seed with SMA
    result[period - 1] = sum(prices[:period]) / period
    k = 2 / (period + 1)
    for i in range(period, len(prices)):
        prev = result[i - 1]
        if prev is not None:
            result[i] = prices[i] * k + prev * (1 - k)
    return result


# ---------------------------------------------------------------------------
# RSI
# ---------------------------------------------------------------------------

def rsi(prices: list[float], period: int = 14) -> list[float | None]:
    """Relative Strength Index (Wilder smoothing)."""
    result: list[float | None] = [None] * len(prices)
    if len(prices) < period + 1:
        return result

    deltas = [prices[i] - prices[i - 1] for i in range(1, len(prices))]
    gains = [max(d, 0) for d in deltas]
    losses = [max(-d, 0) for d in deltas]

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    if avg_loss == 0:
        result[period] = 100.0
    else:
        rs = avg_gain / avg_loss
        result[period] = 100 - 100 / (1 + rs)

    for i in range(period, len(deltas)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        if avg_loss == 0:
            result[i + 1] = 100.0
        else:
            rs = avg_gain / avg_loss
            result[i + 1] = 100 - 100 / (1 + rs)

    return result


# ---------------------------------------------------------------------------
# MACD
# ---------------------------------------------------------------------------

def macd(
    prices: list[float],
    fast: int = 12,
    slow: int = 26,
    signal_period: int = 9,
) -> dict[str, list[float | None]]:
    """MACD line, signal line, and histogram."""
    ema_fast = ema(prices, fast)
    ema_slow = ema(prices, slow)

    macd_line: list[float | None] = [None] * len(prices)
    for i in range(len(prices)):
        if ema_fast[i] is not None and ema_slow[i] is not None:
            macd_line[i] = ema_fast[i] - ema_slow[i]

    # Signal = EMA of MACD line (skip Nones for seeding)
    valid = [(i, v) for i, v in enumerate(macd_line) if v is not None]
    signal_line: list[float | None] = [None] * len(prices)
    if len(valid) >= signal_period:
        seed_vals = [v for _, v in valid[:signal_period]]
        seed_idx = valid[signal_period - 1][0]
        signal_line[seed_idx] = sum(seed_vals) / signal_period
        k = 2 / (signal_period + 1)
        for j in range(signal_period, len(valid)):
            idx = valid[j][0]
            prev_idx = valid[j - 1][0]
            prev_sig = signal_line[prev_idx]
            if prev_sig is not None:
                signal_line[idx] = valid[j][1] * k + prev_sig * (1 - k)

    histogram: list[float | None] = [None] * len(prices)
    for i in range(len(prices)):
        if macd_line[i] is not None and signal_line[i] is not None:
            histogram[i] = macd_line[i] - signal_line[i]

    return {"macd": macd_line, "signal": signal_line, "histogram": histogram}


# ---------------------------------------------------------------------------
# Bollinger Bands
# ---------------------------------------------------------------------------

def bollinger_bands(
    prices: list[float], period: int = 20, num_std: float = 2.0
) -> dict[str, list[float | None]]:
    """Bollinger Bands: upper, middle (SMA), lower."""
    middle = sma(prices, period)
    upper: list[float | None] = [None] * len(prices)
    lower: list[float | None] = [None] * len(prices)

    for i in range(period - 1, len(prices)):
        window = prices[i - period + 1 : i + 1]
        mean = middle[i]
        if mean is not None:
            variance = sum((x - mean) ** 2 for x in window) / period
            std = math.sqrt(variance)
            upper[i] = mean + num_std * std
            lower[i] = mean - num_std * std

    return {"upper": upper, "middle": middle, "lower": lower}


# ---------------------------------------------------------------------------
# Stochastic Oscillator
# ---------------------------------------------------------------------------

def stochastic(
    highs: list[float],
    lows: list[float],
    closes: list[float],
    k_period: int = 14,
    d_period: int = 3,
) -> dict[str, list[float | None]]:
    """Stochastic %K and %D."""
    n = len(closes)
    k_values: list[float | None] = [None] * n

    for i in range(k_period - 1, n):
        h = max(highs[i - k_period + 1 : i + 1])
        l = min(lows[i - k_period + 1 : i + 1])
        if h != l:
            k_values[i] = (closes[i] - l) / (h - l) * 100
        else:
            k_values[i] = 50.0

    # %D is SMA of %K
    d_values: list[float | None] = [None] * n
    valid_k = [(i, v) for i, v in enumerate(k_values) if v is not None]
    for j in range(d_period - 1, len(valid_k)):
        idx = valid_k[j][0]
        d_values[idx] = sum(valid_k[j - d_period + 1 + m][1] for m in range(d_period)) / d_period

    return {"k": k_values, "d": d_values}


# ---------------------------------------------------------------------------
# ATR (Average True Range)
# ---------------------------------------------------------------------------

def atr(
    highs: list[float],
    lows: list[float],
    closes: list[float],
    period: int = 14,
) -> list[float | None]:
    """Average True Range using Wilder smoothing."""
    n = len(closes)
    result: list[float | None] = [None] * n
    if n < 2:
        return result

    true_ranges: list[float] = [highs[0] - lows[0]]
    for i in range(1, n):
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )
        true_ranges.append(tr)

    if n < period:
        return result

    result[period - 1] = sum(true_ranges[:period]) / period
    for i in range(period, n):
        prev = result[i - 1]
        if prev is not None:
            result[i] = (prev * (period - 1) + true_ranges[i]) / period

    return result


# ---------------------------------------------------------------------------
# OBV (On-Balance Volume)
# ---------------------------------------------------------------------------

def obv(closes: list[float], volumes: list[float]) -> list[float | None]:
    """On-Balance Volume."""
    if not closes:
        return []
    result: list[float | None] = [float(volumes[0])]
    for i in range(1, len(closes)):
        prev = result[i - 1] or 0.0
        if closes[i] > closes[i - 1]:
            result.append(prev + volumes[i])
        elif closes[i] < closes[i - 1]:
            result.append(prev - volumes[i])
        else:
            result.append(prev)
    return result


# ---------------------------------------------------------------------------
# VWAP (Volume-Weighted Average Price) — intraday or single-session
# ---------------------------------------------------------------------------

def vwap(
    highs: list[float],
    lows: list[float],
    closes: list[float],
    volumes: list[float],
) -> list[float | None]:
    """Cumulative VWAP using typical price."""
    result: list[float | None] = []
    cum_vol = 0.0
    cum_tp_vol = 0.0
    for i in range(len(closes)):
        tp = (highs[i] + lows[i] + closes[i]) / 3
        cum_vol += volumes[i]
        cum_tp_vol += tp * volumes[i]
        if cum_vol > 0:
            result.append(cum_tp_vol / cum_vol)
        else:
            result.append(None)
    return result


# ---------------------------------------------------------------------------
# Assembly helper for persistence
# ---------------------------------------------------------------------------
# Maps a persisted indicator code -> category (fits TechnicalStudyValue.category,
# String(15)). Codes fit TechnicalStudyValue.indicator, String(25).

_INDICATOR_CATEGORIES: dict[str, str] = {
    "SMA_20": "TREND",
    "SMA_50": "TREND",
    "EMA_12": "TREND",
    "EMA_26": "TREND",
    "RSI_14": "MOMENTUM",
    "MACD": "MOMENTUM",
    "MACD_SIGNAL": "MOMENTUM",
    "MACD_HIST": "MOMENTUM",
    "BB_UPPER": "VOLATILITY",
    "BB_MIDDLE": "VOLATILITY",
    "BB_LOWER": "VOLATILITY",
    "STOCH_K": "MOMENTUM",
    "STOCH_D": "MOMENTUM",
    "ATR_14": "VOLATILITY",
    "OBV": "VOLUME",
    "VWAP": "VOLUME",
}


def latest_study_values(
    highs: list[float],
    lows: list[float],
    closes: list[float],
    volumes: list[float],
) -> list[dict[str, object]]:
    """Compute every supported indicator and return the latest non-None value.

    Uses the pure indicator functions above (math unchanged). Returns a list of
    ``{"indicator": code, "value": float, "category": str}`` for the most recent
    bar, skipping indicators that are still None (insufficient history).
    """
    if not closes:
        return []

    last = len(closes) - 1
    macd_out = macd(closes)
    bb = bollinger_bands(closes)
    stoch = stochastic(highs, lows, closes)

    series: dict[str, list[float | None]] = {
        "SMA_20": sma(closes, 20),
        "SMA_50": sma(closes, 50),
        "EMA_12": ema(closes, 12),
        "EMA_26": ema(closes, 26),
        "RSI_14": rsi(closes, 14),
        "MACD": macd_out["macd"],
        "MACD_SIGNAL": macd_out["signal"],
        "MACD_HIST": macd_out["histogram"],
        "BB_UPPER": bb["upper"],
        "BB_MIDDLE": bb["middle"],
        "BB_LOWER": bb["lower"],
        "STOCH_K": stoch["k"],
        "STOCH_D": stoch["d"],
        "ATR_14": atr(highs, lows, closes, 14),
        "OBV": obv(closes, volumes),
        "VWAP": vwap(highs, lows, closes, volumes),
    }

    out: list[dict[str, object]] = []
    for code, values in series.items():
        val = values[last] if last < len(values) else None
        if val is None:
            continue
        out.append(
            {
                "indicator": code,
                "value": float(val),
                "category": _INDICATOR_CATEGORIES.get(code),
            }
        )
    return out
