"""Equity Strategy Backtester Engine.

Provides performance metric computation, portfolio weighting, and
backtest simulation. All functions are pure computation — no database access.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Performance Metrics
# ---------------------------------------------------------------------------

@dataclass
class PerformanceMetrics:
    """Output of performance metric computation."""
    total_return: float
    annualized_return: float
    annualized_volatility: float
    sharpe_ratio: float | None
    sortino_ratio: float | None
    max_drawdown: float
    max_drawdown_duration_days: int
    beta: float | None
    tracking_error: float | None
    information_ratio: float | None
    win_rate: float
    avg_win: float
    avg_loss: float


def compute_performance_metrics(
    returns: list[float],
    benchmark_returns: list[float] | None = None,
    risk_free_rate: float = 0.0,
    periods_per_year: int = 252,
) -> PerformanceMetrics:
    """Compute portfolio performance metrics from a return series.

    Parameters
    ----------
    returns : list of daily returns (decimal, e.g. 0.01 = 1%)
    benchmark_returns : list of daily benchmark returns (same length)
    risk_free_rate : annualized risk-free rate (decimal)
    periods_per_year : number of trading periods per year (252 for daily)

    Returns
    -------
    PerformanceMetrics
    """
    n = len(returns)
    if n == 0:
        return PerformanceMetrics(
            total_return=0.0, annualized_return=0.0, annualized_volatility=0.0,
            sharpe_ratio=None, sortino_ratio=None,
            max_drawdown=0.0, max_drawdown_duration_days=0,
            beta=None, tracking_error=None, information_ratio=None,
            win_rate=0.0, avg_win=0.0, avg_loss=0.0,
        )

    # Total return (compound)
    cum = 1.0
    for r in returns:
        cum *= (1 + r)
    total_return = cum - 1.0

    # Annualized return
    years = n / periods_per_year
    if years > 0 and cum > 0:
        annualized_return = cum ** (1 / years) - 1
    else:
        annualized_return = 0.0

    # Volatility
    mean_r = sum(returns) / n
    variance = sum((r - mean_r) ** 2 for r in returns) / max(n - 1, 1)
    daily_vol = math.sqrt(variance)
    annualized_vol = daily_vol * math.sqrt(periods_per_year)

    # Sharpe ratio
    daily_rf = risk_free_rate / periods_per_year
    excess_mean = mean_r - daily_rf
    sharpe = (excess_mean / daily_vol * math.sqrt(periods_per_year)) if daily_vol > 1e-10 else None

    # Sortino ratio (downside deviation)
    downside_returns = [min(r - daily_rf, 0) for r in returns]
    downside_var = sum(d ** 2 for d in downside_returns) / max(n - 1, 1)
    downside_dev = math.sqrt(downside_var)
    sortino = (excess_mean / downside_dev * math.sqrt(periods_per_year)) if downside_dev > 1e-10 else None

    # Max drawdown
    peak = 1.0
    cum_val = 1.0
    max_dd = 0.0
    max_dd_days = 0
    current_dd_days = 0
    for r in returns:
        cum_val *= (1 + r)
        if cum_val > peak:
            peak = cum_val
            current_dd_days = 0
        dd = (peak - cum_val) / peak
        if dd > max_dd:
            max_dd = dd
        if cum_val < peak:
            current_dd_days += 1
            if current_dd_days > max_dd_days:
                max_dd_days = current_dd_days

    # Win rate, avg win/loss
    wins = [r for r in returns if r > 0]
    losses = [r for r in returns if r < 0]
    win_rate = len(wins) / n if n > 0 else 0.0
    avg_win = sum(wins) / len(wins) if wins else 0.0
    avg_loss = sum(losses) / len(losses) if losses else 0.0

    # Beta, tracking error, information ratio (vs benchmark)
    beta = None
    tracking_error = None
    information_ratio = None
    if benchmark_returns and len(benchmark_returns) == n:
        mean_b = sum(benchmark_returns) / n
        cov_rb = sum((returns[i] - mean_r) * (benchmark_returns[i] - mean_b) for i in range(n)) / max(n - 1, 1)
        var_b = sum((benchmark_returns[i] - mean_b) ** 2 for i in range(n)) / max(n - 1, 1)
        beta = cov_rb / var_b if var_b > 1e-15 else None

        # Tracking error
        excess = [returns[i] - benchmark_returns[i] for i in range(n)]
        mean_excess = sum(excess) / n
        te_var = sum((e - mean_excess) ** 2 for e in excess) / max(n - 1, 1)
        tracking_error = math.sqrt(te_var) * math.sqrt(periods_per_year)

        # Information ratio
        information_ratio = (mean_excess * periods_per_year / tracking_error) if tracking_error > 1e-10 else None

    return PerformanceMetrics(
        total_return=round(total_return, 6),
        annualized_return=round(annualized_return, 6),
        annualized_volatility=round(annualized_vol, 6),
        sharpe_ratio=round(sharpe, 4) if sharpe is not None else None,
        sortino_ratio=round(sortino, 4) if sortino is not None else None,
        max_drawdown=round(max_dd, 6),
        max_drawdown_duration_days=max_dd_days,
        beta=round(beta, 4) if beta is not None else None,
        tracking_error=round(tracking_error, 6) if tracking_error is not None else None,
        information_ratio=round(information_ratio, 4) if information_ratio is not None else None,
        win_rate=round(win_rate, 4),
        avg_win=round(avg_win, 6),
        avg_loss=round(avg_loss, 6),
    )


# ---------------------------------------------------------------------------
# Portfolio Weighting
# ---------------------------------------------------------------------------

def equal_weight_portfolio(
    security_ids: list[str],
    max_positions: int | None = None,
) -> dict[str, float]:
    """Create equal-weight portfolio from a list of security IDs."""
    if not security_ids:
        return {}
    selected = security_ids[:max_positions] if max_positions else security_ids
    n = len(selected)
    weight = round(1.0 / n, 6)
    return {sid: weight for sid in selected}


def market_cap_weight_portfolio(
    security_ids: list[str],
    market_caps: list[float],
    max_positions: int | None = None,
) -> dict[str, float]:
    """Create market-cap weighted portfolio."""
    if not security_ids or len(security_ids) != len(market_caps):
        return {}

    # Sort by market cap descending, take top N
    pairs = sorted(zip(security_ids, market_caps), key=lambda x: x[1], reverse=True)
    if max_positions:
        pairs = pairs[:max_positions]

    total_cap = sum(mc for _, mc in pairs)
    if total_cap <= 0:
        return {}

    return {sid: round(mc / total_cap, 6) for sid, mc in pairs}


def score_based_weight_portfolio(
    security_ids: list[str],
    scores: list[float],
    max_positions: int | None = None,
) -> dict[str, float]:
    """Create score-based weighted portfolio (higher score = higher weight)."""
    if not security_ids or len(security_ids) != len(scores):
        return {}

    pairs = sorted(zip(security_ids, scores), key=lambda x: x[1], reverse=True)
    if max_positions:
        pairs = pairs[:max_positions]

    total_score = sum(max(s, 0) for _, s in pairs)
    if total_score <= 0:
        # Fall back to equal weight
        n = len(pairs)
        return {sid: round(1.0 / n, 6) for sid, _ in pairs}

    return {sid: round(max(s, 0) / total_score, 6) for sid, s in pairs}


# ---------------------------------------------------------------------------
# Backtest Configuration
# ---------------------------------------------------------------------------

@dataclass
class BacktestConfig:
    """Parsed backtest configuration."""
    name: str
    start_date: str
    end_date: str
    benchmark: str = "SP500"
    weighting_method: str = "EQUAL"
    rebalance_frequency: str = "QUARTERLY"
    max_positions: int = 30
    transaction_cost_bps: float = 10.0
    filters: dict = field(default_factory=dict)
    ranking: dict = field(default_factory=dict)


def parse_strategy(strategy_json: dict) -> BacktestConfig:
    """Parse a strategy definition JSON into a BacktestConfig."""
    return BacktestConfig(
        name=strategy_json.get("name", "Unnamed Strategy"),
        start_date=strategy_json.get("start_date", ""),
        end_date=strategy_json.get("end_date", ""),
        benchmark=strategy_json.get("benchmark", "SP500"),
        weighting_method=strategy_json.get("weighting_method", "EQUAL"),
        rebalance_frequency=strategy_json.get("rebalance_frequency", "QUARTERLY"),
        max_positions=strategy_json.get("max_positions", 30),
        transaction_cost_bps=strategy_json.get("transaction_cost_bps", 10.0),
        filters=strategy_json.get("filters", {}),
        ranking=strategy_json.get("ranking", {}),
    )
