"""Backtesting models (Pillar 2 Supplement – Part 3)."""

import uuid
from datetime import date

from sqlalchemy import CheckConstraint, Date, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin


class BacktestRun(TimestampMixin, Base):
    """A backtest run definition and status."""

    __tablename__ = "backtest_runs"
    __table_args__ = (
        # P4-M-024: date-order sanity check.
        CheckConstraint("start_date <= end_date", name="ck_backtest_date_order"),
        # P4-M-026: confirmed status values -- PENDING (submit_backtest),
        # FAILED/COMPLETED (scripts/run_backtest_worker.py). RUNNING/
        # CANCELLED aren't used by any caller yet but are kept as valid
        # states for a batch-job status machine (a worker in flight is a
        # legitimate future state; the same reasoning covers user-initiated
        # cancellation).
        CheckConstraint(
            "status IN ('PENDING', 'RUNNING', 'COMPLETED', 'FAILED', 'CANCELLED')",
            name="ck_backtest_status",
        ),
    )

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
    # P4-M-028: ownership so "read a backtest by ID" can be authorized --
    # mirrors Portfolio.user_id (src/models/portfolio.py): a free-form
    # identity string resolved from the JWT ``sub`` claim, or the shared
    # anonymous fallback identity when no Bearer token is present (see
    # ANONYMOUS_USER/_resolve_user in src/api/routers/portfolios.py and
    # the equivalent helper added to src/api/routers/backtesting.py). Not
    # a hard FK to ``users`` -- same reasoning as Portfolio.user_id: the
    # anonymous/JWT-sub identity here isn't guaranteed to correspond to a
    # real ``users`` row, and this module's own tests/current callers
    # exercise the API with no Bearer token at all (REQUIRE_AUTH=False by
    # default), so a hard FK would require a larger, coordinated auth
    # rewrite out of scope for this fix (see migration 088's M-004/M-005
    # for what that heavier lift looks like elsewhere in the codebase).
    user_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True, server_default="default_user")
    # P4-M-027: audit trail field, matching Transaction.created_by.
    created_by: Mapped[str | None] = mapped_column(String(100))


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
