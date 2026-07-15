"""Pillar 4 Phase 1: Transaction log and audit trail model."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base

if TYPE_CHECKING:
    from src.models.portfolio import Portfolio


class Transaction(Base):
    """Immutable transaction record for portfolio audit trail."""

    __tablename__ = "transactions"
    __table_args__ = (
        Index("idx_txn_portfolio_date", "portfolio_id", "transaction_date"),
        # P4-M-026: confirmed real-world transaction types (BUY/SELL/
        # DIVIDEND per tests). SPLIT/TRANSFER_IN/TRANSFER_OUT/DEPOSIT/
        # WITHDRAWAL/FEE/INTEREST are included as the standard remaining
        # portfolio cash-ledger event types create_transaction()'s generic
        # "any other type" fallback (src/api/routers/portfolios.py) is
        # designed to accept, without opening this up to arbitrary strings.
        CheckConstraint(
            "transaction_type IN ("
            "'BUY', 'SELL', 'DIVIDEND', 'SPLIT', 'TRANSFER_IN', 'TRANSFER_OUT', "
            "'DEPOSIT', 'WITHDRAWAL', 'FEE', 'INTEREST'"
            ")",
            name="ck_transaction_type",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # P4-M-009: cascade-delete with parent portfolio.
    portfolio_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("portfolios.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    portfolio: Mapped["Portfolio"] = relationship(
        "Portfolio", back_populates="transactions"
    )
    security_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    ticker: Mapped[str | None] = mapped_column(String(20))
    transaction_type: Mapped[str] = mapped_column(String(20), nullable=False)
    transaction_date: Mapped[date] = mapped_column(Date, nullable=False)
    settlement_date: Mapped[date | None] = mapped_column(Date)
    shares: Mapped[Decimal | None] = mapped_column(Numeric(20, 6))
    price_per_share: Mapped[Decimal | None] = mapped_column(Numeric(15, 6))
    gross_amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 2))
    commission: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), default=0)
    net_amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 2))
    cash_impact: Mapped[Decimal | None] = mapped_column(Numeric(20, 2))
    source: Mapped[str] = mapped_column(String(20), default="MANUAL")
    source_reference: Mapped[str | None] = mapped_column(String(200))
    notes: Mapped[str | None] = mapped_column(Text)
    # P4-M-027: audit trail fields so we can answer "who recorded this
    # transaction" even after the user leaves the firm. Free-form for now
    # (no users table to FK against).
    created_by: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
