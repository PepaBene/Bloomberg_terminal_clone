"""Competitive intelligence models (Pillar 3 Phase 3A – Part 1)."""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import Boolean, Date, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin


class MoatAssessment(TimestampMixin, Base):
    """Competitive moat width, stability, and source assessment."""

    __tablename__ = "moat_assessments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("entities.entity_id"),
        nullable=False,
        index=True,
    )
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False)

    # ROIC durability
    roic_above_wacc_years: Mapped[int | None] = mapped_column(Integer)
    roic_consistency_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    gross_margin_stability: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    gross_margin_10y_std: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))

    # Market position
    market_share_trend: Mapped[str | None] = mapped_column(String(15))
    market_share_5y_delta: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    customer_retention_proxy: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))

    # Moat classification
    moat_width: Mapped[str] = mapped_column(String(6), nullable=False)
    moat_stability: Mapped[str | None] = mapped_column(String(10))
    moat_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))

    # Source scores
    cost_advantage_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    network_effects_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    switching_costs_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    intangible_assets_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    efficient_scale_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    dominant_moat_source: Mapped[str | None] = mapped_column(String(30))
    moat_evidence: Mapped[dict | None] = mapped_column(JSONB)

    # AI
    ai_summary: Mapped[str | None] = mapped_column(Text)
    ai_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    __table_args__ = (
        {"comment": "Competitive moat assessment per entity"},
    )


class MoatHistory(TimestampMixin, Base):
    """Historical moat metrics for trend analysis."""

    __tablename__ = "moat_history"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("entities.entity_id"),
        nullable=False,
        index=True,
    )
    period_end_date: Mapped[date] = mapped_column(Date, nullable=False)

    # Snapshot
    moat_width: Mapped[str | None] = mapped_column(String(6))
    moat_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    roic: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    wacc: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    roic_wacc_spread: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    gross_margin: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    market_share_est: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))

    __table_args__ = (
        {"comment": "Historical moat metrics for trend analysis"},
    )


class ConcentrationRiskAssessment(TimestampMixin, Base):
    """Customer, supplier, and geographic concentration risk assessment."""

    __tablename__ = "concentration_risk_assessments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("entities.entity_id"),
        nullable=False,
        index=True,
    )
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False)

    # Customer concentration
    customer_top1_pct: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    customer_top5_pct: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    customer_top10_pct: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    customer_concentration_risk: Mapped[str | None] = mapped_column(String(15))
    customer_details: Mapped[dict | None] = mapped_column(JSONB)

    # Supplier concentration
    supplier_single_source_count: Mapped[int | None] = mapped_column(Integer)
    supplier_critical_count: Mapped[int | None] = mapped_column(Integer)
    supplier_geographic_concentration: Mapped[dict | None] = mapped_column(JSONB)
    supplier_concentration_risk: Mapped[str | None] = mapped_column(String(15))
    supplier_details: Mapped[dict | None] = mapped_column(JSONB)

    # Geographic concentration
    geographic_revenue_breakdown: Mapped[dict | None] = mapped_column(JSONB)
    geographic_top1_pct: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    geographic_hhi: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    fx_exposure_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    geographic_concentration_risk: Mapped[str | None] = mapped_column(String(15))

    # Overall
    overall_concentration_risk: Mapped[str | None] = mapped_column(String(15))
    overall_risk_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))

    __table_args__ = (
        {"comment": "Customer, supplier, and geographic concentration risk"},
    )


class CompetitiveLandscape(TimestampMixin, Base):
    """Entity competitive positioning within its industry peer group."""

    __tablename__ = "competitive_landscapes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("entities.entity_id"),
        nullable=False,
        index=True,
    )
    gics_code: Mapped[str] = mapped_column(String(8), nullable=False)
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False)

    # Peer comparison
    peer_group: Mapped[dict | None] = mapped_column(JSONB)
    market_share_est_pct: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    market_share_rank: Mapped[int | None] = mapped_column(Integer)
    revenue_growth_vs_peers: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    margin_vs_peers: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    roic_vs_peers: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    valuation_vs_peers: Mapped[dict | None] = mapped_column(JSONB)

    # Competitive position
    share_gainer: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    value_chain_position: Mapped[str | None] = mapped_column(String(20))
    competitive_advantages: Mapped[dict | None] = mapped_column(JSONB)
    competitive_threats: Mapped[dict | None] = mapped_column(JSONB)

    __table_args__ = (
        {"comment": "Entity competitive positioning within peer group"},
    )
