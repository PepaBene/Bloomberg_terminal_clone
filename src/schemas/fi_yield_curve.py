"""Pydantic schemas for D11 FI Supplement: Fixed Income Yield Curve endpoints."""

import uuid
from datetime import date, datetime

from pydantic import BaseModel


class EnhancedYieldCurveResponse(BaseModel):
    """Full enhanced yield curve snapshot with par, zero, DF, forward, NSV, and spread fields."""

    model_config = {"from_attributes": True}

    curve_id: uuid.UUID
    curve_date: date
    curve_type: str

    # Par rates
    rate_1m: float | None = None
    rate_3m: float | None = None
    rate_6m: float | None = None
    rate_1y: float | None = None
    rate_2y: float | None = None
    rate_3y: float | None = None
    rate_5y: float | None = None
    rate_7y: float | None = None
    rate_10y: float | None = None
    rate_20y: float | None = None
    rate_30y: float | None = None

    # Existing spreads
    spread_2s10s: float | None = None
    spread_3m10y: float | None = None
    curve_slope: float | None = None
    is_inverted: bool = False
    source: str | None = None

    # Zero-coupon rates
    zero_1m: float | None = None
    zero_3m: float | None = None
    zero_6m: float | None = None
    zero_1y: float | None = None
    zero_2y: float | None = None
    zero_3y: float | None = None
    zero_5y: float | None = None
    zero_7y: float | None = None
    zero_10y: float | None = None
    zero_20y: float | None = None
    zero_30y: float | None = None

    # Discount factors
    df_1y: float | None = None
    df_2y: float | None = None
    df_5y: float | None = None
    df_10y: float | None = None
    df_20y: float | None = None
    df_30y: float | None = None

    # Forward rates
    fwd_0to1y: float | None = None
    fwd_1to2y: float | None = None
    fwd_2to5y: float | None = None
    fwd_5to10y: float | None = None
    fwd_10to30y: float | None = None

    # Nelson-Siegel-Svensson parameters
    nsv_beta0: float | None = None
    nsv_beta1: float | None = None
    nsv_beta2: float | None = None
    nsv_beta3: float | None = None
    nsv_lambda1: float | None = None
    nsv_lambda2: float | None = None
    nsv_fit_error: float | None = None

    # Additional spreads
    butterfly_spread: float | None = None
    spread_5s30s: float | None = None

    created_at: datetime | None = None


class ZeroRateCurveResponse(BaseModel):
    """Zero-coupon rate curve."""
    curve_date: date
    curve_type: str
    zero_rates: dict[str, float | None] = {}


class DiscountFactorResponse(BaseModel):
    """Discount factors for a curve date."""
    curve_date: date
    discount_factors: dict[str, float | None] = {}


class ForwardRateResponse(BaseModel):
    """Forward rates for a curve date."""
    curve_date: date
    forward_rates: dict[str, float | None] = {}


class NSVParamsResponse(BaseModel):
    """Nelson-Siegel-Svensson model parameters."""
    beta0: float | None = None
    beta1: float | None = None
    beta2: float | None = None
    beta3: float | None = None
    lambda1: float | None = None
    lambda2: float | None = None
    fit_error: float | None = None


class SpreadMetricsResponse(BaseModel):
    """Yield curve spread metrics."""
    curve_date: date
    spread_2s10s: float | None = None
    spread_3m10y: float | None = None
    spread_5s30s: float | None = None
    butterfly_spread: float | None = None
    is_inverted: bool = False


class CurveHistoryPointResponse(BaseModel):
    """Single point in a yield curve history time series."""
    curve_date: date
    rate: float | None = None


class CurveSurfacePointResponse(BaseModel):
    """Single point on a yield curve surface (date x tenor x rate)."""
    curve_date: date
    tenor: str
    rate: float | None = None


class FIScenarioRequest(BaseModel):
    """Request body for FI yield curve scenario analysis."""
    shift_type: str  # PARALLEL, STEEPENER, FLATTENER
    shift_bps: float = 100.0


class FIScenarioResponse(BaseModel):
    """Response for FI yield curve scenario analysis."""
    shift_type: str
    shift_bps: float
    original_rates: dict[str, float | None] = {}
    shifted_rates: dict[str, float | None] = {}


class DiscountFactorInterpolatedResponse(BaseModel):
    """Interpolated discount factor at a specific tenor."""
    curve_date: date
    tenor_years: float
    discount_factor: float | None = None
