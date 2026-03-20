"""Domain 9: ESG & Sustainability models (Spec Section 11)."""

import uuid
from datetime import date

from sqlalchemy import Boolean, Date, ForeignKey, Index, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin


class ESGScore(TimestampMixin, Base):
    """ESG scores from rating providers (Spec 11.2)."""

    __tablename__ = "esg_scores"

    score_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entities.entity_id"), nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False)

    # Composite scores
    esg_score: Mapped[float | None] = mapped_column(Numeric(5, 2))
    esg_percentile: Mapped[float | None] = mapped_column(Numeric(5, 2))
    esg_rating: Mapped[str | None] = mapped_column(String(10))

    # Pillar scores
    environmental_score: Mapped[float | None] = mapped_column(Numeric(5, 2))
    social_score: Mapped[float | None] = mapped_column(Numeric(5, 2))
    governance_score: Mapped[float | None] = mapped_column(Numeric(5, 2))

    # Controversy
    controversy_score: Mapped[float | None] = mapped_column(Numeric(5, 2))
    controversy_level: Mapped[str | None] = mapped_column(String(10))

    # Trend
    score_trend: Mapped[str | None] = mapped_column(String(20))

    __table_args__ = (
        Index(
            "uq_esg_score_entity_provider_date",
            "entity_id",
            "provider",
            "as_of_date",
            unique=True,
        ),
    )


class ESGMetric(TimestampMixin, Base):
    """Individual ESG metrics and data points (Spec 11.3)."""

    __tablename__ = "esg_metrics"

    metric_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entities.entity_id"), nullable=False, index=True
    )
    metric_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    metric_category: Mapped[str | None] = mapped_column(String(20))
    period_end_date: Mapped[date | None] = mapped_column(Date)
    period_type: Mapped[str | None] = mapped_column(String(20))
    value: Mapped[float | None] = mapped_column(Numeric(20, 6))
    unit: Mapped[str | None] = mapped_column(String(50))
    is_reported: Mapped[bool | None] = mapped_column(Boolean)
    source: Mapped[str | None] = mapped_column(String(50))


class ESGControversy(TimestampMixin, Base):
    """ESG controversies and incidents (Spec 11.3)."""

    __tablename__ = "esg_controversies"

    controversy_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entities.entity_id"), nullable=False, index=True
    )
    controversy_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    severity: Mapped[str | None] = mapped_column(String(10))
    description: Mapped[str | None] = mapped_column(Text)
    start_date: Mapped[date | None] = mapped_column(Date)
    resolution_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str | None] = mapped_column(String(20))
    estimated_financial_impact: Mapped[float | None] = mapped_column(Numeric(20, 2))
    source: Mapped[str | None] = mapped_column(String(50))
    source_url: Mapped[str | None] = mapped_column(String(500))
