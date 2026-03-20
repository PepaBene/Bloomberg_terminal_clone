"""Domain 4: Estimates models (Spec Section 6)."""

import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin


class ConsensusEstimate(Base):
    """Consensus analyst estimates for a security/metric/period (Spec 6.3)."""

    __tablename__ = "consensus_estimates"

    # Composite primary key
    security_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("securities.security_id"), primary_key=True
    )
    metric: Mapped[str] = mapped_column(String(30), primary_key=True)
    period_end_date: Mapped[date] = mapped_column(Date, primary_key=True)
    as_of_date: Mapped[date] = mapped_column(Date, primary_key=True)

    # Period identification
    fiscal_year: Mapped[int] = mapped_column(Integer, nullable=False)
    fiscal_quarter: Mapped[int | None] = mapped_column(Integer)
    period_type: Mapped[str | None] = mapped_column(String(20))

    # Currency
    currency: Mapped[str | None] = mapped_column(
        String(3), ForeignKey("currencies.currency_code")
    )

    # Statistical aggregates
    mean: Mapped[float | None] = mapped_column(Numeric(20, 4))
    median: Mapped[float | None] = mapped_column(Numeric(20, 4))
    high: Mapped[float | None] = mapped_column(Numeric(20, 4))
    low: Mapped[float | None] = mapped_column(Numeric(20, 4))
    standard_deviation: Mapped[float | None] = mapped_column(Numeric(20, 4))

    # Analyst counts
    num_estimates: Mapped[int | None] = mapped_column(Integer)
    num_revisions_up: Mapped[int | None] = mapped_column(Integer)
    num_revisions_down: Mapped[int | None] = mapped_column(Integer)

    __table_args__ = (
        Index("idx_consensus_security", "security_id"),
        Index("idx_consensus_metric", "metric"),
        Index("idx_consensus_period", "period_end_date"),
    )


class EstimateSurprise(Base):
    """Earnings surprise — actual vs. consensus (Spec 6.3)."""

    __tablename__ = "estimate_surprises"

    surprise_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    security_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("securities.security_id"), nullable=False, index=True
    )

    # Period identification
    fiscal_year: Mapped[int] = mapped_column(Integer, nullable=False)
    fiscal_quarter: Mapped[int | None] = mapped_column(Integer)
    period_type: Mapped[str | None] = mapped_column(String(20))
    metric: Mapped[str] = mapped_column(String(30), nullable=False)

    # Values
    consensus_estimate: Mapped[float | None] = mapped_column(Numeric(20, 4))
    actual_value: Mapped[float | None] = mapped_column(Numeric(20, 4))
    surprise: Mapped[float | None] = mapped_column(Numeric(20, 4))
    surprise_percent: Mapped[float | None] = mapped_column(Numeric(20, 4))

    # Dates
    announcement_date: Mapped[date | None] = mapped_column(Date, index=True)

    __table_args__ = (
        Index("idx_surprise_security_metric", "security_id", "metric"),
    )


class CompanyGuidance(TimestampMixin, Base):
    """Company-issued guidance (Spec 6.3)."""

    __tablename__ = "company_guidance"

    guidance_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entities.entity_id"), nullable=False, index=True
    )
    security_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("securities.security_id")
    )

    # Period identification
    fiscal_year: Mapped[int] = mapped_column(Integer, nullable=False)
    fiscal_quarter: Mapped[int | None] = mapped_column(Integer)
    period_type: Mapped[str | None] = mapped_column(String(20))
    metric: Mapped[str] = mapped_column(String(30), nullable=False)

    # Guidance details
    guidance_type: Mapped[str | None] = mapped_column(String(20))
    point_estimate: Mapped[float | None] = mapped_column(Numeric(20, 4))
    low_estimate: Mapped[float | None] = mapped_column(Numeric(20, 4))
    high_estimate: Mapped[float | None] = mapped_column(Numeric(20, 4))
    currency: Mapped[str | None] = mapped_column(
        String(3), ForeignKey("currencies.currency_code")
    )
    qualitative_guidance: Mapped[str | None] = mapped_column(Text)
    guidance_date: Mapped[date | None] = mapped_column(Date)
    source_event: Mapped[str | None] = mapped_column(String(200))

    __table_args__ = (
        Index("idx_guidance_entity_metric", "entity_id", "metric"),
    )
