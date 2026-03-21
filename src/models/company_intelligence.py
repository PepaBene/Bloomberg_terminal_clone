"""Company intelligence and primer models (Pillar 2 Supplement – Part 7)."""

import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin


class CompanyBriefing(TimestampMixin, Base):
    """Cached AI-generated company intelligence briefing."""

    __tablename__ = "company_briefings"

    briefing_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entities.entity_id"),
        nullable=False, index=True,
    )
    briefing_type: Mapped[str] = mapped_column(String(20), nullable=False, default="DAILY")
    briefing_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="COMPLETED")
    summary_text: Mapped[str | None] = mapped_column(Text)
    key_signals: Mapped[dict | None] = mapped_column(JSONB)
    valuation_context: Mapped[dict | None] = mapped_column(JSONB)
    value_investing_lens: Mapped[dict | None] = mapped_column(JSONB)
    data_snapshot: Mapped[dict | None] = mapped_column(JSONB)
    ai_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index("idx_briefing_entity_type_date", "entity_id", "briefing_type", "briefing_date", unique=True),
    )


class CompanyPrimer(TimestampMixin, Base):
    """One-page company summary/primer."""

    __tablename__ = "company_primers"

    primer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entities.entity_id"),
        nullable=False, index=True,
    )
    generated_date: Mapped[date] = mapped_column(Date, nullable=False)
    business_description: Mapped[str | None] = mapped_column(Text)
    segments_breakdown: Mapped[dict | None] = mapped_column(JSONB)
    competitive_position: Mapped[str | None] = mapped_column(Text)
    financial_summary: Mapped[dict | None] = mapped_column(JSONB)
    valuation_summary: Mapped[dict | None] = mapped_column(JSONB)
    ownership_summary: Mapped[dict | None] = mapped_column(JSONB)
    key_risks: Mapped[dict | None] = mapped_column(JSONB)
    recent_developments: Mapped[dict | None] = mapped_column(JSONB)
    ai_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    __table_args__ = (
        Index("idx_primer_entity_date", "entity_id", "generated_date", unique=True),
    )
