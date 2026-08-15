"""Layer 2 (AI_THREE_LAYER_REBUILD_PLAN.md §4.7 Pillar-3 follow-through)
output storage for the two rows in §4.7's table that had real structured
data (``CommodityPrice``/``CommodityInventory``, ``InsiderSignal``/
``CongressionalTrade``) but no narrative layer over it: "Commodity news/
supply-demand narrative to complement FRED prices" and "Narrative around
Form 4 / congressional disclosures; corroborating news."

One row per (subject, as_of_date), same compute-on-miss shape as
``src/models/interpretation.py`` -- simpler here since there's no
analytics-version freshness concept for either subject: a row for
today's date either exists (cache hit) or doesn't (compute fresh).
"""
import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class CommodityNarrative(Base):
    """AI narrative over one commodity's recent price action, inventory
    level, and any corroborating COMMODITY-tagged news, for one date."""

    __tablename__ = "commodity_narratives"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # Not a FK -- CommodityPrice/CommodityInventory already reference
    # commodity_code by plain string convention, not a constrained FK.
    commodity_code: Mapped[str] = mapped_column(String(20), nullable=False)
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False)

    narrative: Mapped[str] = mapped_column(Text, nullable=False)
    price_summary: Mapped[dict | None] = mapped_column(JSONB)
    news_article_ids: Mapped[list | None] = mapped_column(JSONB)

    model: Mapped[str | None] = mapped_column(String(64))
    prompt_id: Mapped[str | None] = mapped_column(String(64))
    prompt_version: Mapped[int | None] = mapped_column(Integer)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    __table_args__ = (
        Index(
            "idx_commodity_narrative_lookup", "commodity_code", "as_of_date", unique=True,
        ),
    )


class InsiderNarrative(Base):
    """AI narrative over one entity's recent Form 4 insider signals and
    congressional STOCK Act disclosures, for one date."""

    __tablename__ = "insider_narratives"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entities.entity_id"), nullable=False,
    )
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False)

    narrative: Mapped[str] = mapped_column(Text, nullable=False)
    signal_summary: Mapped[dict | None] = mapped_column(JSONB)
    congressional_summary: Mapped[dict | None] = mapped_column(JSONB)

    model: Mapped[str | None] = mapped_column(String(64))
    prompt_id: Mapped[str | None] = mapped_column(String(64))
    prompt_version: Mapped[int | None] = mapped_column(Integer)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    __table_args__ = (
        Index(
            "idx_insider_narrative_lookup", "entity_id", "as_of_date", unique=True,
        ),
    )
