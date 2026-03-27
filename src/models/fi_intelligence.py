"""Pillar 3 Phase 3C: FI intelligence models."""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin


class FIMarketBriefing(TimestampMixin, Base):
    """Daily fixed-income market briefing with credit regime and curve data."""

    __tablename__ = "fi_market_briefings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    briefing_date: Mapped[date] = mapped_column(Date, nullable=False)
    briefing_type: Mapped[str | None] = mapped_column(String(20))
    ig_oas_bps: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    hy_oas_bps: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    ig_oas_1w_change: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    hy_oas_1w_change: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    credit_regime: Mapped[str | None] = mapped_column(String(15))
    spread_2s10s_bps: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    spread_3m10y_bps: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    curve_shape: Mapped[str | None] = mapped_column(String(15))
    fallen_angels_this_period: Mapped[dict | None] = mapped_column(JSONB)
    rising_stars_this_period: Mapped[dict | None] = mapped_column(JSONB)
    narrative: Mapped[str | None] = mapped_column(Text)
    ai_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class NewIssuanceEvent(TimestampMixin, Base):
    """New bond issuance event with pricing and demand details."""

    __tablename__ = "new_issuance_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    entity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entities.entity_id"),
        nullable=True, index=True,
    )
    issue_date: Mapped[date] = mapped_column(Date, nullable=False)
    coupon_rate: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    maturity_date: Mapped[date | None] = mapped_column(Date)
    size_mm: Mapped[Decimal | None] = mapped_column(Numeric(15, 2))
    spread_at_issue_bps: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    initial_talk_bps: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    rating: Mapped[str | None] = mapped_column(String(10))
    use_of_proceeds: Mapped[str | None] = mapped_column(String(30))
    oversubscribed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(500))


class CrossAssetSignal(TimestampMixin, Base):
    """Cross-asset divergence signal between equity and credit."""

    __tablename__ = "cross_asset_signals"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entities.entity_id"),
        nullable=False, index=True,
    )
    signal_date: Mapped[date] = mapped_column(Date, nullable=False)
    signal_type: Mapped[str | None] = mapped_column(String(30))
    equity_return_pct: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    spread_change_bps: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    severity: Mapped[str | None] = mapped_column(String(10))
    narrative: Mapped[str | None] = mapped_column(Text)
    ai_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
