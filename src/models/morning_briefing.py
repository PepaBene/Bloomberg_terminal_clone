"""Pillar 3 Phase 4A: Morning briefing and user preference models."""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin


class MorningBriefing(TimestampMixin, Base):
    """AI-generated daily morning briefing for a user."""

    __tablename__ = "morning_briefings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # M-004: real FK to the authenticated users table (was a bare, FK-less
    # String(100) -- see migration 088 for the real-auth wiring).
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False, index=True
    )
    briefing_date: Mapped[date] = mapped_column(Date, nullable=False)
    regional_context: Mapped[str | None] = mapped_column(String(10))
    executive_summary: Mapped[str | None] = mapped_column(Text)
    portfolio_impact: Mapped[dict | None] = mapped_column(JSONB)
    key_news: Mapped[dict | None] = mapped_column(JSONB)
    thesis_updates: Mapped[dict | None] = mapped_column(JSONB)
    macro_context: Mapped[dict | None] = mapped_column(JSONB)
    actionable_insights: Mapped[dict | None] = mapped_column(JSONB)
    delivery_format: Mapped[str | None] = mapped_column(String(15))
    ai_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    __table_args__ = (
        {"extend_existing": True},
    )


class BriefingPreference(TimestampMixin, Base):
    """User preferences for morning briefing personalization."""

    __tablename__ = "briefing_preferences"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # M-004: real FK to users (see migration 088).
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False, unique=True
    )
    portfolio_entity_ids: Mapped[dict | None] = mapped_column(JSONB)
    watchlist_entity_ids: Mapped[dict | None] = mapped_column(JSONB)
    sector_focus: Mapped[dict | None] = mapped_column(JSONB)
    risk_tolerance: Mapped[str | None] = mapped_column(String(15))
    delivery_time_utc: Mapped[str | None] = mapped_column(String(5))
    delivery_format: Mapped[str | None] = mapped_column(String(15))
    timezone: Mapped[str | None] = mapped_column(String(30))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
