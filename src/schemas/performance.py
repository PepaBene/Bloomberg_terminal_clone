"""Pydantic schemas for Pillar 4 Phase 2: Performance measurement endpoints."""

from datetime import date
from uuid import UUID

from pydantic import BaseModel, field_serializer

from src.schemas.common import round_or_none

# P4-M-005: return/ratio fields across this module are deliberately kept as
# ``float`` on the wire (Pydantic v2 serializes ``Decimal`` as a quoted
# string by default, which would break existing JSON number consumers).
# All fractional return/ratio fields (twr_return, sharpe_ratio, beta, ...)
# are rounded via ``field_serializer`` to 6 decimal places -- matching the
# meaningful precision of their source ``Numeric(12, 8)`` / ``Numeric(10,
# 6)`` DB columns -- so the wire value doesn't imply false floating-point
# precision.
_RATIO_FIELDS = (
    "twr_return", "mwr_return", "benchmark_return", "active_return",
    "sharpe_ratio", "sortino_ratio", "information_ratio", "tracking_error",
    "max_drawdown", "calmar_ratio", "beta", "alpha", "volatility",
    "up_capture", "down_capture", "batting_average", "best_day", "worst_day",
)


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

    @field_serializer(*_RATIO_FIELDS)
    def _round_ratio(self, v: float | None) -> float | None:
        return round_or_none(v, 6)


class ReturnSeriesEntry(BaseModel):
    """A single return data point."""

    date: date
    return_value: float
    cumulative_return: float

    @field_serializer("return_value", "cumulative_return")
    def _round_ratio(self, v: float) -> float:
        return round(v, 6)


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

    @field_serializer(
        "jan", "feb", "mar", "apr", "may", "jun",
        "jul", "aug", "sep", "oct", "nov", "dec", "ytd",
    )
    def _round_ratio(self, v: float | None) -> float | None:
        return round_or_none(v, 6)


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

    @field_serializer("rolling_1m", "rolling_3m", "rolling_6m", "rolling_1y", "rolling_3y")
    def _round_ratio(self, v: float | None) -> float | None:
        return round_or_none(v, 6)


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

    @field_serializer("portfolio_return", "benchmark_return", "active_return")
    def _round_ratio(self, v: float) -> float:
        return round(v, 6)

    @field_serializer("tracking_error", "information_ratio")
    def _round_ratio_optional(self, v: float | None) -> float | None:
        return round_or_none(v, 6)


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

    @field_serializer(
        "sharpe_ratio", "sortino_ratio", "information_ratio", "tracking_error",
        "beta", "alpha", "volatility", "max_drawdown", "calmar_ratio",
        "up_capture", "down_capture",
    )
    def _round_ratio(self, v: float | None) -> float | None:
        return round_or_none(v, 6)


class DrawdownResponse(BaseModel):
    """Drawdown analysis."""

    portfolio_id: UUID
    max_drawdown: float | None = None
    peak_date: date | None = None
    trough_date: date | None = None
    recovery_date: date | None = None
    duration_days: int | None = None

    @field_serializer("max_drawdown")
    def _round_ratio(self, v: float | None) -> float | None:
        return round_or_none(v, 6)


class PerformanceCompareEntry(BaseModel):
    """Single portfolio entry in a comparison."""

    portfolio_id: UUID
    portfolio_name: str | None = None
    twr_return: float | None = None
    sharpe_ratio: float | None = None
    max_drawdown: float | None = None
    volatility: float | None = None

    @field_serializer("twr_return", "sharpe_ratio", "max_drawdown", "volatility")
    def _round_ratio(self, v: float | None) -> float | None:
        return round_or_none(v, 6)


class PerformanceCompareResponse(BaseModel):
    """Compare multiple portfolios."""

    period: str
    portfolios: list[PerformanceCompareEntry]
