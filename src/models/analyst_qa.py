"""Pillar 3 Phase 4B: Analyst Q&A models."""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class QASession(Base):
    """A question-answer session for analyst Q&A."""

    __tablename__ = "qa_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entities.entity_id"), nullable=True
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer_text: Mapped[str | None] = mapped_column(Text)
    answer_type: Mapped[str | None] = mapped_column(String(20))
    confidence_level: Mapped[Decimal | None] = mapped_column(Numeric(3, 2))
    confidence_narrative: Mapped[str | None] = mapped_column(Text)
    sources: Mapped[dict | None] = mapped_column(JSONB)
    supporting_data: Mapped[dict | None] = mapped_column(JSONB)
    follow_up_suggestions: Mapped[dict | None] = mapped_column(JSONB)
    data_completeness: Mapped[dict | None] = mapped_column(JSONB)
    user_rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    execution_time_ms: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class QAFeedback(Base):
    """Feedback on a Q&A session answer."""

    __tablename__ = "qa_feedback"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("qa_sessions.id"), nullable=False
    )
    rating: Mapped[int | None] = mapped_column(Integer)
    feedback_text: Mapped[str | None] = mapped_column(Text)
    is_accurate: Mapped[bool | None] = mapped_column(Boolean)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
