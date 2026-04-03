"""Domain 7: Macroeconomic Data models (Spec Section 9)."""

import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TimestampMixin


class MacroIndicator(TimestampMixin, Base):
    """Registry of macroeconomic indicators/series (Spec 9.3)."""

    __tablename__ = "macro_indicators"

    indicator_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    indicator_code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    short_name: Mapped[str | None] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(Text)

    # Classification
    category: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    subcategory: Mapped[str | None] = mapped_column(String(50))
    country_code: Mapped[str | None] = mapped_column(
        String(2), ForeignKey("countries.country_code_alpha2"), index=True
    )
    region: Mapped[str | None] = mapped_column(String(50))

    # Scheduling
    frequency: Mapped[str] = mapped_column(String(20), nullable=False)
    release_lag: Mapped[int | None] = mapped_column(Integer)
    typical_release_day: Mapped[str | None] = mapped_column(String(50))

    # Measurement
    unit: Mapped[str | None] = mapped_column(String(50))
    seasonal_adjustment: Mapped[str | None] = mapped_column(String(10))
    source_agency: Mapped[str | None] = mapped_column(String(100))
    source_url: Mapped[str | None] = mapped_column(String(500))
    source_series_id: Mapped[str | None] = mapped_column(String(100))
    base_period: Mapped[str | None] = mapped_column(String(50))
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)

    # Transformation flags
    has_yoy: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    has_mom: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    has_level: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    has_annualized: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB)

    # Relationships
    values = relationship("MacroValue", back_populates="indicator", lazy="selectin")

    __table_args__ = (
        Index("idx_macro_indicators_country_category", "country_code", "category"),
    )


class MacroValue(Base):
    """Time series observations for macro indicators (Spec 9.3)."""

    __tablename__ = "macro_values"

    # Composite primary key
    indicator_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("macro_indicators.indicator_id"),
        primary_key=True,
    )
    observation_date: Mapped[date] = mapped_column(Date, primary_key=True)
    vintage_date: Mapped[date] = mapped_column(Date, primary_key=True)

    # Core value
    value: Mapped[float] = mapped_column(Numeric(20, 6), nullable=False)
    period_type: Mapped[str | None] = mapped_column(String(20))
    revision_number: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Pre-computed transforms
    value_yoy: Mapped[float | None] = mapped_column(Numeric(20, 6))
    value_yoy_percent: Mapped[float | None] = mapped_column(Numeric(20, 6))
    value_mom: Mapped[float | None] = mapped_column(Numeric(20, 6))
    value_mom_percent: Mapped[float | None] = mapped_column(Numeric(20, 6))
    value_qoq_annualized: Mapped[float | None] = mapped_column(Numeric(20, 6))

    # Release context
    is_preliminary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_revised: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    previous_value: Mapped[float | None] = mapped_column(Numeric(20, 6))
    consensus_estimate: Mapped[float | None] = mapped_column(Numeric(20, 6))
    surprise: Mapped[float | None] = mapped_column(Numeric(20, 6))
    surprise_percent: Mapped[float | None] = mapped_column(Numeric(20, 6))

    # Metadata
    release_date: Mapped[date | None] = mapped_column(Date)
    release_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source: Mapped[str | None] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    indicator = relationship("MacroIndicator", back_populates="values")

    __table_args__ = (
        Index("idx_macro_values_indicator_date", "indicator_id", "observation_date"),
        Index("idx_macro_values_indicator_vintage", "indicator_id", "vintage_date"),
    )


class CentralBankPolicy(TimestampMixin, Base):
    """Central bank monetary policy decisions (Spec 9.3)."""

    __tablename__ = "central_bank_policies"

    policy_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    bank_code: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    meeting_date: Mapped[date] = mapped_column(Date, nullable=False)
    decision_date: Mapped[date | None] = mapped_column(Date)
    announcement_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Rate info
    policy_rate: Mapped[float | None] = mapped_column(Numeric(6, 4))
    rate_change: Mapped[float | None] = mapped_column(Numeric(6, 4))
    previous_rate: Mapped[float | None] = mapped_column(Numeric(6, 4))
    rate_direction: Mapped[str | None] = mapped_column(String(10))

    # Voting
    votes_for: Mapped[int | None] = mapped_column(Integer)
    votes_against: Mapped[int | None] = mapped_column(Integer)
    votes_abstain: Mapped[int | None] = mapped_column(Integer)
    dissenting_members: Mapped[dict | None] = mapped_column(JSONB)
    guidance_tone: Mapped[str | None] = mapped_column(String(20))

    # Statements
    statement_summary: Mapped[str | None] = mapped_column(Text)
    statement_url: Mapped[str | None] = mapped_column(String(500))
    minutes_url: Mapped[str | None] = mapped_column(String(500))
    minutes_date: Mapped[date | None] = mapped_column(Date)

    # Next meeting
    next_meeting_date: Mapped[date | None] = mapped_column(Date)
    source: Mapped[str | None] = mapped_column(String(50))

    __table_args__ = (
        Index("uq_central_bank_meeting", "bank_code", "meeting_date", unique=True),
    )
