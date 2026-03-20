"""Pydantic schemas for E4 Screening & Ranking endpoints."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class ScreenFilter(BaseModel):
    """Single filter criterion."""

    field: str
    source: str = "ANALYTICS_RESULT"  # ANALYTICS_RESULT, ENTITY, SECURITY, OWNERSHIP
    op: str = "GT"  # GT, LT, GTE, LTE, EQ, NEQ, BETWEEN, IN, NOT_IN, CONTAINS, NOT_NULL, TOP_N, BOTTOM_N, TOP_N_PCT, BOTTOM_N_PCT
    value: Any = None
    value2: Any = None  # for BETWEEN


class ScreenFilterGroup(BaseModel):
    """Logical grouping of filters (AND/OR/NOT, recursive)."""

    logic: str = "AND"  # AND, OR, NOT
    filters: list[ScreenFilter | ScreenFilterGroup] = []


class RankFactor(BaseModel):
    """Single factor in a multi-factor ranking."""

    field: str
    weight: float = 1.0
    ascending: bool = False  # True = lower is better


class ScreenRequest(BaseModel):
    """Custom screen execution request."""

    universe: str = "ALL"
    custom_universe_ids: list[uuid.UUID] | None = None
    filters: ScreenFilterGroup
    ranking: list[RankFactor] | None = None
    limit: int = Field(default=100, le=1000)
    include_metrics: list[str] | None = None


class RankRequest(BaseModel):
    """Multi-factor ranking request."""

    security_ids: list[uuid.UUID] | None = None
    universe: str = "ALL"
    factors: list[RankFactor]
    limit: int = Field(default=100, le=1000)


class SaveScreenRequest(BaseModel):
    """Save a custom screen definition."""

    name: str
    description: str | None = None
    definition: ScreenRequest
    tags: list[str] | None = None


class CustomUniverseRequest(BaseModel):
    """Define a custom universe of securities."""

    name: str
    security_ids: list[uuid.UUID]


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class ScreenedSecurity(BaseModel):
    """Single security in a screen result."""

    security_id: uuid.UUID
    entity_id: uuid.UUID | None = None
    ticker: str | None = None
    name: str | None = None
    rank: int | None = None
    composite_score: float | None = None
    metrics: dict[str, float | None] = {}


class ScreenResult(BaseModel):
    """Screen execution result."""

    total_matches: int
    securities: list[ScreenedSecurity] = []
    screen_name: str | None = None
    universe: str = "ALL"
    execution_time_ms: int = 0


class PrebuiltScreenSummary(BaseModel):
    """Summary of a pre-built screen for listing."""

    screen_id: str
    name: str
    description: str | None = None
    tags: list[str] = []
    filter_count: int = 0


class PrebuiltScreenDetail(BaseModel):
    """Full definition of a pre-built screen."""

    screen_id: str
    name: str
    description: str | None = None
    tags: list[str] = []
    filters: dict = {}
    ranking: list[dict] | None = None


class SavedScreenResponse(BaseModel):
    """Response for a saved screen."""

    model_config = {"from_attributes": True}

    screen_id: uuid.UUID
    name: str
    description: str | None = None
    screen_type: str
    is_prebuilt: bool = False
    universe: str = "ALL"
    tags: list | None = None
    created_at: datetime | None = None
    last_run_at: datetime | None = None
    result_count: int | None = None


class ScreenFieldMeta(BaseModel):
    """Metadata for a single screenable field."""

    field_name: str
    source: str
    data_type: str  # numeric, categorical, boolean
    description: str | None = None
    category: str | None = None
    unit: str | None = None


class ScreenFieldsResponse(BaseModel):
    """All screenable fields."""

    total_fields: int
    fields: list[ScreenFieldMeta] = []


class UniverseResponse(BaseModel):
    """Universe definition."""

    universe_name: str
    security_count: int
    security_ids: list[uuid.UUID] = []
