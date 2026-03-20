"""Domain 2: Security Master models (Spec Section 4)."""

import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TimestampMixin


class Security(TimestampMixin, Base):
    """Canonical registry of all tradeable instruments (Spec 4.3)."""

    __tablename__ = "securities"

    # Primary identification
    security_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    security_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    security_subtype: Mapped[str | None] = mapped_column(String(50))

    # Issuer link
    issuer_entity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entities.entity_id"), index=True
    )

    # Names
    name: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    short_name: Mapped[str | None] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)

    # Status
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    status_date: Mapped[date | None] = mapped_column(Date)
    status_reason: Mapped[str | None] = mapped_column(String(500))

    # Issuance details
    issue_date: Mapped[date | None] = mapped_column(Date)
    maturity_date: Mapped[date | None] = mapped_column(Date)
    issue_amount: Mapped[float | None] = mapped_column(Numeric(20, 2))
    issue_currency: Mapped[str | None] = mapped_column(
        String(3), ForeignKey("currencies.currency_code")
    )

    # Classification
    asset_class: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    cfi_code: Mapped[str | None] = mapped_column(String(6))

    # Primary exchange
    primary_exchange_mic: Mapped[str | None] = mapped_column(
        String(4), ForeignKey("exchanges.mic"), index=True
    )
    primary_currency: Mapped[str | None] = mapped_column(
        String(3), ForeignKey("currencies.currency_code")
    )

    # Relationships
    identifiers = relationship("SecurityIdentifier", back_populates="security", lazy="selectin")
    equity_details = relationship("EquityDetails", back_populates="security", uselist=False, lazy="selectin")
    fixed_income_details = relationship("FixedIncomeDetails", back_populates="security", uselist=False, lazy="selectin")
    credit_ratings = relationship("CreditRating", backref="security", lazy="selectin")
    call_put_schedule = relationship("CallPutSchedule", backref="security", lazy="selectin")


class SecurityIdentifier(Base):
    """Security identifiers — all 8 types (Spec 4.3)."""

    __tablename__ = "security_identifiers"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    security_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("securities.security_id"), nullable=False, index=True
    )
    identifier_type: Mapped[str] = mapped_column(String(30), nullable=False)
    identifier_value: Mapped[str] = mapped_column(String(50), nullable=False)
    source: Mapped[str | None] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    security = relationship("Security", back_populates="identifiers")

    __table_args__ = (
        Index("uq_security_identifier", "identifier_type", "identifier_value", unique=True),
    )


class EquityDetails(Base):
    """Equity-specific security details (Spec 4.4)."""

    __tablename__ = "equity_details"

    security_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("securities.security_id"), primary_key=True
    )

    # Share structure
    shares_outstanding: Mapped[float | None] = mapped_column(Numeric(20, 2))
    shares_authorized: Mapped[float | None] = mapped_column(Numeric(20, 2))
    float_shares: Mapped[float | None] = mapped_column(Numeric(20, 2))

    # Par value
    par_value: Mapped[float | None] = mapped_column(Numeric(10, 4))
    par_value_currency: Mapped[str | None] = mapped_column(
        String(3), ForeignKey("currencies.currency_code")
    )

    # Voting
    voting_rights: Mapped[bool | None] = mapped_column(Boolean)
    votes_per_share: Mapped[float | None] = mapped_column(Numeric(5, 2))

    # Dividend
    dividend_frequency: Mapped[str | None] = mapped_column(String(20))
    dividend_currency: Mapped[str | None] = mapped_column(
        String(3), ForeignKey("currencies.currency_code")
    )

    # Share class
    share_class: Mapped[str | None] = mapped_column(String(5))
    share_class_description: Mapped[str | None] = mapped_column(String(200))
    conversion_ratio: Mapped[float | None] = mapped_column(Numeric(10, 4))

    security = relationship("Security", back_populates="equity_details")


class FixedIncomeDetails(Base):
    """Fixed income-specific security details (Spec 4.5)."""

    __tablename__ = "fixed_income_details"

    security_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("securities.security_id"), primary_key=True
    )

    # Principal
    face_value: Mapped[float | None] = mapped_column(Numeric(20, 4))
    face_currency: Mapped[str | None] = mapped_column(
        String(3), ForeignKey("currencies.currency_code")
    )
    minimum_denomination: Mapped[float | None] = mapped_column(Numeric(20, 2))

    # Coupon
    coupon_rate: Mapped[float | None] = mapped_column(Numeric(10, 6))
    coupon_type: Mapped[str | None] = mapped_column(String(20))
    coupon_frequency: Mapped[str | None] = mapped_column(String(20))
    day_count_convention: Mapped[str | None] = mapped_column(String(20))

    # Floating rate
    spread: Mapped[float | None] = mapped_column(Numeric(10, 4))
    reference_rate: Mapped[str | None] = mapped_column(String(50))
    reset_frequency: Mapped[str | None] = mapped_column(String(20))
    floor: Mapped[float | None] = mapped_column(Numeric(10, 6))
    cap: Mapped[float | None] = mapped_column(Numeric(10, 6))

    # Dates
    first_coupon_date: Mapped[date | None] = mapped_column(Date)
    last_coupon_date: Mapped[date | None] = mapped_column(Date)
    first_settlement_date: Mapped[date | None] = mapped_column(Date)

    # Seniority & security
    seniority: Mapped[str | None] = mapped_column(String(30))
    collateral_type: Mapped[str | None] = mapped_column(String(200))

    # Call/put features
    callable: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    puttable: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Covenants
    has_financial_covenants: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    has_negative_pledge: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    has_cross_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Credit
    rated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    security = relationship("Security", back_populates="fixed_income_details")


class CreditRating(Base):
    """Credit ratings from agencies (Spec 4.5)."""

    __tablename__ = "credit_ratings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    security_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("securities.security_id"), nullable=False, index=True
    )
    agency: Mapped[str] = mapped_column(String(50), nullable=False)
    rating: Mapped[str] = mapped_column(String(10), nullable=False)
    outlook: Mapped[str | None] = mapped_column(String(20))
    rating_date: Mapped[date | None] = mapped_column(Date)
    source: Mapped[str | None] = mapped_column(String(50))


class CallPutSchedule(Base):
    """Call/put date schedules for fixed income (Spec 4.5)."""

    __tablename__ = "call_put_schedule"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    security_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("securities.security_id"), nullable=False, index=True
    )
    schedule_type: Mapped[str] = mapped_column(String(4), nullable=False)  # CALL or PUT
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    price: Mapped[float | None] = mapped_column(Numeric(10, 4))
    notes: Mapped[str | None] = mapped_column(String(200))


class EODPrice(Base):
    """End-of-day price reference (Spec 4.6)."""

    __tablename__ = "eod_prices"

    security_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("securities.security_id"), primary_key=True
    )
    price_date: Mapped[date] = mapped_column(Date, primary_key=True)

    open: Mapped[float | None] = mapped_column(Numeric(18, 6))
    high: Mapped[float | None] = mapped_column(Numeric(18, 6))
    low: Mapped[float | None] = mapped_column(Numeric(18, 6))
    close: Mapped[float | None] = mapped_column(Numeric(18, 6))
    close_adjusted: Mapped[float | None] = mapped_column(Numeric(18, 6))
    volume: Mapped[int | None] = mapped_column(Numeric(20, 0))
    currency: Mapped[str | None] = mapped_column(
        String(3), ForeignKey("currencies.currency_code")
    )
    adjustment_factor: Mapped[float | None] = mapped_column(Numeric(18, 10))
    source: Mapped[str | None] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
