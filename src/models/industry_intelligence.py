"""Industry intelligence models (Pillar 3 Phase 3A – Part 1)."""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import Date, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin


class IndustryProfile(TimestampMixin, Base):
    """Aggregate industry-level profile keyed by GICS code and date."""

    __tablename__ = "industry_profiles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    gics_code: Mapped[str] = mapped_column(String(8), nullable=False, index=True)
    gics_level: Mapped[str] = mapped_column(String(20), nullable=False)
    gics_name: Mapped[str] = mapped_column(String(200), nullable=False)
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False)

    # Size metrics
    company_count: Mapped[int | None] = mapped_column(Integer)
    total_market_cap: Mapped[Decimal | None] = mapped_column(Numeric(20, 2))
    median_market_cap: Mapped[Decimal | None] = mapped_column(Numeric(20, 2))

    # Growth
    revenue_growth_3y_cagr: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    revenue_growth_5y_cagr: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    revenue_dispersion: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))

    # Profitability
    median_gross_margin: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    median_operating_margin: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    median_capex_to_revenue: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    median_rd_to_revenue: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))

    # Returns
    median_roic: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    median_wacc: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    roic_wacc_spread: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    roic_dispersion: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))

    # Cycle
    capital_cycle_indicator: Mapped[str | None] = mapped_column(String(20))

    __table_args__ = (
        {"comment": "Aggregate industry profile by GICS code"},
    )


class IndustryCyclePosition(TimestampMixin, Base):
    """Industry cycle position assessment."""

    __tablename__ = "industry_cycle_positions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    gics_code: Mapped[str] = mapped_column(String(8), nullable=False, index=True)
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False)

    # Cycle indicators
    revenue_growth_acceleration: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    capacity_utilization_proxy: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    inventory_dynamics: Mapped[str | None] = mapped_column(String(20))
    inventory_to_sales_trend: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    margin_cycle_direction: Mapped[str | None] = mapped_column(String(20))
    operating_margin_momentum: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))

    # Position
    cycle_position: Mapped[str] = mapped_column(String(15), nullable=False)
    cycle_confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    prior_cycle_position: Mapped[str | None] = mapped_column(String(15))
    cycle_duration_quarters: Mapped[int | None] = mapped_column(Integer)

    __table_args__ = (
        {"comment": "Industry cycle position assessment"},
    )


class IndustryCompetitiveStructure(TimestampMixin, Base):
    """Industry competitive structure and concentration metrics."""

    __tablename__ = "industry_competitive_structures"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    gics_code: Mapped[str] = mapped_column(String(8), nullable=False, index=True)
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False)

    # Concentration
    hhi_index: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    hhi_classification: Mapped[str | None] = mapped_column(String(20))
    top3_market_share: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    top5_market_share: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    top10_market_share: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))

    # Consolidation
    consolidation_trend: Mapped[str | None] = mapped_column(String(20))
    consolidation_5y_delta: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))

    # Barriers & pricing
    barrier_to_entry: Mapped[str | None] = mapped_column(String(10))
    barrier_factors: Mapped[dict | None] = mapped_column(JSONB)
    pricing_power: Mapped[str | None] = mapped_column(String(10))
    pricing_power_evidence: Mapped[dict | None] = mapped_column(JSONB)

    # Dynamics
    competitive_dynamics: Mapped[str | None] = mapped_column(String(30))
    market_share_data: Mapped[dict | None] = mapped_column(JSONB)

    __table_args__ = (
        {"comment": "Industry competitive structure metrics"},
    )
