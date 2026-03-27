"""Pillar 3 Phase 1: Insider Intelligence models (Form 4 transactions, signals)."""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import Boolean, Date, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin


class InsiderTransactionP3(TimestampMixin, Base):
    """Structured Form 4 insider transaction data (Pillar 3)."""

    __tablename__ = "insider_transactions_p3"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("entities.entity_id"),
        nullable=False,
        index=True,
    )
    reporting_person: Mapped[str] = mapped_column(String(200), nullable=False)
    reporting_person_cik: Mapped[str | None] = mapped_column(String(10))
    relationship: Mapped[str] = mapped_column(String(30), nullable=False)
    transaction_type: Mapped[str] = mapped_column(String(20), nullable=False)
    transaction_code: Mapped[str | None] = mapped_column(String(2))
    transaction_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    shares: Mapped[Decimal | None] = mapped_column(Numeric(15, 2))
    price_per_share: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    total_value: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    shares_owned_after: Mapped[Decimal | None] = mapped_column(Numeric(15, 2))
    is_open_market: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_10b5_1: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_direct_ownership: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    filing_date: Mapped[date | None] = mapped_column(Date)
    filing_url: Mapped[str | None] = mapped_column(String(500))

    __table_args__ = (
        Index("idx_insider_tx_entity_date", "entity_id", "transaction_date"),
        Index("idx_insider_tx_person_date", "reporting_person_cik", "transaction_date"),
    )


class InsiderSignal(TimestampMixin, Base):
    """Computed insider trading signals for an entity."""

    __tablename__ = "insider_signals"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("entities.entity_id"),
        nullable=False,
        index=True,
    )
    signal_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    signal_type: Mapped[str] = mapped_column(String(30), nullable=False)
    signal_strength: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    net_shares_30d: Mapped[Decimal | None] = mapped_column(Numeric(15, 2))
    net_value_30d: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    net_shares_90d: Mapped[Decimal | None] = mapped_column(Numeric(15, 2))
    net_value_90d: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    net_shares_365d: Mapped[Decimal | None] = mapped_column(Numeric(15, 2))
    net_value_365d: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    open_market_buy_count_90d: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    insider_count_buying_30d: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    insider_count_selling_30d: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    ownership_pct_change: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    detail: Mapped[dict | None] = mapped_column(JSONB)

    __table_args__ = (
        Index(
            "uq_insider_signal",
            "entity_id", "signal_date", "signal_type",
            unique=True,
        ),
    )
