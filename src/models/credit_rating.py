"""Pillar 1 Supplement: Credit Rating History models (RATC/RATD)."""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import Boolean, Date, ForeignKey, Index, Integer, Numeric, String, text
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

    # D11 FI Supplement: Numeric rating scale + crossover flags
    new_rating_numeric: Mapped[int | None] = mapped_column(Integer)
    old_rating_numeric: Mapped[int | None] = mapped_column(Integer)
    notches_changed: Mapped[int | None] = mapped_column(Integer)
    is_fallen_angel: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_rising_star: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    entity_stock_price_at_event: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    bond_spread_at_event: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    watch_status: Mapped[str | None] = mapped_column(String(20))

    __table_args__ = (
        Index("idx_rating_entity_date", "entity_id", "event_date"),
        Index("idx_rating_agency", "agency"),
    )


class CurrentCreditRating(TimestampMixin, Base):
    """Current credit rating snapshot per entity per agency (materialized view)."""

    __tablename__ = "current_credit_ratings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entities.entity_id"), nullable=False
    )
    agency: Mapped[str] = mapped_column(String(10), nullable=False)
    rating_type: Mapped[str | None] = mapped_column(String(20))
    current_rating: Mapped[str] = mapped_column(String(10), nullable=False)
    current_rating_numeric: Mapped[int | None] = mapped_column(Integer)
    outlook: Mapped[str | None] = mapped_column(String(15))
    watch_status: Mapped[str | None] = mapped_column(String(20))
    last_action_date: Mapped[date | None] = mapped_column(Date)
    last_action_type: Mapped[str | None] = mapped_column(String(15))
    is_investment_grade: Mapped[bool | None] = mapped_column(Boolean)

    __table_args__ = (
        # Partial unique index: one rating per (entity, agency, rating_type) when rating_type is set
        Index(
            "idx_current_rating_entity_agency_typed",
            "entity_id",
            "agency",
            "rating_type",
            unique=True,
            postgresql_where=text("rating_type IS NOT NULL"),
        ),
        # Separate unique index for NULL rating_type: one untyped rating per (entity, agency)
        Index(
            "idx_current_rating_entity_agency_untyped",
            "entity_id",
            "agency",
            unique=True,
            postgresql_where=text("rating_type IS NULL"),
        ),
    )
