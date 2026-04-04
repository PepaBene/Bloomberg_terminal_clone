"""Pillar 2: Analytics Engine models (Spec Sections 3-4, 11, 15).

Stores computed ratios, DuPont decompositions, valuation multiples,
WACC results, and calculation lineage for audit/reproducibility.
"""

import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin


class AnalyticsResult(TimestampMixin, Base):
    """Computed ratio/metric results.

    One row per security × metric × period.  The primary storage for
    all batch-computed analytics.  The ``inputs`` JSONB column carries
    the full lineage so every derived number is auditable to its source.
    """

    __tablename__ = "analytics_results"

    result_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    security_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("securities.security_id"), nullable=False, index=True
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entities.entity_id"), nullable=False, index=True
    )
    engine_id: Mapped[str] = mapped_column(String(10), nullable=False)
    metric_name: Mapped[str] = mapped_column(String(100), nullable=False)
    metric_category: Mapped[str] = mapped_column(String(30), nullable=False)
    value: Mapped[float | None] = mapped_column(Numeric(20, 6))
    unit: Mapped[str] = mapped_column(String(20), nullable=False, default="RATIO")
    period: Mapped[str] = mapped_column(String(20), nullable=False)
    period_end_date: Mapped[date | None] = mapped_column(Date)
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False)
    data_quality: Mapped[str] = mapped_column(String(100), nullable=False, default="COMPLETE")
    inputs: Mapped[dict | None] = mapped_column(JSONB)
    calculation_version: Mapped[str] = mapped_column(String(10), nullable=False, default="1.0")

    __table_args__ = (
        Index("idx_ar_security_metric", "security_id", "metric_name", "period"),
        Index("idx_ar_entity_metric", "entity_id", "metric_name"),
        Index("idx_ar_category_date", "metric_category", "as_of_date"),
        CheckConstraint("metric_category = UPPER(metric_category)", name="ck_ar_metric_category_upper"),
    )


class DuPontDecomposition(TimestampMixin, Base):
    """DuPont analysis results (3-factor and 5-factor)."""

    __tablename__ = "dupont_decompositions"

    decomposition_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entities.entity_id"), nullable=False, index=True
    )
    security_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("securities.security_id"), index=True
    )
    period: Mapped[str] = mapped_column(String(20), nullable=False)
    period_end_date: Mapped[date | None] = mapped_column(Date)
    model_type: Mapped[str] = mapped_column(String(20), nullable=False)

    # 3-factor components
    roe: Mapped[float | None] = mapped_column(Numeric(12, 6))
    net_profit_margin: Mapped[float | None] = mapped_column(Numeric(12, 6))
    asset_turnover: Mapped[float | None] = mapped_column(Numeric(12, 6))
    equity_multiplier: Mapped[float | None] = mapped_column(Numeric(12, 6))

    # 5-factor additional components
    tax_burden: Mapped[float | None] = mapped_column(Numeric(12, 6))
    interest_burden: Mapped[float | None] = mapped_column(Numeric(12, 6))
    operating_margin: Mapped[float | None] = mapped_column(Numeric(12, 6))

    data_quality: Mapped[str] = mapped_column(String(100), nullable=False, default="COMPLETE")
    inputs: Mapped[dict | None] = mapped_column(JSONB)

    __table_args__ = (
        Index("idx_dupont_entity_period", "entity_id", "period"),
        Index("idx_dupont_security", "security_id"),
    )


class MultipleTimeSeries(Base):
    """Historical valuation multiple time series.

    Composite PK on (security_id, multiple_type, calculation_date) so
    we store one row per security per multiple per date.
    """

    __tablename__ = "multiple_time_series"

    security_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("securities.security_id"), primary_key=True
    )
    multiple_type: Mapped[str] = mapped_column(String(30), primary_key=True)
    calculation_date: Mapped[date] = mapped_column(Date, primary_key=True)

    value: Mapped[float | None] = mapped_column(Numeric(18, 6))
    numerator_value: Mapped[float | None] = mapped_column(Numeric(20, 2))
    denominator_value: Mapped[float | None] = mapped_column(Numeric(20, 2))
    is_forward: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    forward_period: Mapped[str | None] = mapped_column(String(10))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("idx_mts_security_type", "security_id", "multiple_type", "calculation_date"),
    )


