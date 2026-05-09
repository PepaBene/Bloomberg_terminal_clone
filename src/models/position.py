"""Pillar 4 Phase 1: Portfolio position tracking model."""

import uuid
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Date, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from src.models.portfolio import Portfolio


class Position(TimestampMixin, Base):
    """Individual security position within a portfolio."""

    __tablename__ = "positions"
    __table_args__ = (
        UniqueConstraint(
            "portfolio_id", "ticker", "status",
            name="uq_position_portfolio_ticker_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # P4-M-009: cascade-delete positions with their parent portfolio so
    # we don't strand orphans (or fail with a FK violation on portfolio
    # deletion).
    portfolio_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("portfolios.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    # P4-M-011: ORM-level back_populates so eager loading works.
    portfolio: Mapped["Portfolio"] = relationship(
        "Portfolio", back_populates="positions"
    )
    security_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    ticker: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(10), default="OPEN")
    shares: Mapped[Decimal | None] = mapped_column(Numeric(20, 6))
    cost_basis_total: Mapped[Decimal | None] = mapped_column(Numeric(20, 2))
    cost_basis_per_share: Mapped[Decimal | None] = mapped_column(Numeric(15, 6))
    first_acquisition_date: Mapped[date | None] = mapped_column(Date)
    market_value: Mapped[Decimal | None] = mapped_column(Numeric(20, 2))
    unrealized_pnl: Mapped[Decimal | None] = mapped_column(Numeric(20, 2))
    unrealized_pnl_pct: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    weight: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    closing_price: Mapped[Decimal | None] = mapped_column(Numeric(15, 4))
    day_change_pct: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    notes: Mapped[str | None] = mapped_column(Text)
