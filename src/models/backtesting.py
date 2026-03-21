"""Backtesting models (Pillar 2 Supplement – Part 3)."""

import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin


class BacktestRun(TimestampMixin, Base):
    """A backtest run definition and status."""

    __tablename__ = "backtest_runs"

    backtest_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDING")
    strategy_definition: Mapped[dict | None] = mapped_column(JSONB)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    benchmark: Mapped[str | None] = mapped_column(String(30))
    weighting_method: Mapped[str | None] = mapped_column(String(20))
    rebalance_frequency: Mapped[str | None] = mapped_column(String(20))
    max_positions: Mapped[int | None] = mapped_column(Integer)
    transaction_cost_bps: Mapped[float | None] = mapped_column(Numeric(6, 2))


class BacktestResult(TimestampMixin, Base):
    """Performance results for a backtest run."""

    __tablename__ = "backtest_results"

    result_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    backtest_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("backtest_runs.backtest_id"), nullable=False
    )
    total_return: Mapped[float | None] = mapped_column(Numeric(10, 6))
    annualized_return: Mapped[float | None] = mapped_column(Numeric(10, 6))
    benchmark_return: Mapped[float | None] = mapped_column(Numeric(10, 6))
    excess_return: Mapped[float | None] = mapped_column(Numeric(10, 6))
    sharpe_ratio: Mapped[float | None] = mapped_column(Numeric(8, 4))
    sortino_ratio: Mapped[float | None] = mapped_column(Numeric(8, 4))
    max_drawdown: Mapped[float | None] = mapped_column(Numeric(8, 6))
    max_drawdown_duration_days: Mapped[int | None] = mapped_column(Integer)
    annualized_volatility: Mapped[float | None] = mapped_column(Numeric(8, 6))
    beta: Mapped[float | None] = mapped_column(Numeric(6, 4))
    tracking_error: Mapped[float | None] = mapped_column(Numeric(8, 6))
    information_ratio: Mapped[float | None] = mapped_column(Numeric(8, 4))
    win_rate: Mapped[float | None] = mapped_column(Numeric(6, 4))
    avg_win: Mapped[float | None] = mapped_column(Numeric(8, 6))
    avg_loss: Mapped[float | None] = mapped_column(Numeric(8, 6))
    turnover_annual: Mapped[float | None] = mapped_column(Numeric(6, 4))
    total_trades: Mapped[int | None] = mapped_column(Integer)
    monthly_returns: Mapped[dict | None] = mapped_column(JSONB)
    period_holdings: Mapped[dict | None] = mapped_column(JSONB)
    sector_attribution: Mapped[dict | None] = mapped_column(JSONB)

    __table_args__ = (
        Index("idx_br_backtest_id", "backtest_id"),
    )
