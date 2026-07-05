"""Pillar 3 Phase 4B: Investment thesis models."""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin


class InvestmentThesis(TimestampMixin, Base):
    """An AI-assisted investment thesis for an entity."""

    __tablename__ = "investment_theses"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entities.entity_id"), nullable=False, index=True
    )
    # TODO: Add ForeignKey("users.id") once the users table is created.
    analyst_id: Mapped[str] = mapped_column(String(100), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    thesis_title: Mapped[str | None] = mapped_column(String(200))
    investment_horizon: Mapped[str | None] = mapped_column(String(10))
    conviction_level: Mapped[str | None] = mapped_column(String(15))
    executive_summary: Mapped[str | None] = mapped_column(Text)
    key_drivers: Mapped[dict | None] = mapped_column(JSONB)  # [{driver: str, impact: str, confidence: float}]
    primary_risks: Mapped[dict | None] = mapped_column(JSONB)  # [{risk: str, severity: str, likelihood: float}]
    valuation_scenarios: Mapped[dict | None] = mapped_column(JSONB)  # {bull: {target, rationale}, base: {...}, bear: {...}}
    catalysts: Mapped[dict | None] = mapped_column(JSONB)  # [{catalyst: str, expected_date: str, impact: str}]
    quality_metrics: Mapped[dict | None] = mapped_column(JSONB)  # {data_coverage: float, staleness_days: int, ...}
    elevator_pitch: Mapped[str | None] = mapped_column(String(500))
    slide_outline: Mapped[dict | None] = mapped_column(JSONB)  # [{slide_number: int, title: str, bullets: [str]}]
    ai_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class ThesisVersion(Base):
    """A versioned snapshot of an investment thesis."""

    __tablename__ = "thesis_versions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    thesis_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("investment_theses.id", ondelete="CASCADE"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    conviction_change: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    updated_drivers: Mapped[dict | None] = mapped_column(JSONB)  # [{driver: str, change: str, impact: str}]
    analyst_note: Mapped[str | None] = mapped_column(Text)
    snapshot_data: Mapped[dict | None] = mapped_column(JSONB)  # Full thesis state at this version point
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
