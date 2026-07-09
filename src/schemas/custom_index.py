"""Pydantic schemas for custom index."""

import uuid
from datetime import date

from pydantic import BaseModel


class CreateIndexRequest(BaseModel):
    """Request to create a custom index."""
    name: str
    description: str | None = None
    weighting_method: str = "EQUAL"
    rebalance_frequency: str = "QUARTERLY"
    max_constituents: int | None = None
    min_market_cap: float | None = None
    security_ids: list[uuid.UUID] = []


class SetConstituentsRequest(BaseModel):
    """Set (replace) the constituents of a custom index.

    Weights are computed by the custom-index engine from ``weighting_method``
    (falling back to the index's configured method). ``market_caps`` /
    ``scores`` are positionally aligned with ``security_ids``.
    """
    security_ids: list[uuid.UUID]
    weighting_method: str | None = None
    market_caps: list[float] | None = None
    scores: list[float] | None = None


class CustomIndexResponse(BaseModel):
    """Custom index response."""

    model_config = {"from_attributes": True}

    index_id: uuid.UUID
    name: str
    description: str | None = None
    status: str
    weighting_method: str | None = None
    rebalance_frequency: str | None = None
    max_constituents: int | None = None
    inception_date: date | None = None
    total_return_inception: float | None = None
    annualized_return: float | None = None
    annualized_volatility: float | None = None
    sharpe_ratio: float | None = None
    max_drawdown: float | None = None


class IndexConstituentResponse(BaseModel):
    """Single constituent in an index."""

    model_config = {"from_attributes": True}

    constituent_id: uuid.UUID
    security_id: uuid.UUID
    weight: float | None = None
    added_date: date
    removed_date: date | None = None
    is_active: bool = True


class IndexPerformancePointResponse(BaseModel):
    """Single performance point."""
    perf_date: date
    index_level: float | None = None
    daily_return: float | None = None
    cumulative_return: float | None = None


class IndexPerformanceResponse(BaseModel):
    """Index performance time series."""
    index_id: uuid.UUID
    points: list[IndexPerformancePointResponse] = []
