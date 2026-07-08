"""Pillar 3 Phase 4A: Company primer generation models."""

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin


class CompanyPrimer(TimestampMixin, Base):
    """AI-generated company research primer."""

    __tablename__ = "research_primers"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entities.entity_id"), nullable=False
    )
    primer_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    generated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    executive_summary: Mapped[str | None] = mapped_column(Text)
    business_model: Mapped[dict | None] = mapped_column(JSONB)
    competitive_landscape: Mapped[dict | None] = mapped_column(JSONB)
    financial_health: Mapped[dict | None] = mapped_column(JSONB)
    strategic_initiatives: Mapped[dict | None] = mapped_column(JSONB)
    risk_factors: Mapped[dict | None] = mapped_column(JSONB)
    analyst_consensus: Mapped[dict | None] = mapped_column(JSONB)
    recent_catalysts: Mapped[dict | None] = mapped_column(JSONB)
    data_completeness_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    last_filing_date: Mapped[date | None] = mapped_column(Date)
    last_earnings_call_date: Mapped[date | None] = mapped_column(Date)
    ai_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    prompt_template_used: Mapped[str | None] = mapped_column(String(50))


class PrimerRefreshLog(Base):
    """Tracks primer refresh events and their status."""

    __tablename__ = "primer_refresh_log"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entities.entity_id"), nullable=False
    )
    refresh_type: Mapped[str] = mapped_column(String(15), nullable=False)
    trigger_event: Mapped[str | None] = mapped_column(String(50))
    status: Mapped[str | None] = mapped_column(String(15), default="PENDING")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
