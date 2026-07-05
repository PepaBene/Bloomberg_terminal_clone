"""Pillar 1 Supplement: Capital Structure Analysis models (CAST)."""

import uuid
from datetime import date

from sqlalchemy import Boolean, Date, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TimestampMixin


class CapitalStructure(TimestampMixin, Base):
    """Aggregate capital structure snapshot for an entity at a point in time."""

    __tablename__ = "capital_structures"

    capital_structure_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entities.entity_id"), nullable=False, index=True
    )
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False)
    # The filings table is named ``filings`` in fundamentals.py; the
    # original ``sec_filings`` reference was a stale name from an early
    # spec that prevented the metadata from compiling.
    filing_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("filings.filing_id")
    )

    # Aggregate metrics
    total_debt: Mapped[float | None] = mapped_column(Numeric(20, 2))
    total_long_term_debt: Mapped[float | None] = mapped_column(Numeric(20, 2))
    total_short_term_debt: Mapped[float | None] = mapped_column(Numeric(20, 2))
    total_preferred_stock: Mapped[float | None] = mapped_column(Numeric(20, 2))
    net_debt: Mapped[float | None] = mapped_column(Numeric(20, 2))
    total_capitalization: Mapped[float | None] = mapped_column(Numeric(20, 2))
    debt_to_capitalization: Mapped[float | None] = mapped_column(Numeric(8, 4))

    # Metadata
    source: Mapped[str | None] = mapped_column(String(20))
    extraction_method: Mapped[str | None] = mapped_column(String(30))
    confidence_score: Mapped[float | None] = mapped_column(Numeric(4, 3))

    # Relationships
    tranches = relationship(
        "DebtTranche", back_populates="capital_structure", lazy="selectin", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_capstruct_entity_date", "entity_id", "as_of_date"),
    )


class DebtTranche(TimestampMixin, Base):
    """Individual debt obligation within a capital structure."""

    __tablename__ = "debt_tranches"

    tranche_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entities.entity_id"), nullable=False, index=True
    )
    capital_structure_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("capital_structures.capital_structure_id"),
        nullable=False,
    )

    # Identification
    instrument_name: Mapped[str | None] = mapped_column(String(300))
    instrument_type: Mapped[str | None] = mapped_column(String(40))

    # Terms
    principal_amount: Mapped[float | None] = mapped_column(Numeric(20, 2))
    original_amount: Mapped[float | None] = mapped_column(Numeric(20, 2))
    currency: Mapped[str | None] = mapped_column(
        String(3), ForeignKey("currencies.currency_code")
    )
    coupon_rate: Mapped[float | None] = mapped_column(Numeric(8, 4))
    coupon_type: Mapped[str | None] = mapped_column(String(10))
    floating_reference: Mapped[str | None] = mapped_column(String(20))
    floating_spread: Mapped[float | None] = mapped_column(Numeric(8, 2))

    # Dates
    issue_date: Mapped[date | None] = mapped_column(Date)
    maturity_date: Mapped[date | None] = mapped_column(Date)
    first_call_date: Mapped[date | None] = mapped_column(Date)
    next_put_date: Mapped[date | None] = mapped_column(Date)

    # Seniority & security
    seniority_rank: Mapped[int | None] = mapped_column(Integer)
    seniority_type: Mapped[str | None] = mapped_column(String(30))
    collateral_description: Mapped[str | None] = mapped_column(Text)

    # Covenant flags
    has_financial_covenants: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    has_change_of_control: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    has_cross_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Related security (if publicly traded)
    security_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("securities.security_id")
    )

    # Source
    source_filing_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    extracted_from: Mapped[str | None] = mapped_column(String(30))

    # Relationships
    capital_structure = relationship("CapitalStructure", back_populates="tranches")

    __table_args__ = (
        Index("idx_tranche_entity_maturity", "entity_id", "maturity_date"),
        Index("idx_tranche_capstruct", "capital_structure_id"),
    )
