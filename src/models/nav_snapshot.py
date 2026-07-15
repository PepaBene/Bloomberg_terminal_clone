"""Pillar 4 Phase 1: NAV snapshot and corporate action queue models."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base

if TYPE_CHECKING:  # avoid circular imports at runtime
    from src.models.portfolio import Portfolio
    from src.models.position import Position


class NAVSnapshot(Base):
    """Daily portfolio NAV snapshot with full position state."""

    __tablename__ = "nav_snapshots"
    __table_args__ = (
        UniqueConstraint("portfolio_id", "snapshot_date", name="uq_nav_portfolio_date"),
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
    # P4-M-010: ORM-level back-reference so Portfolio.nav_snapshots can
    # eager-load without a separate query.
    portfolio: Mapped["Portfolio"] = relationship(
        "Portfolio", back_populates="nav_snapshots"
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
    __table_args__ = (
        # P4-M-021: date-order sanity check. NAVSnapshot itself only has a
        # single ``snapshot_date`` column (no period_start/period_end to
        # order), so the meaningful date-order invariant in *this* module
        # is CorporateActionQueue's ex_date/payment_date pair -- a dividend
        # or split can't be paid before its ex-date. Both columns are
        # nullable (not every queued action has both dates yet), so the
        # check only fires once both are populated.
        CheckConstraint(
            "ex_date IS NULL OR payment_date IS NULL OR ex_date <= payment_date",
            name="ck_corp_action_ex_before_payment",
        ),
        # P4-M-026: confirmed status values (PENDING/APPLIED/DISMISSED) --
        # see test_nav_snapshot_models.py's corporate-action transition
        # tests. ``action_type`` is deliberately left unconstrained: this
        # table has no production writer yet (only test fixtures construct
        # it), so the full universe of real-world action types isn't
        # established well enough to lock down safely.
        CheckConstraint(
            "status IN ('PENDING', 'APPLIED', 'DISMISSED')",
            name="ck_corp_action_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # P4-M-009: cascade-delete with parent portfolio, matching the rest of
    # this module's portfolio_id FKs.
    portfolio_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("portfolios.id", ondelete="CASCADE"),
        nullable=False,
    )
    # P4-M-013: ORM-level relationships so callers can navigate from a
    # queued corporate action back to its portfolio/position without a
    # separate query. There is no relationship to NAVSnapshot: no FK column
    # links the two tables (a corporate action queue entry isn't tied to
    # a specific historical NAV snapshot), so only the two real FK-backed
    # siblings -- Portfolio and Position -- get a relationship() here.
    portfolio: Mapped["Portfolio"] = relationship(
        "Portfolio", back_populates="corporate_actions"
    )
    position_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("positions.id", ondelete="SET NULL"),
    )
    position: Mapped["Position | None"] = relationship(
        "Position", back_populates="corporate_actions"
    )
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
