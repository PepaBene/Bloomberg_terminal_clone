"""Company intelligence and primer models (Pillar 2 Supplement – Part 7)."""

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin


class CompanyBriefing(TimestampMixin, Base):
    """Cached AI-generated company intelligence briefing."""

    __tablename__ = "company_briefings"

    briefing_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entities.entity_id"),
        nullable=False, index=True,
    )
    briefing_type: Mapped[str] = mapped_column(String(20), nullable=False, default="DAILY")
    briefing_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="COMPLETED")
    summary_text: Mapped[str | None] = mapped_column(Text)
    key_signals: Mapped[dict | None] = mapped_column(JSONB)
    valuation_context: Mapped[dict | None] = mapped_column(JSONB)
    value_investing_lens: Mapped[dict | None] = mapped_column(JSONB)
    data_snapshot: Mapped[dict | None] = mapped_column(JSONB)
    ai_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index("idx_briefing_entity_type_date", "entity_id", "briefing_type", "briefing_date", unique=True),
    )


class CompanyPrimer(TimestampMixin, Base):
    """One-page company summary/primer."""

    __tablename__ = "company_primers"

    primer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entities.entity_id"),
        nullable=False, index=True,
    )
    generated_date: Mapped[date] = mapped_column(Date, nullable=False)
    business_description: Mapped[str | None] = mapped_column(Text)
    segments_breakdown: Mapped[dict | None] = mapped_column(JSONB)
    competitive_position: Mapped[str | None] = mapped_column(Text)
    financial_summary: Mapped[dict | None] = mapped_column(JSONB)
    valuation_summary: Mapped[dict | None] = mapped_column(JSONB)
    ownership_summary: Mapped[dict | None] = mapped_column(JSONB)
    key_risks: Mapped[dict | None] = mapped_column(JSONB)
    recent_developments: Mapped[dict | None] = mapped_column(JSONB)
    ai_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    __table_args__ = (
        Index("idx_primer_entity_date", "entity_id", "generated_date", unique=True),
    )


# ── Pillar 3 Phase 2: Deep Company Analysis ───────────────────────────


class BusinessModelAnalysis(TimestampMixin, Base):
    """Revenue quality, operating leverage, and competitive moat analysis."""

    __tablename__ = "business_model_analyses"

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

    # Revenue quality
    revenue_decomposition: Mapped[dict | None] = mapped_column(JSONB)
    recurring_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    deferred_revenue_trend: Mapped[str | None] = mapped_column(String(15))
    customer_concentration: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    diversification_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    cyclicality_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    revenue_per_employee: Mapped[Decimal | None] = mapped_column(Numeric(20, 2))
    unit_economics: Mapped[dict | None] = mapped_column(JSONB)

    # Operating leverage
    operating_leverage: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    incremental_margin: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    sga_scalability: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))

    # Competitive moat
    switching_cost_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    moat_type: Mapped[str | None] = mapped_column(String(30))
    disruption_vulnerability: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))

    # AI
    ai_summary: Mapped[str | None] = mapped_column(Text)
    ai_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    __table_args__ = (
        Index("idx_bma_entity_date", "entity_id", "as_of_date"),
    )


class CapitalAllocationAssessment(TimestampMixin, Base):
    """Capital allocation discipline: FCF conversion, ROIC, M&A, buybacks."""

    __tablename__ = "capital_allocation_assessments"

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

    # Cash flow conversion
    ebitda_to_fcf_conversion: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    maintenance_capex_pct: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    growth_capex_pct: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    working_capital_discipline: Mapped[dict | None] = mapped_column(
        JSONB
    )  # {ccc, dio, dso, dpo}

    # Returns
    roic_vs_wacc_spread: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    roic_vs_wacc_history: Mapped[dict | None] = mapped_column(JSONB)

    # Deployment
    ma_discipline: Mapped[dict | None] = mapped_column(JSONB)
    buyback_effectiveness: Mapped[dict | None] = mapped_column(JSONB)
    dividend_sustainability: Mapped[dict | None] = mapped_column(JSONB)

    # Overall
    overall_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))  # 0-100
    ai_summary: Mapped[str | None] = mapped_column(Text)
    ai_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    __table_args__ = (
        Index("idx_caa_entity_date", "entity_id", "as_of_date"),
    )


class BalanceSheetRiskAssessment(TimestampMixin, Base):
    """Leverage, liquidity, refinancing, and covenant risk assessment."""

    __tablename__ = "balance_sheet_risk_assessments"

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

    # Leverage
    net_debt_ebitda: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    net_debt_ebitda_trend: Mapped[str | None] = mapped_column(String(15))
    interest_coverage: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    interest_coverage_trend: Mapped[str | None] = mapped_column(String(15))

    # Liquidity
    liquidity_ratio: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    cash_burn_rate: Mapped[Decimal | None] = mapped_column(Numeric(20, 2))

    # Refinancing
    refinancing_risk_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    maturity_24mo_pct: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    coverage_trend: Mapped[str | None] = mapped_column(String(15))

    # Credit
    z_score: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    covenant_analysis: Mapped[dict | None] = mapped_column(JSONB)
    fi_profile: Mapped[dict | None] = mapped_column(JSONB)

    # AI
    ai_summary: Mapped[str | None] = mapped_column(Text)
    ai_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    __table_args__ = (
        Index("idx_bsra_entity_date", "entity_id", "as_of_date"),
    )


class ManagementQualityAssessment(TimestampMixin, Base):
    """Management execution quality, accounting quality, and governance scoring."""

    __tablename__ = "management_quality_assessments"

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

    # Execution quality
    guidance_accuracy_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    strategic_consistency_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    margin_stability_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    wc_management_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    execution_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))

    # Accounting quality
    beneish_m_score: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    accruals_quality: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    auditor_change_flag: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    restatement_flag: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )

    # Governance
    compensation_alignment: Mapped[dict | None] = mapped_column(JSONB)
    governance_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))

    # Overall
    overall_quality_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    red_flags: Mapped[dict | None] = mapped_column(JSONB)
    ai_summary: Mapped[str | None] = mapped_column(Text)
    ai_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    __table_args__ = (
        Index("idx_mqa_entity_date", "entity_id", "as_of_date"),
    )
