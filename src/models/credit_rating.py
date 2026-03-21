"""Pillar 1 Supplement: Credit Rating History models (RATC/RATD)."""

import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin


class CreditRatingEvent(TimestampMixin, Base):
    """A single credit rating action (upgrade, downgrade, affirmation, etc.)."""

    __tablename__ = "credit_rating_events"

    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entities.entity_id"), nullable=False, index=True
    )

    # Rating details
    agency: Mapped[str] = mapped_column(String(10), nullable=False)
    rating_type: Mapped[str | None] = mapped_column(String(20))
    new_rating: Mapped[str | None] = mapped_column(String(10))
    old_rating: Mapped[str | None] = mapped_column(String(10))
    direction: Mapped[str | None] = mapped_column(String(15))
    outlook: Mapped[str | None] = mapped_column(String(15))

    # Timing
    event_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    effective_date: Mapped[date | None] = mapped_column(Date)

    # Source
    source_type: Mapped[str | None] = mapped_column(String(30))
    source_filing_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    source_url: Mapped[str | None] = mapped_column(String(500))

    __table_args__ = (
        Index("idx_rating_entity_date", "entity_id", "event_date"),
        Index("idx_rating_agency", "agency"),
    )
