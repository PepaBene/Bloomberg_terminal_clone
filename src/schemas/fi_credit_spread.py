"""Pydantic v2 schemas for Credit Spread Indices API (D11 FI Supplement P6)."""

import uuid
from datetime import date, datetime

from pydantic import BaseModel


class CreditSpreadIndexResponse(BaseModel):
    """Single credit spread index observation."""

    id: uuid.UUID
    series_id: str
    observation_date: date
    index_name: str | None = None
    rating_category: str | None = None
    spread_bps: float | None = None
    total_return_index: float | None = None
    source: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class CreditSpreadPercentileResponse(BaseModel):
    """Percentile rank and descriptive stats for a spread series."""

    id: uuid.UUID
    series_id: str
    as_of_date: date
    lookback_years: int
    percentile_rank: float | None = None
    current_oas: float | None = None
    min_oas: float | None = None
    max_oas: float | None = None
    mean_oas: float | None = None
    std_dev: float | None = None
    z_score: float | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class SpreadRegimeResponse(BaseModel):
    """Current spread regime classification for a rating category."""

    regime: str
    percentile: float
    current_oas: float | None = None
    category: str

    model_config = {"from_attributes": True}


class IGHYDifferentialResponse(BaseModel):
    """IG vs HY OAS differential."""

    ig_oas: float | None = None
    hy_oas: float | None = None
    ratio: float | None = None
    spread: float | None = None

    model_config = {"from_attributes": True}
