"""Pillar 1 FI Supplement D11.3+D11.4: Corporate Bond Reference + TRACE Pricing."""

import uuid
from datetime import date, time
from decimal import Decimal

from sqlalchemy import Boolean, Date, ForeignKey, Index, Integer, Numeric, String, Time
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TimestampMixin


class CorporateBond(TimestampMixin, Base):
    __tablename__ = "corporate_bonds"

    bond_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    cusip: Mapped[str] = mapped_column(String(9), nullable=False, unique=True, index=True)
    isin: Mapped[str | None] = mapped_column(String(12))
    figi: Mapped[str | None] = mapped_column(String(12))

    # Issuer
    issuer_entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entities.entity_id"), nullable=False, index=True
    )
    issuer_name: Mapped[str | None] = mapped_column(String(500))
    issuer_cik: Mapped[str | None] = mapped_column(String(10))

    # Security master link
    security_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))

    # Bond name
    name: Mapped[str] = mapped_column(String(500), nullable=False)

    # Coupon
    coupon_rate: Mapped[Decimal | None] = mapped_column(Numeric(8, 6))
    coupon_type: Mapped[str | None] = mapped_column(String(20))
    coupon_frequency: Mapped[int | None] = mapped_column(Integer)
    day_count_convention: Mapped[str | None] = mapped_column(String(20))
    floating_reference_rate: Mapped[str | None] = mapped_column(String(20))
    floating_spread_bps: Mapped[int | None] = mapped_column(Integer)

    # Dates
    issue_date: Mapped[date | None] = mapped_column(Date)
    maturity_date: Mapped[date] = mapped_column(Date, nullable=False)
    first_coupon_date: Mapped[date | None] = mapped_column(Date)

    # Size
    original_issue_amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 2))
    outstanding_amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 2))
    minimum_denomination: Mapped[Decimal | None] = mapped_column(Numeric(20, 2))
    currency: Mapped[str | None] = mapped_column(String(3))

    # Seniority
    seniority: Mapped[str | None] = mapped_column(String(30))
    collateral_type: Mapped[str | None] = mapped_column(String(200))
    is_guaranteed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    guarantor_entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))

    # Embedded options
    is_callable: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    callable_from_date: Mapped[date | None] = mapped_column(Date)
    call_type: Mapped[str | None] = mapped_column(String(20))
    is_puttable: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_convertible: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    conversion_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))

    # Initial ratings
    initial_rating_sp: Mapped[str | None] = mapped_column(String(10))
    initial_rating_moodys: Mapped[str | None] = mapped_column(String(10))
    initial_rating_fitch: Mapped[str | None] = mapped_column(String(10))
    is_investment_grade: Mapped[bool | None] = mapped_column(Boolean)

    # Use of proceeds
    use_of_proceeds: Mapped[str | None] = mapped_column(String(30))
    use_of_proceeds_text: Mapped[str | None] = mapped_column(String(200))

    # Covenants
    has_change_of_control_put: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    has_negative_pledge: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    has_leverage_covenant: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    has_interest_coverage_covenant: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )

    # Filing provenance
    source_filing_accession: Mapped[str | None] = mapped_column(String(25))
    source_filing_type: Mapped[str | None] = mapped_column(String(10))
    source_filing_date: Mapped[date | None] = mapped_column(Date)

    # Status
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="OUTSTANDING")
    status_date: Mapped[date | None] = mapped_column(Date)
    status_reason: Mapped[str | None] = mapped_column(String(200))

    # Relationships
    call_schedule = relationship("BondCallSchedule", back_populates="bond", lazy="selectin")

    __table_args__ = (
        Index("idx_corp_bond_issuer", "issuer_entity_id"),
        Index("idx_corp_bond_maturity", "maturity_date"),
        Index("idx_corp_bond_status", "status"),
    )


class BondCallSchedule(TimestampMixin, Base):
    __tablename__ = "bond_call_schedules"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    bond_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("corporate_bonds.bond_id"),
        nullable=False,
        index=True,
    )
    call_date: Mapped[date] = mapped_column(Date, nullable=False)
    call_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    call_type: Mapped[str | None] = mapped_column(String(20))

    bond = relationship("CorporateBond", back_populates="call_schedule")


class BondTrade(TimestampMixin, Base):
    __tablename__ = "bond_trades"

    trade_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    bond_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("corporate_bonds.bond_id"),
        nullable=False,
    )
    trade_date: Mapped[date] = mapped_column(Date, nullable=False)
    trade_time: Mapped[time | None] = mapped_column(Time)
    settlement_date: Mapped[date | None] = mapped_column(Date)
    price: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))
    yield_value: Mapped[Decimal | None] = mapped_column(Numeric(8, 6))
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(20, 2))
    quantity_reported: Mapped[str | None] = mapped_column(String(10))
    trade_type: Mapped[str | None] = mapped_column(String(20))
    is_when_issued: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    source: Mapped[str | None] = mapped_column(String(20))

    __table_args__ = (
        Index("idx_bond_trade_bond_date", "bond_id", "trade_date"),
    )


class BondEODPrice(TimestampMixin, Base):
    __tablename__ = "bond_eod_prices"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    bond_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("corporate_bonds.bond_id"),
        nullable=False,
    )
    price_date: Mapped[date] = mapped_column(Date, nullable=False)
    last_trade_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))
    vwap: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))
    high_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))
    low_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))
    trade_count: Mapped[int | None] = mapped_column(Integer)
    total_volume: Mapped[Decimal | None] = mapped_column(Numeric(20, 2))
    yield_to_maturity: Mapped[Decimal | None] = mapped_column(Numeric(8, 6))
    yield_to_worst: Mapped[Decimal | None] = mapped_column(Numeric(8, 6))
    g_spread_bps: Mapped[int | None] = mapped_column(Integer)
    treasury_benchmark_cusip: Mapped[str | None] = mapped_column(String(9))
    liquidity_score: Mapped[int | None] = mapped_column(Integer)
    has_sufficient_trades: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    price_source: Mapped[str | None] = mapped_column(String(20))

    __table_args__ = (
        Index("idx_bond_eod_bond_date", "bond_id", "price_date", unique=True),
    )
