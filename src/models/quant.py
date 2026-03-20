"""Pillar 2: Quantitative & Statistical models (Spec §9).

Stores regression results, correlation analyses, and time-series test
outcomes produced by the E7 Quantitative Engine.
"""

import uuid
from datetime import date

from sqlalchemy import Boolean, Date, ForeignKey, Index, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin


class RegressionResult(TimestampMixin, Base):
    """OLS / robust regression results."""

    __tablename__ = "regression_results"

    regression_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    security_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("securities.security_id"), index=True
    )
    calculation_date: Mapped[date] = mapped_column(Date, nullable=False)
    method: Mapped[str] = mapped_column(String(20), nullable=False)
    dependent_var: Mapped[str] = mapped_column(String(100), nullable=False)
    independent_vars: Mapped[dict] = mapped_column(JSONB, nullable=False)
    coefficients: Mapped[dict] = mapped_column(JSONB, nullable=False)
    std_errors: Mapped[dict | None] = mapped_column(JSONB)
    r_squared: Mapped[float | None] = mapped_column(Numeric(8, 6))
    adj_r_squared: Mapped[float | None] = mapped_column(Numeric(8, 6))
    f_statistic: Mapped[float | None] = mapped_column(Numeric(12, 4))
    f_p_value: Mapped[float | None] = mapped_column(Numeric(10, 8))
    n_observations: Mapped[int] = mapped_column(Integer, nullable=False)
    period_start: Mapped[date | None] = mapped_column(Date)
    period_end: Mapped[date | None] = mapped_column(Date)
    residuals_summary: Mapped[dict | None] = mapped_column(JSONB)
    confidence_intervals: Mapped[dict | None] = mapped_column(JSONB)
    data_quality: Mapped[str] = mapped_column(String(20), nullable=False, default="COMPLETE")

    __table_args__ = (
        Index("idx_reg_security_dep_date", "security_id", "dependent_var", "calculation_date"),
    )


class CorrelationResult(TimestampMixin, Base):
    """Pairwise correlation results."""

    __tablename__ = "correlation_results"

    correlation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    calculation_date: Mapped[date] = mapped_column(Date, nullable=False)
    method: Mapped[str] = mapped_column(String(20), nullable=False)
    series_x_id: Mapped[str] = mapped_column(String(100), nullable=False)
    series_y_id: Mapped[str] = mapped_column(String(100), nullable=False)
    series_x_label: Mapped[str | None] = mapped_column(String(100))
    series_y_label: Mapped[str | None] = mapped_column(String(100))
    coefficient: Mapped[float | None] = mapped_column(Numeric(8, 6))
    p_value: Mapped[float | None] = mapped_column(Numeric(10, 8))
    n_observations: Mapped[int] = mapped_column(Integer, nullable=False)
    period_start: Mapped[date | None] = mapped_column(Date)
    period_end: Mapped[date | None] = mapped_column(Date)
    data_quality: Mapped[str] = mapped_column(String(20), nullable=False, default="COMPLETE")

    __table_args__ = (
        Index("idx_corr_xy_date", "series_x_id", "series_y_id", "calculation_date"),
    )


class TimeSeriesTestResult(TimestampMixin, Base):
    """Stationarity / cointegration / Granger test results."""

    __tablename__ = "time_series_test_results"

    test_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    security_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("securities.security_id"), index=True
    )
    calculation_date: Mapped[date] = mapped_column(Date, nullable=False)
    test_type: Mapped[str] = mapped_column(String(30), nullable=False)
    series_name: Mapped[str] = mapped_column(String(100), nullable=False)
    test_statistic: Mapped[float | None] = mapped_column(Numeric(12, 6))
    p_value: Mapped[float | None] = mapped_column(Numeric(10, 8))
    critical_values: Mapped[dict | None] = mapped_column(JSONB)
    is_significant: Mapped[bool | None] = mapped_column(Boolean)
    lags_used: Mapped[int | None] = mapped_column(Integer)
    extra_params: Mapped[dict | None] = mapped_column(JSONB)
    data_quality: Mapped[str] = mapped_column(String(20), nullable=False, default="COMPLETE")

    __table_args__ = (
        Index("idx_ts_security_test_date", "security_id", "test_type", "calculation_date"),
    )
