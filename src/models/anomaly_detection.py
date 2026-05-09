"""Pillar 3 Phase 4A: Anomaly detection models."""

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin


class DetectedAnomaly(TimestampMixin, Base):
    """A detected market/fundamental anomaly for an entity."""

    __tablename__ = "detected_anomalies"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entities.entity_id"), nullable=False, index=True
    )
    anomaly_type: Mapped[str] = mapped_column(String(60), nullable=False)
    severity_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    detected_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    anomaly_window_start: Mapped[date | None] = mapped_column(Date)
    anomaly_window_end: Mapped[date | None] = mapped_column(Date)
    lookback_period: Mapped[str | None] = mapped_column(String(10))
    observed_value: Mapped[Decimal | None] = mapped_column(Numeric(15, 4))
    expected_value: Mapped[Decimal | None] = mapped_column(Numeric(15, 4))
    z_score: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    percentile_rank: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    contextual_analysis: Mapped[dict | None] = mapped_column(JSONB)
    related_data: Mapped[dict | None] = mapped_column(JSONB)
    ai_narrative: Mapped[str | None] = mapped_column(Text)
    recommended_actions: Mapped[dict | None] = mapped_column(JSONB)
    confidence_level: Mapped[Decimal | None] = mapped_column(Numeric(3, 2))
    is_acknowledged: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    acknowledged_by: Mapped[str | None] = mapped_column(String(100))


class AnomalyRule(TimestampMixin, Base):
    """Configurable anomaly detection rule."""

    __tablename__ = "anomaly_rules"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    anomaly_type: Mapped[str] = mapped_column(String(60), nullable=False)
    rule_name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    threshold_config: Mapped[dict | None] = mapped_column(JSONB)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
