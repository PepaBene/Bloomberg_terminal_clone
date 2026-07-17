"""Pydantic schemas for backtesting."""

import uuid
from datetime import date

from pydantic import BaseModel, Field, field_serializer

from src.schemas.common import round_or_none


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
    """Response for a backtest run.

    P4-M-006: ``transaction_cost_bps`` is deliberately kept as ``float`` on
    the wire (Pydantic v2 serializes ``Decimal`` as a quoted string, which
    would break existing JSON number consumers); rounded to 2dp, matching
    the source ``Numeric(6, 2)`` column.
    """

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

    @field_serializer("transaction_cost_bps")
    def _round_bps(self, v: float | None) -> float | None:
        return round_or_none(v, 2)


class BacktestPerformanceResponse(BaseModel):
    """Performance metrics for a backtest.

    P4-M-006: return/ratio fields are deliberately kept as ``float`` on the
    wire (Pydantic v2 serializes ``Decimal`` as a quoted string by default,
    which would break existing JSON number consumers). Fields are rounded
    via ``field_serializer`` to the decimal scale of their source
    ``Numeric`` DB column (``BacktestResult``) to avoid false
    floating-point precision.
    """

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

    # total_return / annualized_return / benchmark_return / excess_return:
    # Numeric(10, 6); max_drawdown / annualized_volatility / avg_win /
    # avg_loss / tracking_error: Numeric(8, 6)
    @field_serializer(
        "total_return", "annualized_return", "benchmark_return", "excess_return",
        "max_drawdown", "annualized_volatility", "avg_win", "avg_loss", "tracking_error",
    )
    def _round_6dp(self, v: float | None) -> float | None:
        return round_or_none(v, 6)

    # sharpe_ratio / sortino_ratio / information_ratio: Numeric(8, 4);
    # beta: Numeric(6, 4); win_rate / turnover_annual: Numeric(6, 4)
    @field_serializer(
        "sharpe_ratio", "sortino_ratio", "information_ratio",
        "beta", "win_rate", "turnover_annual",
    )
    def _round_4dp(self, v: float | None) -> float | None:
        return round_or_none(v, 4)


class BacktestHoldingEntry(BaseModel):
    """Single holding in a period."""
    security_id: str | None = None
    weight: float
    name: str | None = None

    @field_serializer("weight")
    def _round_ratio(self, v: float) -> float:
        return round(v, 6)


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
