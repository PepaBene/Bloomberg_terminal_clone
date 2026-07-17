"""Pillar 4 Phase 2: Performance measurement snapshot model."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base

if TYPE_CHECKING:  # avoid circular imports at runtime
    from src.models.portfolio import Portfolio


class PerformanceSnapshot(Base):
    """Periodic performance metrics for a portfolio."""

    __tablename__ = "performance_snapshots"
    __table_args__ = (
        UniqueConstraint("portfolio_id", "period_type", "period_end", name="uq_perf_portfolio_type_end"),
        # P4-M-022: date-order sanity check.
        CheckConstraint("period_start <= period_end", name="ck_perf_period_order"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # P4-M-009: cascade-delete with parent portfolio so ``session.delete
    # (portfolio)`` doesn't fail with a bare FK violation against history
    # tables.
    portfolio_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("portfolios.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    # P4-M-010: ORM-level back-reference so Portfolio.performance_snapshots
    # can eager-load without a separate query.
    portfolio: Mapped["Portfolio"] = relationship(
        "Portfolio", back_populates="performance_snapshots"
    )
    period_type: Mapped[str] = mapped_column(String(10), nullable=False)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    twr_return: Mapped[Decimal | None] = mapped_column(Numeric(12, 8))
    mwr_return: Mapped[Decimal | None] = mapped_column(Numeric(12, 8))
    benchmark_return: Mapped[Decimal | None] = mapped_column(Numeric(12, 8))
    active_return: Mapped[Decimal | None] = mapped_column(Numeric(12, 8))
    sharpe_ratio: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))
    sortino_ratio: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))
    information_ratio: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))
    tracking_error: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))
    max_drawdown: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))
    calmar_ratio: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))
    beta: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))
    alpha: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))
    volatility: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))
    up_capture: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))
    down_capture: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))
    batting_average: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))
    best_day: Mapped[Decimal | None] = mapped_column(Numeric(12, 8))
    worst_day: Mapped[Decimal | None] = mapped_column(Numeric(12, 8))
    positive_days: Mapped[int | None] = mapped_column(Integer)
    negative_days: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
