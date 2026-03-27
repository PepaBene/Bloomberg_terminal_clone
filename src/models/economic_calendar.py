"""Pillar 3 Phase 2: Economic Calendar models."""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import Boolean, Date, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin


class EconomicRelease(TimestampMixin, Base):
    """Scheduled economic data releases with consensus, actuals, and impact analysis."""

    __tablename__ = "economic_releases"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # Release identification
    release_type: Mapped[str] = mapped_column(
        String(40), nullable=False
    )  # CPI, GDP, NFP, FOMC, TREASURY_AUCTION etc
    release_category: Mapped[str] = mapped_column(
        String(30), nullable=False
    )  # ECONOMIC_DATA, CENTRAL_BANK, TREASURY, REGULATORY
    release_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    release_time: Mapped[str | None] = mapped_column(String(10))  # "08:30 ET"
    country_code: Mapped[str | None] = mapped_column(String(3), default="US")
    period_label: Mapped[str | None] = mapped_column(
        String(30)
    )  # "Q4 2025", "Dec 2025"

    # Values
    consensus_value: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))
    prior_value: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))
    actual_value: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))
    surprise_value: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))
    surprise_magnitude: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))

    # Impact analysis
    sector_sensitivity: Mapped[dict | None] = mapped_column(
        JSONB
    )  # {sector: sensitivity}
    historical_reactions: Mapped[dict | None] = mapped_column(
        JSONB
    )  # {sector: avg_reaction}
    affected_entity_ids: Mapped[list | None] = mapped_column(
        JSONB
    )  # [entity_ids]

    # AI-generated insights
    ai_summary: Mapped[str | None] = mapped_column(Text)
    ai_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Metadata
    importance: Mapped[str | None] = mapped_column(String(10))  # HIGH/MEDIUM/LOW
    source: Mapped[str | None] = mapped_column(String(30))

    __table_args__ = (
        Index("idx_econ_release_date_type", "release_date", "release_type"),
        Index("idx_econ_category_date", "release_category", "release_date"),
    )
