"""Pydantic schemas for yield curve analytics."""

import uuid
from datetime import date

from pydantic import BaseModel


class FittedCurvePointResponse(BaseModel):
    """Single point on a fitted curve."""
    tenor_years: float
    fitted_rate: float


class NelsonSiegelParamsResponse(BaseModel):
    """Nelson-Siegel model parameters."""
    beta0: float
    beta1: float
    beta2: float
    tau: float
    fit_error: float


class FittedCurveResponse(BaseModel):
    """Fitted yield curve with params and interpolated points."""

    model_config = {"from_attributes": True}

    fit_id: uuid.UUID | None = None
    curve_date: date
    curve_type: str
    method: str
    params: NelsonSiegelParamsResponse | None = None
    points: list[FittedCurvePointResponse] = []


class CurveAnalyticsResponse(BaseModel):
    """Daily yield curve analytics metrics."""

    model_config = {"from_attributes": True}

    id: uuid.UUID | None = None
    curve_date: date
    spread_2s10s: float | None = None
    spread_3m10y: float | None = None
    steepness: float | None = None
    curvature: float | None = None
    breakeven_5y: float | None = None
    breakeven_10y: float | None = None
    is_inverted: bool | None = None


class RiskFreeRateResponse(BaseModel):
    """Interpolated risk-free rate at a specific tenor."""
    tenor_years: float
    rate: float
    curve_date: date
    interpolation_method: str


class CurveScenarioRequest(BaseModel):
    """Request to generate a scenario-shifted curve."""
    shift_type: str  # PARALLEL, STEEPENER, FLATTENER, CUSTOM
    shift_bps: float = 100.0
    custom_shifts: dict[str, float] | None = None  # {tenor: bps shift}


class ShiftedCurvePointResponse(BaseModel):
    """A point on a shifted curve."""
    tenor_years: float
    original_rate: float
    shifted_rate: float
    shift_bps: float


class CurveScenarioResponse(BaseModel):
    """Scenario-shifted curve response."""
    shift_type: str
    shift_bps: float
    points: list[ShiftedCurvePointResponse] = []


class CurveSpreadHistoryPointResponse(BaseModel):
    """Single point in spread history."""
    curve_date: date
    spread_value: float


class CurveSpreadHistoryResponse(BaseModel):
    """Spread time series."""
    spread_type: str
    points: list[CurveSpreadHistoryPointResponse] = []
