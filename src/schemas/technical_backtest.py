"""Pydantic schemas for technical backtester."""

import uuid

from pydantic import BaseModel


class TechnicalSignalResponse(BaseModel):
    """A single technical signal."""
    index: int
    signal_type: str
    indicator: str
    value: float
    threshold: float | None = None


class TechnicalStrategyRequest(BaseModel):
    """Request to run a technical strategy backtest."""
    name: str = "Technical Strategy"
    indicator: str = "MA_CROSSOVER"
    fast_period: int = 10
    slow_period: int = 50
    ma_type: str = "SMA"
    rsi_period: int = 14
    rsi_overbought: float = 70.0
    rsi_oversold: float = 30.0
    bb_period: int = 20
    bb_std: float = 2.0
    initial_capital: float = 100000.0
    position_size: float = 1.0
    transaction_cost_bps: float = 10.0
    prices: list[float] = []


class TechnicalBacktestResponse(BaseModel):
    """Response from a technical backtest run."""
    backtest_id: uuid.UUID | None = None
    name: str
    indicator: str
    total_trades: int
    final_value: float
    total_return: float
    total_return_pct: float = 0.0
    annualized_return: float = 0.0
    annualized_volatility: float = 0.0
    sharpe_ratio: float | None = None
    sortino_ratio: float | None = None
    max_drawdown: float = 0.0
    win_rate: float = 0.0
    signals_generated: int = 0
