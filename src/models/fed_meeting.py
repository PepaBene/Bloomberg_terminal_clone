"""Pillar 1 Supplement: Fed Meeting + Money Market Rate models (Part 2)."""

import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin


class FedMeeting(TimestampMixin, Base):
    """Individual FOMC meeting with rate decision and supplementary data."""

    __tablename__ = "fed_meetings"

    meeting_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    meeting_date: Mapped[date] = mapped_column(Date, nullable=False, unique=True)
    meeting_type: Mapped[str | None] = mapped_column(String(15))
    rate_decision: Mapped[str | None] = mapped_column(String(10))

    # Rate levels
    fed_funds_lower: Mapped[float | None] = mapped_column(Numeric(6, 4))
    fed_funds_upper: Mapped[float | None] = mapped_column(Numeric(6, 4))
    change_bps: Mapped[int | None] = mapped_column(Integer)

    # Statement
    statement_text: Mapped[str | None] = mapped_column(Text)
    statement_url: Mapped[str | None] = mapped_column(String(500))
    minutes_url: Mapped[str | None] = mapped_column(String(500))
    minutes_release_date: Mapped[date | None] = mapped_column(Date)

    # Balance sheet
    total_assets: Mapped[float | None] = mapped_column(Numeric(20, 2))
    treasury_holdings: Mapped[float | None] = mapped_column(Numeric(20, 2))
    mbs_holdings: Mapped[float | None] = mapped_column(Numeric(20, 2))

    # Dot plot
    dot_plot_data: Mapped[dict | None] = mapped_column(JSONB)

    # Link to existing D7 model
    policy_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("central_bank_policies.policy_id")
    )


class MoneyMarketRate(TimestampMixin, Base):
    """Daily money market rate observation."""

    __tablename__ = "money_market_rates"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    rate_date: Mapped[date] = mapped_column(Date, nullable=False)
    rate_type: Mapped[str] = mapped_column(String(30), nullable=False)
    rate_value: Mapped[float | None] = mapped_column(Numeric(8, 6))
    source: Mapped[str | None] = mapped_column(String(20), default="FRED")

    __table_args__ = (
        Index("idx_mmr_date_type", "rate_date", "rate_type", unique=True),
    )
