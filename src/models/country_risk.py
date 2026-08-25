"""Country risk and geopolitical event models (Pillar 3 Phase 3B – Part 8)."""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import Boolean, Date, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin


class CountryProfile(TimestampMixin, Base):
    """Static country reference data with economic classification."""

    __tablename__ = "country_profiles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    country_code: Mapped[str] = mapped_column(String(3), nullable=False, unique=True)
    country_name: Mapped[str] = mapped_column(String(100), nullable=False)
    region: Mapped[str | None] = mapped_column(String(30))
    income_group: Mapped[str | None] = mapped_column(String(30))
    is_g20: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_eu: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    population: Mapped[Decimal | None] = mapped_column(Numeric(15, 0))
    gdp_usd: Mapped[Decimal | None] = mapped_column(Numeric(20, 2))


class CountryRiskScore(TimestampMixin, Base):
    """Composite country risk scoring across political, economic, and sanctions dimensions."""

    __tablename__ = "country_risk_scores"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    country_code: Mapped[str] = mapped_column(String(3), nullable=False, index=True)
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False)

    # Risk scores
    political_risk_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    economic_risk_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    sanctions_risk_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    composite_risk_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    risk_classification: Mapped[str | None] = mapped_column(String(15))
    risk_trend: Mapped[str | None] = mapped_column(String(15))

    # Component breakdowns
    political_components: Mapped[dict | None] = mapped_column(JSONB)
    economic_components: Mapped[dict | None] = mapped_column(JSONB)
    sanctions_components: Mapped[dict | None] = mapped_column(JSONB)

    __table_args__ = (
        {"comment": "Country risk scores with composite and component breakdowns"},
    )


class CompanyCountryExposure(TimestampMixin, Base):
    """Company-level geographic revenue/operations exposure by country."""

    __tablename__ = "company_country_exposures"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("entities.entity_id"),
        nullable=False,
    )
    country_code: Mapped[str] = mapped_column(String(3), nullable=False)
    exposure_type: Mapped[str | None] = mapped_column(String(20))
    exposure_pct: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    source: Mapped[str | None] = mapped_column(String(20))
    as_of_date: Mapped[date | None] = mapped_column(Date)


class GeopoliticalEvent(TimestampMixin, Base):
    """Tracked geopolitical events with sector and commodity impact assessment."""

    __tablename__ = "geopolitical_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    event_type: Mapped[str | None] = mapped_column(String(30))
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    # Layer 2 §4.1 (AI_THREE_LAYER_REBUILD_PLAN.md): a real column, not
    # parsed out of `description`'s "Source: {domain} — {url}" text --
    # lets gdelt_news_bridge.py dedup/link by URL instead of the
    # connector's own title-based de-dup (fragile: two distinct events
    # can legitimately share a headline).
    source_url: Mapped[str | None] = mapped_column(String(1000), unique=True)
    countries_involved: Mapped[dict | None] = mapped_column(JSONB)
    severity: Mapped[str | None] = mapped_column(String(10))
    status: Mapped[str | None] = mapped_column(String(20))
    start_date: Mapped[date | None] = mapped_column(Date)
    commodity_impact: Mapped[dict | None] = mapped_column(JSONB)
    sector_impact: Mapped[dict | None] = mapped_column(JSONB)
    affected_entity_ids: Mapped[dict | None] = mapped_column(JSONB)
