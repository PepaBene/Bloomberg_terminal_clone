"""Layer 3 (Financial Adviser) chat storage —
AI_THREE_LAYER_REBUILD_PLAN.md §5.3: multi-turn conversations with the
adviser agent.
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class Conversation(Base):
    """One adviser chat thread."""

    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # Free-form string, not a UUID FK to `users` -- matches
    # Portfolio.user_id's existing convention throughout this codebase.
    user_id: Mapped[str] = mapped_column(String(100), nullable=False)
    portfolio_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("portfolios.id", ondelete="CASCADE"),
    )
    title: Mapped[str | None] = mapped_column(String(500))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    __table_args__ = (
        Index("idx_conversations_user_id", "user_id"),
    )


class ConversationMessage(Base):
    """One turn (user or assistant) within a conversation."""

    __tablename__ = "conversation_messages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False,
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # user|assistant
    content: Mapped[str] = mapped_column(Text, nullable=False)
    tool_calls: Mapped[list | None] = mapped_column(JSONB)
    citations: Mapped[list | None] = mapped_column(JSONB)
    tokens: Mapped[int | None] = mapped_column(Integer)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("idx_conversation_messages_conversation_id", "conversation_id", "created_at"),
    )
