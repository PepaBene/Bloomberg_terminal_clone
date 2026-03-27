"""Pillar 4 Phase 1: NAV snapshot and corporate action queue models."""

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class NAVSnapshot(Base):
    """Daily portfolio NAV snapshot with full position state."""

    __tablename__ = "nav_snapshots"
    __table_args__ = (
        UniqueConstraint("portfolio_id", "snapshot_date", name="uq_nav_portfolio_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    portfolio_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("portfolios.id"),
        nullable=False, index=True,
    )
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)
    nav: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    market_value: Mapped[Decimal | None] = mapped_column(Numeric(20, 2))
    cash_balance: Mapped[Decimal | None] = mapped_column(Numeric(20, 2))
    unrealized_pnl: Mapped[Decimal | None] = mapped_column(Numeric(20, 2))
    daily_return: Mapped[Decimal | None] = mapped_column(Numeric(12, 8))
    cumulative_return: Mapped[Decimal | None] = mapped_column(Numeric(12, 8))
    benchmark_daily_return: Mapped[Decimal | None] = mapped_column(Numeric(12, 8))
    benchmark_cumulative_return: Mapped[Decimal | None] = mapped_column(Numeric(12, 8))
    positions_snapshot: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class CorporateActionQueue(Base):
    """Pending corporate actions for portfolio positions."""

    __tablename__ = "corporate_action_queue"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    portfolio_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("portfolios.id"), nullable=False,
    )
    position_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    action_type: Mapped[str] = mapped_column(String(20), nullable=False)
    security_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    ticker: Mapped[str | None] = mapped_column(String(20))
    ex_date: Mapped[date | None] = mapped_column(Date)
    payment_date: Mapped[date | None] = mapped_column(Date)
    details: Mapped[dict | None] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(15), default="PENDING")
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
