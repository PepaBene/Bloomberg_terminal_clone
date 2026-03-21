"""Technical Strategy Backtester Engine.

Generates trading signals from technical indicators and runs backtests.
All functions are pure computation — no database access.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.engines.backtester import PerformanceMetrics, compute_performance_metrics
from src.engines.technical_studies import sma, ema, rsi, macd, bollinger_bands


@dataclass
class TechnicalSignal:
    """A single generated technical signal."""
    index: int
    signal_type: str
    indicator: str
    value: float
    threshold: float | None = None


def generate_ma_crossover_signals(
    prices: list[float],
    fast_period: int = 10,
    slow_period: int = 50,
    ma_type: str = "SMA",
) -> list[TechnicalSignal]:
    """Generate moving average crossover signals.

    Parameters
    ----------
    prices : List of close prices.
    fast_period : Period for the fast moving average.
    slow_period : Period for the slow moving average.
    ma_type : "SMA" or "EMA".

    Returns
    -------
    List of TechnicalSignal for each crossover event.
    """
    ma_func = ema if ma_type.upper() == "EMA" else sma
    fast_ma = ma_func(prices, fast_period)
    slow_ma = ma_func(prices, slow_period)

    signals = []
    for i in range(1, len(prices)):
        if fast_ma[i] is None or slow_ma[i] is None:
            continue
        if fast_ma[i - 1] is None or slow_ma[i - 1] is None:
            continue

        # Crossover above
        if fast_ma[i - 1] <= slow_ma[i - 1] and fast_ma[i] > slow_ma[i]:
            signals.append(TechnicalSignal(
                index=i,
                signal_type="CROSSOVER_ABOVE",
                indicator=f"{ma_type}_{fast_period}/{slow_period}",
                value=fast_ma[i],
                threshold=slow_ma[i],
            ))
        # Crossover below
        elif fast_ma[i - 1] >= slow_ma[i - 1] and fast_ma[i] < slow_ma[i]:
            signals.append(TechnicalSignal(
                index=i,
                signal_type="CROSSOVER_BELOW",
                indicator=f"{ma_type}_{fast_period}/{slow_period}",
                value=fast_ma[i],
                threshold=slow_ma[i],
            ))

    return signals


def generate_rsi_signals(
    prices: list[float],
    period: int = 14,
    overbought: float = 70.0,
    oversold: float = 30.0,
) -> list[TechnicalSignal]:
    """Generate RSI threshold signals.

    Parameters
    ----------
    prices : List of close prices.
    period : RSI lookback period.
    overbought : Upper threshold (sell signal).
    oversold : Lower threshold (buy signal).

    Returns
    -------
    List of TechnicalSignal for threshold crossings.
    """
    rsi_values = rsi(prices, period)
    signals = []

    for i in range(1, len(rsi_values)):
        if rsi_values[i] is None or rsi_values[i - 1] is None:
            continue

        # Cross above overbought
        if rsi_values[i - 1] <= overbought and rsi_values[i] > overbought:
            signals.append(TechnicalSignal(
                index=i,
                signal_type="THRESHOLD_ABOVE",
                indicator=f"RSI_{period}",
                value=rsi_values[i],
                threshold=overbought,
            ))
        # Cross below oversold
        elif rsi_values[i - 1] >= oversold and rsi_values[i] < oversold:
            signals.append(TechnicalSignal(
                index=i,
                signal_type="THRESHOLD_BELOW",
                indicator=f"RSI_{period}",
                value=rsi_values[i],
                threshold=oversold,
            ))

    return signals


def generate_bollinger_signals(
    prices: list[float],
    period: int = 20,
    num_std: float = 2.0,
) -> list[TechnicalSignal]:
    """Generate Bollinger Band breakout/breakdown signals.

    Parameters
    ----------
    prices : List of close prices.
    period : Bollinger band lookback period.
    num_std : Number of standard deviations for the bands.

    Returns
    -------
    List of TechnicalSignal for band breakout/breakdown events.
    """
    bands = bollinger_bands(prices, period, num_std)
    signals = []

    for i in range(1, len(prices)):
        upper = bands["upper"][i]
        lower = bands["lower"][i]
        prev_upper = bands["upper"][i - 1]
        prev_lower = bands["lower"][i - 1]

        if upper is None or lower is None or prev_upper is None or prev_lower is None:
            continue

        # Breakout above upper band
        if prices[i - 1] <= prev_upper and prices[i] > upper:
            signals.append(TechnicalSignal(
                index=i,
                signal_type="BAND_BREAKOUT",
                indicator=f"BBANDS_{period}",
                value=prices[i],
                threshold=upper,
            ))
        # Breakdown below lower band
        elif prices[i - 1] >= prev_lower and prices[i] < lower:
            signals.append(TechnicalSignal(
                index=i,
                signal_type="BAND_BREAKDOWN",
                indicator=f"BBANDS_{period}",
                value=prices[i],
                threshold=lower,
            ))

    return signals


def run_technical_backtest(
    prices: list[float],
    signals: list[TechnicalSignal],
    initial_capital: float = 100000.0,
    position_size: float = 1.0,
    transaction_cost_bps: float = 10.0,
) -> dict:
    """Run a simple long-only backtest from technical signals.

    Buy on CROSSOVER_ABOVE, THRESHOLD_BELOW (oversold), BAND_BREAKDOWN.
    Sell on CROSSOVER_BELOW, THRESHOLD_ABOVE (overbought), BAND_BREAKOUT.

    Parameters
    ----------
    prices : List of daily close prices.
    signals : List of TechnicalSignal from signal generators.
    initial_capital : Starting capital.
    position_size : Fraction of capital to invest per trade (0 to 1).
    transaction_cost_bps : Cost per trade in basis points.

    Returns
    -------
    dict with keys: returns, total_trades, performance (PerformanceMetrics)
    """
    buy_signals = {"CROSSOVER_ABOVE", "THRESHOLD_BELOW", "BAND_BREAKDOWN"}
    sell_signals = {"CROSSOVER_BELOW", "THRESHOLD_ABOVE", "BAND_BREAKOUT"}

    # Build signal map: index -> action
    signal_map: dict[int, str] = {}
    for sig in signals:
        if sig.signal_type in buy_signals:
            signal_map[sig.index] = "BUY"
        elif sig.signal_type in sell_signals:
            signal_map[sig.index] = "SELL"

    # Simulate
    capital = initial_capital
    position = 0.0  # number of shares
    entry_price = 0.0
    total_trades = 0
    daily_returns: list[float] = []
    cost_factor = transaction_cost_bps / 10000.0

    for i in range(len(prices)):
        if i == 0:
            daily_returns.append(0.0)
            continue

        # Daily return from position
        if position > 0 and prices[i - 1] > 0:
            daily_ret = (prices[i] - prices[i - 1]) / prices[i - 1]
            # Scale by position value as fraction of total portfolio
            position_value = position * prices[i - 1]
            total_value = capital + position_value
            if total_value > 0:
                daily_returns.append(daily_ret * (position_value / total_value))
            else:
                daily_returns.append(0.0)
        else:
            daily_returns.append(0.0)

        action = signal_map.get(i)
        if action == "BUY" and position == 0 and capital > 0:
            invest = capital * position_size
            cost = invest * cost_factor
            shares = (invest - cost) / prices[i] if prices[i] > 0 else 0
            position = shares
            entry_price = prices[i]
            capital -= invest
            total_trades += 1
        elif action == "SELL" and position > 0:
            proceeds = position * prices[i]
            cost = proceeds * cost_factor
            capital += proceeds - cost
            position = 0.0
            total_trades += 1

    # Final portfolio value
    final_value = capital + position * prices[-1] if prices else capital

    # Compute performance metrics
    benchmark_returns = []
    for i in range(len(prices)):
        if i == 0:
            benchmark_returns.append(0.0)
        elif prices[i - 1] > 0:
            benchmark_returns.append((prices[i] - prices[i - 1]) / prices[i - 1])
        else:
            benchmark_returns.append(0.0)

    performance = compute_performance_metrics(
        daily_returns, benchmark_returns, risk_free_rate=0.0
    )

    return {
        "returns": daily_returns,
        "total_trades": total_trades,
        "final_value": round(final_value, 2),
        "total_return": round((final_value / initial_capital - 1) * 100, 4) if initial_capital > 0 else 0.0,
        "performance": performance,
    }
