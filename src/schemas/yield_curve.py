"""Pydantic schemas for Yield Curve API."""

import uuid
from datetime import date, datetime

from pydantic import BaseModel


class YieldCurveSnapshotResponse(BaseModel):
    """Daily yield curve snapshot."""
    curve_id: uuid.UUID
    curve_date: date
    curve_type: str
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
    spread_2s10s: float | None = None
    spread_3m10y: float | None = None
    curve_slope: float | None = None
    is_inverted: bool = False
    source: str | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class ZeroCouponCurveResponse(BaseModel):
    """Single zero-coupon curve point."""
    id: uuid.UUID
    curve_date: date
    tenor_years: float
    zero_rate: float | None = None
    discount_factor: float | None = None
    forward_rate: float | None = None

    model_config = {"from_attributes": True}


class ForwardCurveResponse(BaseModel):
    """Collection of forward rates for a given date."""
    curve_date: date
    points: list[ZeroCouponCurveResponse] = []
