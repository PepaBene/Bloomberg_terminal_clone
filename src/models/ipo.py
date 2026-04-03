"""Pillar 1 Supplement: IPO Monitor models (Part 3)."""

import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, Index, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin


class IPOEvent(TimestampMixin, Base):
    """IPO lifecycle event from S-1/424B filings."""

    __tablename__ = "ipo_events"

    ipo_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    entity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entities.entity_id"), index=True
    )
    security_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("securities.security_id")
    )

    # Filing info
    s1_filing_date: Mapped[date | None] = mapped_column(Date)
    s1_accession_number: Mapped[str | None] = mapped_column(String(25))

    # Pricing
    pricing_date: Mapped[date | None] = mapped_column(Date, index=True)
    trading_start_date: Mapped[date | None] = mapped_column(Date)
    initial_range_low: Mapped[float | None] = mapped_column(Numeric(12, 4))
    initial_range_high: Mapped[float | None] = mapped_column(Numeric(12, 4))
    offer_price: Mapped[float | None] = mapped_column(Numeric(12, 4))
    shares_offered: Mapped[float | None] = mapped_column(Numeric(20, 0))
    total_proceeds: Mapped[float | None] = mapped_column(Numeric(20, 2))
    overallotment_shares: Mapped[float | None] = mapped_column(Numeric(20, 0))

    # Performance
    first_day_close: Mapped[float | None] = mapped_column(Numeric(12, 4))
    first_day_return_pct: Mapped[float | None] = mapped_column(Numeric(8, 4))
    current_price: Mapped[float | None] = mapped_column(Numeric(12, 4))
    return_vs_offer_pct: Mapped[float | None] = mapped_column(Numeric(8, 4))

    # Underwriters
    lead_underwriters: Mapped[list | None] = mapped_column(JSONB)
    co_managers: Mapped[list | None] = mapped_column(JSONB)

    # Company info
    company_description: Mapped[str | None] = mapped_column(Text)
    gics_sector: Mapped[str | None] = mapped_column(String(100))
    gics_industry: Mapped[str | None] = mapped_column(String(100))
    revenue_ltm: Mapped[float | None] = mapped_column(Numeric(20, 2))
    net_income_ltm: Mapped[float | None] = mapped_column(Numeric(20, 2))

    # Status
    status: Mapped[str | None] = mapped_column(String(15), index=True)
    withdrawal_date: Mapped[date | None] = mapped_column(Date)
    withdrawal_reason: Mapped[str | None] = mapped_column(Text)

    # Source
    source_filings: Mapped[list | None] = mapped_column(JSONB)

    __table_args__ = (
        Index("idx_ipo_entity", "entity_id"),
    )