class WACCResult(TimestampMixin, Base):
    """WACC calculation results with component breakdown."""

    __tablename__ = "wacc_results"

    wacc_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entities.entity_id"), nullable=False, index=True
    )
    security_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("securities.security_id"), index=True
    )
    calculation_date: Mapped[date] = mapped_column(Date, nullable=False)

    # CAPM + WACC components
    risk_free_rate: Mapped[float | None] = mapped_column(Numeric(8, 4))
    equity_risk_premium: Mapped[float | None] = mapped_column(Numeric(8, 4))
    beta: Mapped[float | None] = mapped_column(Numeric(6, 3))
    size_premium: Mapped[float | None] = mapped_column(Numeric(8, 4))
    country_premium: Mapped[float | None] = mapped_column(Numeric(8, 4))
    cost_of_equity: Mapped[float | None] = mapped_column(Numeric(8, 4))
    cost_of_debt_pretax: Mapped[float | None] = mapped_column(Numeric(8, 4))
    effective_tax_rate: Mapped[float | None] = mapped_column(Numeric(6, 4))
    cost_of_debt_aftertax: Mapped[float | None] = mapped_column(Numeric(8, 4))
    debt_weight: Mapped[float | None] = mapped_column(Numeric(6, 4))
    equity_weight: Mapped[float | None] = mapped_column(Numeric(6, 4))
    wacc: Mapped[float | None] = mapped_column(Numeric(8, 4))

    # Context
    market_cap: Mapped[float | None] = mapped_column(Numeric(20, 2))
    total_debt: Mapped[float | None] = mapped_column(Numeric(20, 2))
    assumptions: Mapped[dict | None] = mapped_column(JSONB)
    data_quality: Mapped[str] = mapped_column(String(100), nullable=False, default="COMPLETE")

    __table_args__ = (
        Index("idx_wacc_entity_date", "entity_id", "calculation_date"),
    )


class DCFResult(TimestampMixin, Base):
    """DCF valuation results (FCFF or FCFE)."""

    __tablename__ = "dcf_results"

    dcf_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entities.entity_id"), nullable=False, index=True
    )
    security_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("securities.security_id"), nullable=False, index=True
    )
    calculation_date: Mapped[date] = mapped_column(Date, nullable=False)
    method: Mapped[str] = mapped_column(String(10), nullable=False)  # FCFF or FCFE
    assumptions: Mapped[dict | None] = mapped_column(JSONB)

    # WACC / discount rate
    wacc_used: Mapped[float | None] = mapped_column(Numeric(8, 4))
    cost_of_equity: Mapped[float | None] = mapped_column(Numeric(8, 4))

    # Projections
    projected_cashflows: Mapped[dict | None] = mapped_column(JSONB)

    # Terminal value
    terminal_value: Mapped[float | None] = mapped_column(Numeric(20, 2))
    terminal_method: Mapped[str | None] = mapped_column(String(20))
    terminal_growth_rate: Mapped[float | None] = mapped_column(Numeric(6, 4))
    terminal_exit_multiple: Mapped[float | None] = mapped_column(Numeric(8, 2))
    pv_terminal: Mapped[float | None] = mapped_column(Numeric(20, 2))
    terminal_pct_of_ev: Mapped[float | None] = mapped_column(Numeric(6, 4))

    # Output
    pv_of_fcf: Mapped[float | None] = mapped_column(Numeric(20, 2))
    enterprise_value: Mapped[float | None] = mapped_column(Numeric(20, 2))
    net_debt: Mapped[float | None] = mapped_column(Numeric(20, 2))
    equity_value: Mapped[float | None] = mapped_column(Numeric(20, 2))
    shares_outstanding: Mapped[float | None] = mapped_column(Numeric(20, 2))
    implied_price: Mapped[float | None] = mapped_column(Numeric(18, 6))
    current_price: Mapped[float | None] = mapped_column(Numeric(18, 6))
    upside_downside_pct: Mapped[float | None] = mapped_column(Numeric(8, 4))

    # Sensitivity
    sensitivity_grid: Mapped[dict | None] = mapped_column(JSONB)

    data_quality: Mapped[str] = mapped_column(String(100), nullable=False, default="COMPLETE")
    currency: Mapped[str | None] = mapped_column(String(3))

    __table_args__ = (
        Index("idx_dcf_entity_date", "entity_id", "calculation_date"),
        Index("idx_dcf_security_date", "security_id", "calculation_date"),
    )


