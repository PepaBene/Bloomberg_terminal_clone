"""Domain 6: Ownership models (Spec Section 8)."""

import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin


class InstitutionProfile(TimestampMixin, Base):
    """Institutional investor profile (Spec 8.2)."""

    __tablename__ = "institution_profiles"

    institution_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    entity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entities.entity_id"), unique=True, nullable=True
    )
    cik: Mapped[str | None] = mapped_column(String(10))
    institution_name: Mapped[str] = mapped_column(String(300), nullable=False, index=True)
    institution_type: Mapped[str | None] = mapped_column(String(30), index=True)
    tier: Mapped[str | None] = mapped_column(String(10))
    aum: Mapped[float | None] = mapped_column(Numeric(20, 2))
    number_of_holdings: Mapped[int | None] = mapped_column(Integer)

    __table_args__ = (
        Index("idx_institution_profiles_type", "institution_type"),
    )


class InstitutionalHolding(Base):
    """Institutional ownership of securities via 13F filings (Spec 8.2)."""

    __tablename__ = "institutional_holdings"

    institution_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("institution_profiles.institution_id"),
        primary_key=True,
    )
    security_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("securities.security_id"),
        primary_key=True,
    )
    report_date: Mapped[date] = mapped_column(Date, primary_key=True)
    filing_date: Mapped[date | None] = mapped_column(Date)
    shares_held: Mapped[float | None] = mapped_column(Numeric(20, 2))
    market_value: Mapped[float | None] = mapped_column(Numeric(20, 2))
    percent_of_portfolio: Mapped[float | None] = mapped_column(Numeric(8, 4))
    percent_of_outstanding: Mapped[float | None] = mapped_column(Numeric(8, 4))
    shares_change: Mapped[float | None] = mapped_column(Numeric(20, 2))
    is_new_position: Mapped[bool | None] = mapped_column(Boolean)
    is_sold_out: Mapped[bool | None] = mapped_column(Boolean)
    source: Mapped[str | None] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("idx_institutional_holdings_security", "security_id"),
        Index("idx_institutional_holdings_report_date", "report_date"),
    )


class InsiderHolding(Base):
    """Insider transactions and holdings (Spec 8.3)."""

    __tablename__ = "insider_holdings"

    transaction_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    security_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("securities.security_id"), nullable=False, index=True
    )
    entity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entities.entity_id"), index=True
    )
    insider_name: Mapped[str | None] = mapped_column(String(200))
    insider_title: Mapped[str | None] = mapped_column(String(100))
    insider_relationship: Mapped[str | None] = mapped_column(String(30))
    transaction_type: Mapped[str | None] = mapped_column(String(20))
    transaction_date: Mapped[date | None] = mapped_column(Date, index=True)
    shares_transacted: Mapped[float | None] = mapped_column(Numeric(20, 2))
    price_per_share: Mapped[float | None] = mapped_column(Numeric(18, 6))
    total_value: Mapped[float | None] = mapped_column(Numeric(20, 2))
    shares_owned_after: Mapped[float | None] = mapped_column(Numeric(20, 2))
    ownership_nature: Mapped[str | None] = mapped_column(String(10))

    __table_args__ = (
        Index("idx_insider_holdings_security_date", "security_id", "transaction_date"),
    )


class OwnershipSummary(Base):
    """Aggregated ownership summary per security (Spec 8.4)."""

    __tablename__ = "ownership_summaries"

    security_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("securities.security_id"),
        primary_key=True,
    )
    report_date: Mapped[date] = mapped_column(Date, primary_key=True)
    institutional_holders_count: Mapped[int | None] = mapped_column(Integer)
    institutional_shares: Mapped[float | None] = mapped_column(Numeric(20, 2))
    insider_shares: Mapped[float | None] = mapped_column(Numeric(20, 2))
    institutional_percent: Mapped[float | None] = mapped_column(Numeric(8, 4))
    insider_percent: Mapped[float | None] = mapped_column(Numeric(8, 4))
    top_10_concentration: Mapped[float | None] = mapped_column(Numeric(8, 4))

    __table_args__ = (
        Index("idx_ownership_summaries_security", "security_id"),
    )


class BeneficialOwnershipFiling(TimestampMixin, Base):
    """Beneficial ownership disclosures from SEC Schedule 13D / 13G filings.

    SC 13D is filed by a beneficial owner of >5% of a class of equity
    securities who has (or intends to influence/change) control of the
    issuer -- the "activist" schedule. SC 13G is the short-form alternative
    for passive holders (qualified institutional investors, exempt
    investors, or holders below the control threshold). ``schedule_type``
    carries the raw EDGAR form string ("SC 13D", "SC 13D/A", "SC 13G",
    "SC 13G/A"); ``is_activist`` is a convenience flag for the 13D family.
    """

    __tablename__ = "beneficial_ownership_filings"

    filing_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    issuer_entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entities.entity_id"), nullable=False
    )
    security_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("securities.security_id")
    )

    # The reporting person (activist fund, individual, institution). Often
    # NOT a pre-existing covered entity, so the FK is nullable and the name
    # is always kept denormalized -- same idiom as MandADeal.acquirer_*.
    filer_entity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entities.entity_id")
    )
    filer_name: Mapped[str] = mapped_column(String(300), nullable=False)
    filer_cik: Mapped[str | None] = mapped_column(String(10))
    reporting_person_type: Mapped[str | None] = mapped_column(String(5))

    schedule_type: Mapped[str] = mapped_column(String(10), nullable=False)
    is_activist: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_amendment: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    filing_date: Mapped[date] = mapped_column(Date, nullable=False)
    event_date: Mapped[date | None] = mapped_column(Date)

    shares_owned: Mapped[float | None] = mapped_column(Numeric(20, 2))
    percent_of_class: Mapped[float | None] = mapped_column(Numeric(8, 4))
    sole_voting_power: Mapped[float | None] = mapped_column(Numeric(20, 2))
    shared_voting_power: Mapped[float | None] = mapped_column(Numeric(20, 2))
    sole_dispositive_power: Mapped[float | None] = mapped_column(Numeric(20, 2))
    shared_dispositive_power: Mapped[float | None] = mapped_column(Numeric(20, 2))

    accession_number: Mapped[str | None] = mapped_column(String(30))
    filing_url: Mapped[str | None] = mapped_column(String(500))
    source: Mapped[str | None] = mapped_column(String(50))

    __table_args__ = (
        Index("idx_beneficial_ownership_issuer_date", "issuer_entity_id", "filing_date"),
        Index("idx_beneficial_ownership_security", "security_id"),
        Index("idx_beneficial_ownership_filer", "filer_entity_id"),
        Index("idx_beneficial_ownership_schedule_type", "schedule_type"),
        Index("uq_beneficial_ownership_accession", "accession_number", unique=True),
    )


class ShortInterest(Base):
    """Short interest data per security (Spec 8.5)."""

    __tablename__ = "short_interest"

    security_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("securities.security_id"),
        primary_key=True,
    )
    settlement_date: Mapped[date] = mapped_column(Date, primary_key=True)
    shares_short: Mapped[float | None] = mapped_column(Numeric(20, 2))
    short_percent_float: Mapped[float | None] = mapped_column(Numeric(8, 4))
    short_percent_outstanding: Mapped[float | None] = mapped_column(Numeric(8, 4))
    days_to_cover: Mapped[float | None] = mapped_column(Numeric(8, 2))
    source: Mapped[str | None] = mapped_column(String(30))

    __table_args__ = (
        Index("idx_short_interest_security", "security_id"),
        Index("idx_short_interest_security_settle", "security_id", "settlement_date"),
    )
