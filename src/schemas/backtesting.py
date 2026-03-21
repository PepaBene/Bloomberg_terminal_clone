"""Pydantic schemas for backtesting."""

import uuid
from datetime import date

from pydantic import BaseModel, Field


class BacktestRequest(BaseModel):
    """Request to submit a new backtest."""
    name: str
    description: str | None = None
    strategy_definition: dict  # filter criteria, ranking, etc.
    start_date: date
    end_date: date
    benchmark: str = "SP500"
    weighting_method: str = "EQUAL"
    rebalance_frequency: str = "QUARTERLY"
    max_positions: int = 30
    transaction_cost_bps: float = 10.0


class BacktestRunResponse(BaseModel):
    """Response for a backtest run."""

    model_config = {"from_attributes": True}

    backtest_id: uuid.UUID
    name: str
    description: str | None = None
    status: str
    start_date: date
    end_date: date
    benchmark: str | None = None
    weighting_method: str | None = None
    rebalance_frequency: str | None = None
    max_positions: int | None = None
    transaction_cost_bps: float | None = None


class BacktestPerformanceResponse(BaseModel):
    """Performance metrics for a backtest."""

    model_config = {"from_attributes": True}

    backtest_id: uuid.UUID
    total_return: float | None = None
    annualized_return: float | None = None
    benchmark_return: float | None = None
    excess_return: float | None = None
    sharpe_ratio: float | None = None
    sortino_ratio: float | None = None
    max_drawdown: float | None = None
    max_drawdown_duration_days: int | None = None
    annualized_volatility: float | None = None
    beta: float | None = None
    tracking_error: float | None = None
    information_ratio: float | None = None
    win_rate: float | None = None
    avg_win: float | None = None
    avg_loss: float | None = None
    turnover_annual: float | None = None
    total_trades: int | None = None
    monthly_returns: dict | None = None


class BacktestHoldingEntry(BaseModel):
    """Single holding in a period."""
    security_id: str | None = None
    weight: float
    name: str | None = None


class BacktestHoldingsResponse(BaseModel):
    """Holdings at a specific rebalance date."""
    backtest_id: uuid.UUID
    period_holdings: dict | None = None  # {date_str: [{security_id, weight}]}


class BacktestCompareRequest(BaseModel):
    """Request to compare multiple backtests."""
    backtest_ids: list[uuid.UUID] = Field(..., min_length=2, max_length=10)


class BacktestCompareResponse(BaseModel):
    """Comparison of multiple backtests."""
    backtests: list[BacktestPerformanceResponse] = []
