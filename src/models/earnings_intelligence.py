"""Pillar 1 Supplement: Earnings Intelligence models (Part 3)."""

import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, Index, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin


class EarningsSurprise(TimestampMixin, Base):
    """Earnings surprise data with market reaction metrics."""

    __tablename__ = "earnings_surprises"

    surprise_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entities.entity_id"), nullable=False, index=True
    )
    security_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("securities.security_id")
    )

    # Period
    fiscal_year: Mapped[int] = mapped_column(Integer, nullable=False)
    fiscal_quarter: Mapped[int] = mapped_column(Integer, nullable=False)
    period_end_date: Mapped[date | None] = mapped_column(Date)

    # Actuals
    actual_eps: Mapped[float | None] = mapped_column(Numeric(12, 4))
    actual_revenue: Mapped[float | None] = mapped_column(Numeric(20, 2))
    actual_ebitda: Mapped[float | None] = mapped_column(Numeric(20, 2))

    # Consensus
    consensus_eps: Mapped[float | None] = mapped_column(Numeric(12, 4))
    consensus_revenue: Mapped[float | None] = mapped_column(Numeric(20, 2))
    consensus_ebitda: Mapped[float | None] = mapped_column(Numeric(20, 2))
    number_of_estimates: Mapped[int | None] = mapped_column(Integer)

    # Surprise
    eps_surprise: Mapped[float | None] = mapped_column(Numeric(12, 4))
    eps_surprise_pct: Mapped[float | None] = mapped_column(Numeric(8, 4))
    revenue_surprise: Mapped[float | None] = mapped_column(Numeric(20, 2))
    revenue_surprise_pct: Mapped[float | None] = mapped_column(Numeric(8, 4))

    # Market reaction
    announcement_date: Mapped[date | None] = mapped_column(Date, index=True)
    pre_earnings_close: Mapped[float | None] = mapped_column(Numeric(12, 4))
    post_earnings_close: Mapped[float | None] = mapped_column(Numeric(12, 4))
    price_reaction_pct: Mapped[float | None] = mapped_column(Numeric(8, 4))
    price_reaction_5d_pct: Mapped[float | None] = mapped_column(Numeric(8, 4))

    # Source
    source_filing_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))

    __table_args__ = (
        Index("idx_surprise_entity_period", "entity_id", "fiscal_year", "fiscal_quarter"),
        Index("idx_surprise_announcement", "announcement_date"),
    )


class GuidanceTracking(TimestampMixin, Base):
    """Corporate guidance vs. consensus tracking."""

    __tablename__ = "guidance_tracking"

    guidance_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entities.entity_id"), nullable=False, index=True
    )

    # Period
    guidance_fiscal_year: Mapped[int] = mapped_column(Integer, nullable=False)
    guidance_fiscal_quarter: Mapped[int | None] = mapped_column(Integer)

    # Guidance detail
    metric: Mapped[str] = mapped_column(String(20), nullable=False)
    guidance_low: Mapped[float | None] = mapped_column(Numeric(20, 4))
    guidance_high: Mapped[float | None] = mapped_column(Numeric(20, 4))
    guidance_midpoint: Mapped[float | None] = mapped_column(Numeric(20, 4))
    guidance_date: Mapped[date] = mapped_column(Date, nullable=False)
    guidance_type: Mapped[str | None] = mapped_column(String(15))

    # Prior guidance
    prior_guidance_low: Mapped[float | None] = mapped_column(Numeric(20, 4))
    prior_guidance_high: Mapped[float | None] = mapped_column(Numeric(20, 4))

    # Consensus comparison
    consensus_at_guidance_date: Mapped[float | None] = mapped_column(Numeric(20, 4))
    guidance_vs_consensus: Mapped[str | None] = mapped_column(String(10))

    # Source
    source_filing_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))

    __table_args__ = (
        Index("idx_guidance_entity_year", "entity_id", "guidance_fiscal_year"),
        Index("idx_guidance_date", "guidance_date"),
    )
