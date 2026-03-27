"""Pillar 4 Phase 1: Portfolio watchlist models for named entity lists."""

import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin


class PortfolioWatchlist(TimestampMixin, Base):
    """Named watchlist containing multiple entities."""

    __tablename__ = "portfolio_watchlists"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    alert_config: Mapped[dict | None] = mapped_column(JSONB)


class PortfolioWatchlistEntry(Base):
    """Individual entity within a portfolio watchlist."""

    __tablename__ = "portfolio_watchlist_entries"
    __table_args__ = (
        Index(
            "uq_pwl_entry_wl_entity",
            "watchlist_id", "entity_id",
            unique=True,
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    watchlist_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("portfolio_watchlists.id"),
        nullable=False, index=True,
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entities.entity_id"),
        nullable=False, index=True,
    )
    added_date: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
