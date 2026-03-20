"""Pillar 2: Screening & Universe Management models."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin


class SavedScreen(TimestampMixin, Base):
    """Persisted screen definitions (pre-built and user-saved).

    Stores the full filter/rank specification as JSONB so screens can
    be replayed without re-entering criteria.
    """

    __tablename__ = "saved_screens"

    screen_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    screen_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default="CUSTOM"
    )  # PREBUILT, CUSTOM, UNIVERSE
    is_prebuilt: Mapped[bool] = mapped_column(Boolean, default=False)
    definition: Mapped[dict] = mapped_column(JSONB, nullable=False)
    universe: Mapped[str] = mapped_column(String(30), default="ALL")
    created_by: Mapped[str | None] = mapped_column(String(100))
    tags: Mapped[dict | None] = mapped_column(JSONB)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    result_count: Mapped[int | None] = mapped_column(Integer)

    __table_args__ = (
        Index("idx_saved_screens_type", "screen_type"),
        Index("idx_saved_screens_prebuilt", "is_prebuilt"),
    )
