"""Pillar 2: Risk Analytics models (Spec §7).

Stores VaR results, stress-test outcomes, and factor risk exposures
produced by the E5 Risk Analytics Engine.
"""

import uuid
from datetime import date

from sqlalchemy import Boolean, Date, ForeignKey, Index, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin


class VaRResult(TimestampMixin, Base):
    """Value at Risk computation results."""

    __tablename__ = "var_results"

    var_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    security_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("securities.security_id"), nullable=False, index=True
    )
    calculation_date: Mapped[date] = mapped_column(Date, nullable=False)
    method: Mapped[str] = mapped_column(String(20), nullable=False)
    confidence_level: Mapped[float] = mapped_column(Numeric(4, 2), nullable=False)
    holding_period_days: Mapped[int] = mapped_column(Integer, nullable=False)
    var_value: Mapped[float | None] = mapped_column(Numeric(18, 6))
    var_dollar: Mapped[float | None] = mapped_column(Numeric(20, 2))
    expected_shortfall: Mapped[float | None] = mapped_column(Numeric(18, 6))
    lookback_days: Mapped[int] = mapped_column(Integer, nullable=False, default=252)
    annualized_volatility: Mapped[float | None] = mapped_column(Numeric(10, 6))
    daily_mean_return: Mapped[float | None] = mapped_column(Numeric(10, 8))
    daily_std_return: Mapped[float | None] = mapped_column(Numeric(10, 8))
    skewness: Mapped[float | None] = mapped_column(Numeric(8, 4))
    kurtosis: Mapped[float | None] = mapped_column(Numeric(8, 4))
    data_quality: Mapped[str] = mapped_column(String(20), nullable=False, default="COMPLETE")
    inputs: Mapped[dict | None] = mapped_column(JSONB)

    __table_args__ = (
        Index(
            "idx_var_security_date_method",
            "security_id", "calculation_date", "method", "confidence_level",
        ),
    )


class StressTestResult(TimestampMixin, Base):
    """Stress testing scenario results."""

    __tablename__ = "stress_test_results"

    stress_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    security_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("securities.security_id"), nullable=False, index=True
    )
    calculation_date: Mapped[date] = mapped_column(Date, nullable=False)
    scenario_type: Mapped[str] = mapped_column(String(20), nullable=False)
    scenario_name: Mapped[str] = mapped_column(String(100), nullable=False)
    scenario_params: Mapped[dict] = mapped_column(JSONB, nullable=False)
    pnl_percent: Mapped[float | None] = mapped_column(Numeric(10, 6))
    max_drawdown: Mapped[float | None] = mapped_column(Numeric(10, 6))
    recovery_days: Mapped[int | None] = mapped_column(Integer)
    worst_day: Mapped[float | None] = mapped_column(Numeric(10, 6))
    best_day: Mapped[float | None] = mapped_column(Numeric(10, 6))
    data_quality: Mapped[str] = mapped_column(String(20), nullable=False, default="COMPLETE")

    __table_args__ = (
        Index("idx_stress_security_scenario", "security_id", "scenario_name", "calculation_date"),
    )


class FactorExposure(TimestampMixin, Base):
    """Style-factor risk exposures (Z-scores)."""

    __tablename__ = "factor_exposures"

    exposure_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    security_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("securities.security_id"), nullable=False, index=True
    )
    calculation_date: Mapped[date] = mapped_column(Date, nullable=False)
    factor_name: Mapped[str] = mapped_column(String(30), nullable=False)
    z_score: Mapped[float | None] = mapped_column(Numeric(8, 4))
    raw_value: Mapped[float | None] = mapped_column(Numeric(20, 6))
    percentile_rank: Mapped[float | None] = mapped_column(Numeric(6, 2))
    data_quality: Mapped[str] = mapped_column(String(20), nullable=False, default="COMPLETE")

    __table_args__ = (
        Index("idx_factor_security_date", "security_id", "calculation_date"),
        Index("idx_factor_name_date", "factor_name", "calculation_date"),
    )
