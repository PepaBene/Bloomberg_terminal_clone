"""Central bank and global macro indicator models (Pillar 3 Phase 3B – Part 8)."""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import Boolean, Date, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin


class CentralBankProfile(TimestampMixin, Base):
    """Central bank reference profile with current policy stance."""

    __tablename__ = "central_bank_profiles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    bank_code: Mapped[str] = mapped_column(String(10), nullable=False, unique=True)
    bank_name: Mapped[str | None] = mapped_column(String(100))
    country_code: Mapped[str | None] = mapped_column(String(3))
    current_rate: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    policy_stance: Mapped[str | None] = mapped_column(String(10))
    next_meeting_date: Mapped[date | None] = mapped_column(Date)
    forward_guidance_summary: Mapped[str | None] = mapped_column(Text)


class CentralBankDecision(TimestampMixin, Base):
    """Individual central bank rate decision record."""

    __tablename__ = "central_bank_decisions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    bank_code: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    decision_date: Mapped[date] = mapped_column(Date, nullable=False)

    # Rate details
    rate_before: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    rate_after: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    rate_change_bps: Mapped[int | None] = mapped_column(Integer)
    decision_type: Mapped[str | None] = mapped_column(String(15))
    was_surprise: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    vote_split: Mapped[str | None] = mapped_column(String(50))
    statement_summary: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        {"comment": "Central bank rate decisions with vote and surprise tracking"},
    )


class GlobalMacroIndicator(TimestampMixin, Base):
    """Country-level macroeconomic indicator release data."""

    __tablename__ = "global_macro_indicators"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    country_code: Mapped[str] = mapped_column(String(3), nullable=False, index=True)
    indicator_type: Mapped[str | None] = mapped_column(String(30))
    period_label: Mapped[str | None] = mapped_column(String(20))
    value: Mapped[Decimal | None] = mapped_column(Numeric(15, 4))
    prior_value: Mapped[Decimal | None] = mapped_column(Numeric(15, 4))
    forecast_value: Mapped[Decimal | None] = mapped_column(Numeric(15, 4))
    source: Mapped[str | None] = mapped_column(String(30))
    release_date: Mapped[date | None] = mapped_column(Date)
