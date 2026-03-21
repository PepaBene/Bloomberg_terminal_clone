"""Pillar 1 Supplement: Corporate Actions Calendar models (CACS)."""

import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin


class CalendarEvent(TimestampMixin, Base):
    """A corporate event projected onto a calendar for date-range queries."""

    __tablename__ = "calendar_events"

    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    entity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entities.entity_id"), index=True
    )
    security_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("securities.security_id"), index=True
    )

    # Event details
    event_type: Mapped[str] = mapped_column(String(40), nullable=False)
    event_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    event_description: Mapped[str | None] = mapped_column(Text)

    # Linked records (nullable FKs — at most one set)
    corporate_action_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("corporate_actions.action_id")
    )
    # deal_id and ipo_id will be plain UUIDs until Part 3 creates those tables
    deal_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    ipo_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))

    __table_args__ = (
        Index("idx_calendar_date_type", "event_date", "event_type"),
        Index("idx_calendar_entity_date", "entity_id", "event_date"),
    )