class CompsResult(TimestampMixin, Base):
    """Comparable company analysis results."""

    __tablename__ = "comps_results"

    comps_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    security_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("securities.security_id"), nullable=False, index=True
    )
    calculation_date: Mapped[date] = mapped_column(Date, nullable=False)
    peer_security_ids: Mapped[dict | None] = mapped_column(JSONB)
    peer_count: Mapped[int | None] = mapped_column(Integer)
    peer_selection_method: Mapped[str | None] = mapped_column(String(30))
    multiples_comparison: Mapped[dict | None] = mapped_column(JSONB)
    historical_avg_1y: Mapped[dict | None] = mapped_column(JSONB)
    historical_avg_3y: Mapped[dict | None] = mapped_column(JSONB)
    historical_avg_5y: Mapped[dict | None] = mapped_column(JSONB)
    primary_multiple: Mapped[str | None] = mapped_column(String(20))
    composite_implied_price: Mapped[float | None] = mapped_column(Numeric(18, 6))
    current_price: Mapped[float | None] = mapped_column(Numeric(18, 6))
    data_quality: Mapped[str] = mapped_column(String(100), nullable=False, default="COMPLETE")

    __table_args__ = (
        Index("idx_comps_security_date", "security_id", "calculation_date"),
    )


class CompositeScore(TimestampMixin, Base):
    """Composite quality/safety scores."""

    __tablename__ = "composite_scores"

    score_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    security_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("securities.security_id"), nullable=False, index=True
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entities.entity_id"), nullable=False, index=True
    )
    calculation_date: Mapped[date] = mapped_column(Date, nullable=False)
    score_type: Mapped[str] = mapped_column(String(30), nullable=False)
    score_value: Mapped[float | None] = mapped_column(Numeric(6, 2))
    classification: Mapped[str | None] = mapped_column(String(30))
    components: Mapped[dict | None] = mapped_column(JSONB)
    data_quality: Mapped[str] = mapped_column(String(100), nullable=False, default="COMPLETE")

    __table_args__ = (
        Index("idx_composite_security_type", "security_id", "score_type", "calculation_date"),
    )


class CalculationLineage(TimestampMixin, Base):
    """Audit trail for every derived number (Spec §15).

    Every computation writes a lineage record so that any metric can be
    traced back to its source Pillar 1 data points and the exact formula
    used.
    """

    __tablename__ = "calculation_lineage"

    lineage_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    security_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("securities.security_id"), nullable=False, index=True
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entities.entity_id"), nullable=False
    )
    engine_id: Mapped[str] = mapped_column(String(10), nullable=False)
    engine_version: Mapped[str] = mapped_column(String(20), nullable=False)
    output_metric: Mapped[str] = mapped_column(String(100), nullable=False)
    output_value: Mapped[float | None] = mapped_column(Numeric(20, 6))
    period: Mapped[str] = mapped_column(String(20), nullable=False)
    calculation_formula: Mapped[str | None] = mapped_column(Text)
    inputs: Mapped[dict] = mapped_column(JSONB, nullable=False)
    calculated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("idx_lineage_security_metric", "security_id", "output_metric", "period"),
        Index("idx_lineage_entity", "entity_id"),
        Index("idx_lineage_calculated_at", "calculated_at"),
    )
