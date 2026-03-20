"""Pillar 2: Quantitative & Statistical schemas (Spec §9)."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Regression
# ---------------------------------------------------------------------------

class RegressionRequest(BaseModel):
    """Request body for running a regression."""
    security_id: UUID | None = None
    dependent_var: str = "daily_return"
    independent_vars: list[str] = ["market_return"]
    method: str = "OLS"
    period_days: int = 756
    data_source: str = "PRICE"


class RegressionResponse(BaseModel):
    """Regression results."""
    regression_id: UUID | None = None
    method: str = "OLS"
    coefficients: dict[str, float] = {}
    std_errors: dict[str, float] | None = None
    r_squared: float | None = None
    adj_r_squared: float | None = None
    f_statistic: float | None = None
    f_p_value: float | None = None
    n_observations: int = 0
    confidence_intervals: dict[str, list[float]] | None = None
    residuals_summary: dict | None = None


class RollingRegressionRequest(BaseModel):
    """Request for rolling regression."""
    security_id: UUID
    independent_var: str = "market_return"
    window: int = 60
    period_days: int = 1260


class RollingRegressionPoint(BaseModel):
    """Single data point in rolling regression output."""
    index: int
    beta: float
    alpha: float
    r_squared: float


class RollingRegressionResponse(BaseModel):
    """Rolling regression time series."""
    security_id: UUID | None = None
    data_points: list[RollingRegressionPoint] = []


# ---------------------------------------------------------------------------
# Correlation
# ---------------------------------------------------------------------------

class CorrelationRequest(BaseModel):
    """Pairwise correlation request."""
    series_x_id: str
    series_y_id: str
    method: str = "PEARSON"
    period_days: int = 756


class CorrelationResponse(BaseModel):
    """Pairwise correlation result."""
    correlation_id: UUID | None = None
    method: str = "PEARSON"
    coefficient: float | None = None
    p_value: float | None = None
    n_observations: int = 0


class CorrelationMatrixRequest(BaseModel):
    """Full correlation matrix request."""
    series_ids: list[str]
    method: str = "PEARSON"
    period_days: int = 756


class CorrelationMatrixResponse(BaseModel):
    """Correlation matrix result."""
    method: str = "PEARSON"
    labels: list[str] = []
    matrix: list[list[float | None]] = []
    p_values: list[list[float | None]] | None = None


# ---------------------------------------------------------------------------
# Stationarity / Time Series
# ---------------------------------------------------------------------------

class StationarityRequest(BaseModel):
    """Stationarity test request."""
    security_id: UUID | None = None
    series_name: str = "price"
    test_type: str = "ADF"
    period_days: int = 756


class StationarityResponse(BaseModel):
    """Stationarity test result."""
    test_id: UUID | None = None
    test_type: str = "ADF"
    series_name: str = ""
    test_statistic: float | None = None
    p_value: float | None = None
    critical_values: dict[str, float] | None = None
    is_significant: bool = False
    lags_used: int | None = None


class CointegrationRequest(BaseModel):
    """Cointegration test request."""
    series_x_id: str
    series_y_id: str
    period_days: int = 756


class CointegrationResponse(BaseModel):
    """Cointegration test result."""
    test_id: UUID | None = None
    test_statistic: float | None = None
    p_value: float | None = None
    hedge_ratio: float | None = None
    is_cointegrated: bool = False


class AutocorrelationRequest(BaseModel):
    """Autocorrelation request."""
    security_id: UUID
    max_lags: int = 20
    period_days: int = 756


class AutocorrelationResponse(BaseModel):
    """ACF / PACF result."""
    security_id: UUID | None = None
    lags: list[int] = []
    acf_values: list[float] = []


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

class QuantSummaryResponse(BaseModel):
    """Default quant metrics summary for a security."""
    security_id: UUID
    beta_market: float | None = None
    beta_blume_adjusted: float | None = None
    beta_rolling_60d: float | None = None
    correlation_market_pearson: float | None = None
    correlation_market_spearman: float | None = None
    autocorrelation_lag1: float | None = None
    adf_test_statistic: float | None = None
    adf_p_value: float | None = None
    is_stationary: bool | None = None
