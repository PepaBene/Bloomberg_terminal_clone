"""Pillar 4 Phase 1: Portfolio management model."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, Date, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TimestampMixin

if TYPE_CHECKING:  # avoid circular imports at runtime
    from src.models.position import Position
    from src.models.transaction import Transaction
    from src.models.nav_snapshot import NAVSnapshot, CorporateActionQueue
    from src.models.performance import PerformanceSnapshot
    from src.models.attribution import AttributionResult


class Portfolio(TimestampMixin, Base):
    """User portfolio with benchmark, cash, and configuration."""

    __tablename__ = "portfolios"
    __table_args__ = (
        UniqueConstraint("user_id", "portfolio_name", name="uq_portfolio_user_name"),
        # P4-M-026: confirmed status values (ACTIVE default, ARCHIVED on
        # soft-delete/close -- see test_portfolio_models.py).
        # ``portfolio_type`` is deliberately left unconstrained: real
        # callers use REAL/PAPER *and* EQUITY (src/api/routers/
        # portfolios.py's CSV-upload commit path), an inconsistency that's
        # a separate, pre-existing bug outside this fix's scope -- locking
        # the CHECK to only 2 of the 3 in-use values would break the third.
        CheckConstraint("status IN ('ACTIVE', 'ARCHIVED')", name="ck_portfolio_status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    portfolio_name: Mapped[str] = mapped_column(String(200), nullable=False)
    portfolio_type: Mapped[str] = mapped_column(
        String(10), nullable=False, default="REAL"
    )
    benchmark_id: Mapped[str | None] = mapped_column(String(20))
    inception_date: Mapped[date] = mapped_column(Date, nullable=False)
    base_currency: Mapped[str] = mapped_column(String(3), default="USD")
    initial_cash: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    current_cash: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(10), default="ACTIVE")
    tags: Mapped[dict | None] = mapped_column(JSONB)
    notes: Mapped[str | None] = mapped_column(Text)
    # P4-M-029: soft-delete support — distinct from status="ARCHIVED" which
    # is a user-driven state. Hard-delete still cascades; this allows
    # restore-from-trash semantics for accidental deletes.
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # P4-M-010: ORM-level navigation so callers can selectinload positions
    # without a separate query. Children cascade-delete with the parent so
    # ``await session.delete(portfolio)`` cleans up positions/transactions.
    positions: Mapped[list["Position"]] = relationship(
        "Position",
        back_populates="portfolio",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    transactions: Mapped[list["Transaction"]] = relationship(
        "Transaction",
        back_populates="portfolio",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    # P4-M-010: NAV/performance/attribution history relationships, added
    # alongside the P4-M-009 ``ondelete="CASCADE"`` fix on their portfolio_id
    # FKs so ``session.delete(portfolio)`` cleans these up the same way it
    # already does for positions/transactions.
    nav_snapshots: Mapped[list["NAVSnapshot"]] = relationship(
        "NAVSnapshot",
        back_populates="portfolio",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    performance_snapshots: Mapped[list["PerformanceSnapshot"]] = relationship(
        "PerformanceSnapshot",
        back_populates="portfolio",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    attribution_results: Mapped[list["AttributionResult"]] = relationship(
        "AttributionResult",
        back_populates="portfolio",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    # P4-M-013: reverse side of CorporateActionQueue.portfolio.
    corporate_actions: Mapped[list["CorporateActionQueue"]] = relationship(
        "CorporateActionQueue",
        back_populates="portfolio",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
