"""Pydantic schemas for Pillar 4 Phase 2: Performance measurement endpoints."""

from datetime import date
from uuid import UUID

from pydantic import BaseModel


class PerformanceResponse(BaseModel):
    """Performance snapshot summary for a portfolio."""

    id: UUID
    portfolio_id: UUID
    period_type: str
    period_start: date
    period_end: date
    twr_return: float | None = None
    mwr_return: float | None = None
    benchmark_return: float | None = None
    active_return: float | None = None
    sharpe_ratio: float | None = None
    sortino_ratio: float | None = None
    information_ratio: float | None = None
    tracking_error: float | None = None
    max_drawdown: float | None = None
    calmar_ratio: float | None = None
    beta: float | None = None
    alpha: float | None = None
    volatility: float | None = None
    up_capture: float | None = None
    down_capture: float | None = None
    batting_average: float | None = None
    best_day: float | None = None
    worst_day: float | None = None
    positive_days: int | None = None
    negative_days: int | None = None

    model_config = {"from_attributes": True}


class ReturnSeriesEntry(BaseModel):
    """A single return data point."""

    date: date
    return_value: float
    cumulative_return: float


class ReturnSeriesResponse(BaseModel):
    """Time series of returns."""

    portfolio_id: UUID
    period: str
    entries: list[ReturnSeriesEntry]


class CalendarReturnEntry(BaseModel):
    """Calendar-year return entry."""

    year: int
    jan: float | None = None
    feb: float | None = None
    mar: float | None = None
    apr: float | None = None
    may: float | None = None
    jun: float | None = None
    jul: float | None = None
    aug: float | None = None
    sep: float | None = None
    oct: float | None = None
    nov: float | None = None
    dec: float | None = None
    ytd: float | None = None


class CalendarReturnResponse(BaseModel):
    """Calendar-year return grid."""

    portfolio_id: UUID
    years: list[CalendarReturnEntry]


class RollingReturnEntry(BaseModel):
    """Rolling return entry."""

    date: date
    rolling_1m: float | None = None
    rolling_3m: float | None = None
    rolling_6m: float | None = None
    rolling_1y: float | None = None
    rolling_3y: float | None = None


class RollingReturnResponse(BaseModel):
    """Rolling return series."""

    portfolio_id: UUID
    entries: list[RollingReturnEntry]


class BenchmarkComparisonResponse(BaseModel):
    """Portfolio vs benchmark comparison."""

    portfolio_id: UUID
    period: str
    portfolio_return: float
    benchmark_return: float
    active_return: float
    tracking_error: float | None = None
    information_ratio: float | None = None


class RiskMetricsResponse(BaseModel):
    """Comprehensive risk metrics."""

    portfolio_id: UUID
    period: str
    sharpe_ratio: float | None = None
    sortino_ratio: float | None = None
    information_ratio: float | None = None
    tracking_error: float | None = None
    beta: float | None = None
    alpha: float | None = None
    volatility: float | None = None
    max_drawdown: float | None = None
    calmar_ratio: float | None = None
    up_capture: float | None = None
    down_capture: float | None = None


class DrawdownResponse(BaseModel):
    """Drawdown analysis."""

    portfolio_id: UUID
    max_drawdown: float | None = None
    peak_date: date | None = None
    trough_date: date | None = None
    recovery_date: date | None = None
    duration_days: int | None = None


class PerformanceCompareEntry(BaseModel):
    """Single portfolio entry in a comparison."""

    portfolio_id: UUID
    portfolio_name: str | None = None
    twr_return: float | None = None
    sharpe_ratio: float | None = None
    max_drawdown: float | None = None
    volatility: float | None = None


class PerformanceCompareResponse(BaseModel):
    """Compare multiple portfolios."""

    period: str
    portfolios: list[PerformanceCompareEntry]
