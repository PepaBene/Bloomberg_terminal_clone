"""Pillar 4 Phase 4: Research Notes model."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin


class ResearchNote(TimestampMixin, Base):
    """User research notes linked to entities/portfolios."""

    __tablename__ = "research_notes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)  # markdown
    note_type: Mapped[str] = mapped_column(
        String(30), nullable=False, default="GENERAL"
    )  # GENERAL, THESIS, EARNINGS, FILING, MEETING, TRADE_IDEA
    entity_id: Mapped[str | None] = mapped_column(String(50), index=True)  # linked entity
    portfolio_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("portfolios.id"), index=True
    )
    security_id: Mapped[str | None] = mapped_column(String(50), index=True)
    ticker: Mapped[str | None] = mapped_column(String(20))
    tags: Mapped[dict | None] = mapped_column(JSONB)  # stored as JSON list of strings
    sentiment: Mapped[str | None] = mapped_column(String(10))  # BULLISH, BEARISH, NEUTRAL
    priority: Mapped[str | None] = mapped_column(String(10), default="NORMAL")  # LOW, NORMAL, HIGH, URGENT
    is_pinned: Mapped[bool | None] = mapped_column(default=False)
    is_archived: Mapped[bool | None] = mapped_column(default=False)
    attachments: Mapped[dict | None] = mapped_column(JSONB)  # [{filename, url, type}, ...]
