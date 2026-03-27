"""Pillar 3 Phase 4C: Macro theme score and scenario models."""

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class MacroThemeScore(Base):
    """Exposure score for an entity against a macro theme."""

    __tablename__ = "macro_theme_scores"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entities.entity_id"), nullable=False, index=True
    )
    theme: Mapped[str] = mapped_column(String(25), nullable=False)
    exposure_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    sensitivity_direction: Mapped[str | None] = mapped_column(String(10))
    evidence: Mapped[dict | None] = mapped_column(JSONB)
    quantified_exposure: Mapped[str | None] = mapped_column(String(500))
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now()
    )


class MacroScenario(Base):
    """A macro scenario definition for what-if analysis."""

    __tablename__ = "macro_scenarios"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    scenario_name: Mapped[str] = mapped_column(String(50), nullable=False)
    scenario_type: Mapped[str | None] = mapped_column(String(20))
    description: Mapped[str | None] = mapped_column(Text)
    assumptions: Mapped[dict | None] = mapped_column(JSONB)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now()
    )
