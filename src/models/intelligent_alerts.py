"""Pillar 3 Phase 4C: Consolidated alerts and earnings surprise intelligence models."""

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class ConsolidatedAlert(Base):
    """A deduplicated, priority-ranked alert for an entity."""

    __tablename__ = "consolidated_alerts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entities.entity_id"), nullable=False, index=True
    )
    alert_priority: Mapped[int | None] = mapped_column(Integer)
    alert_categories: Mapped[dict | None] = mapped_column(JSONB)  # [str] list of alert category tags
    primary_headline: Mapped[str | None] = mapped_column(String(500))
    primary_type: Mapped[str | None] = mapped_column(String(30))
    source_alert_ids: Mapped[dict | None] = mapped_column(JSONB)  # [uuid] IDs of original alerts consolidated here
    secondary_alerts: Mapped[dict | None] = mapped_column(JSONB)  # [{type, headline, priority}] lower-priority grouped alerts
    ai_synthesis: Mapped[str | None] = mapped_column(Text)
    recommended_action: Mapped[str | None] = mapped_column(String(20))
    related_catalysts: Mapped[dict | None] = mapped_column(JSONB)  # [{catalyst, expected_date, relevance}]
    is_acknowledged: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    acknowledged_by: Mapped[str | None] = mapped_column(String(100))
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint("entity_id", "primary_type", "created_at", name="uq_consolidated_alert_entity_type_ts"),
    )


class EarningsSurpriseIntelligence(Base):
    """Post-earnings analysis with surprise metrics and AI narrative."""

    __tablename__ = "earnings_surprise_intelligence"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entities.entity_id"), nullable=False, index=True
    )
    report_date: Mapped[date] = mapped_column(Date, nullable=False)
    fiscal_period: Mapped[str | None] = mapped_column(String(20))
    eps_consensus: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    eps_actual: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    eps_surprise_pct: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    revenue_consensus: Mapped[Decimal | None] = mapped_column(Numeric(15, 2))
    revenue_actual: Mapped[Decimal | None] = mapped_column(Numeric(15, 2))
    revenue_surprise_pct: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    margin_analysis: Mapped[dict | None] = mapped_column(JSONB)  # {gross_margin, operating_margin, yoy_change, ...}
    guidance_implications: Mapped[dict | None] = mapped_column(JSONB)  # {raised, lowered, maintained, detail}
    stock_reaction: Mapped[dict | None] = mapped_column(JSONB)  # {price_change_pct, volume_vs_avg, after_hours_move}
    ai_narrative: Mapped[str | None] = mapped_column(Text)
    key_takeaways: Mapped[dict | None] = mapped_column(JSONB)  # [str] bullet-point key takeaways
    revision_implications: Mapped[dict | None] = mapped_column(JSONB)  # {eps_revision_direction, target_price_impact, ...}
    recommendation: Mapped[str | None] = mapped_column(String(30))
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now()
    )
