"""Pillar 4 Phase 3: Portfolio risk models — VaR, concentration, factors, stress."""

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class PortfolioVarSnapshot(Base):
    """Daily portfolio VaR calculation snapshot."""

    __tablename__ = "portfolio_var_snapshots"
    __table_args__ = (
        UniqueConstraint("portfolio_id", "snapshot_date", name="uq_var_portfolio_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # P4-M-009: cascade-delete with parent portfolio so ``session.delete
    # (portfolio)`` doesn't fail with a bare FK violation against risk
    # history tables.
    portfolio_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("portfolios.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)
    var_1d_95: Mapped[Decimal | None] = mapped_column(Numeric(15, 4))
    var_1d_99: Mapped[Decimal | None] = mapped_column(Numeric(15, 4))
    var_10d_95: Mapped[Decimal | None] = mapped_column(Numeric(15, 4))
    var_10d_99: Mapped[Decimal | None] = mapped_column(Numeric(15, 4))
    undiversified_var: Mapped[Decimal | None] = mapped_column(Numeric(15, 4))
    diversification_ratio: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    marginal_var: Mapped[dict | None] = mapped_column(JSONB)
    component_var: Mapped[dict | None] = mapped_column(JSONB)
    incremental_var: Mapped[dict | None] = mapped_column(JSONB)
    portfolio_nav: Mapped[Decimal | None] = mapped_column(Numeric(20, 2))
    method: Mapped[str | None] = mapped_column(String(20), server_default="HISTORICAL")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ConcentrationAnalysis(Base):
    """Portfolio concentration metrics snapshot."""

    __tablename__ = "concentration_analyses"
    __table_args__ = (
        UniqueConstraint("portfolio_id", "snapshot_date", name="uq_conc_portfolio_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # P4-M-009: cascade-delete with parent portfolio so ``session.delete
    # (portfolio)`` doesn't fail with a bare FK violation against risk
    # history tables.
    portfolio_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("portfolios.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)
    hhi_position: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    hhi_sector: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    hhi_industry: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    largest_position_weight: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    top_5_weight: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    top_10_weight: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    effective_num_positions: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    concentration_classification: Mapped[str | None] = mapped_column(String(15))
    sector_detail: Mapped[dict | None] = mapped_column(JSONB)
    industry_detail: Mapped[dict | None] = mapped_column(JSONB)
    issuer_detail: Mapped[dict | None] = mapped_column(JSONB)
    geographic_detail: Mapped[dict | None] = mapped_column(JSONB)
    flags: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class FactorExposureSnapshot(Base):
    """Portfolio factor exposure snapshot."""

    __tablename__ = "factor_exposure_snapshots"
    __table_args__ = (
        UniqueConstraint("portfolio_id", "snapshot_date", name="uq_factor_portfolio_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # P4-M-009: cascade-delete with parent portfolio so ``session.delete
    # (portfolio)`` doesn't fail with a bare FK violation against risk
    # history tables.
    portfolio_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("portfolios.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)
    value_exposure: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    growth_exposure: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    momentum_exposure: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    quality_exposure: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    size_exposure: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    low_vol_exposure: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    benchmark_value: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    benchmark_growth: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    benchmark_momentum: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    benchmark_quality: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    benchmark_size: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    benchmark_low_vol: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    active_exposures: Mapped[dict | None] = mapped_column(JSONB)
    factor_contributions: Mapped[dict | None] = mapped_column(JSONB)
    unintended_flags: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class PortfolioStressTestResult(Base):
    """Portfolio-level stress test scenario result."""

    __tablename__ = "portfolio_stress_test_results"
    __table_args__ = (
        UniqueConstraint("portfolio_id", "snapshot_date", "scenario_name", name="uq_pstress_portfolio_date_scenario"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # P4-M-009: cascade-delete with parent portfolio so ``session.delete
    # (portfolio)`` doesn't fail with a bare FK violation against risk
    # history tables.
    portfolio_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("portfolios.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)
    scenario_name: Mapped[str] = mapped_column(String(50), nullable=False)
    scenario_type: Mapped[str] = mapped_column(String(15), nullable=False)
    total_pnl_dollar: Mapped[Decimal | None] = mapped_column(Numeric(20, 2))
    total_pnl_percent: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))
    max_drawdown_pct: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))
    recovery_time_months: Mapped[Decimal | None] = mapped_column(Numeric(5, 1))
    per_position_pnl: Mapped[dict | None] = mapped_column(JSONB)
    worst_positions: Mapped[dict | None] = mapped_column(JSONB)
    scenario_params: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
