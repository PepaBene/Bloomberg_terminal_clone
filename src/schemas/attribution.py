"""Pydantic schemas for Pillar 4 Phase 2: Attribution endpoints."""

from datetime import date
from uuid import UUID

from pydantic import BaseModel, field_serializer

from src.schemas.common import round_or_none

# P4-M-007: attribution effect/return/weight fields are deliberately kept
# as ``float`` on the wire (Pydantic v2 serializes ``Decimal`` as a quoted
# string by default, which would break existing JSON number consumers).
# All are rounded to 6 decimal places via ``field_serializer``, matching
# the meaningful precision of the source ``Numeric(12, 8)`` columns on
# ``AttributionResult`` (and the equivalent JSONB-detail fields), to avoid
# false floating-point precision on the wire.


class SectorAttributionEntry(BaseModel):
    """Single sector in Brinson attribution."""

    sector: str
    portfolio_weight: float
    benchmark_weight: float
    portfolio_return: float
    benchmark_return: float
    allocation_effect: float
    selection_effect: float
    interaction_effect: float
    total_effect: float

    @field_serializer(
        "portfolio_weight", "benchmark_weight", "portfolio_return", "benchmark_return",
        "allocation_effect", "selection_effect", "interaction_effect", "total_effect",
    )
    def _round_ratio(self, v: float) -> float:
        return round(v, 6)


class BrinsonResponse(BaseModel):
    """Full Brinson attribution result."""

    portfolio_id: UUID
    period_start: date
    period_end: date
    total_portfolio_return: float | None = None
    total_benchmark_return: float | None = None
    total_active_return: float | None = None
    total_allocation: float | None = None
    total_selection: float | None = None
    total_interaction: float | None = None
    residual: float | None = None
    sector_detail: list[SectorAttributionEntry]

    @field_serializer(
        "total_portfolio_return", "total_benchmark_return", "total_active_return",
        "total_allocation", "total_selection", "total_interaction", "residual",
    )
    def _round_ratio(self, v: float | None) -> float | None:
        return round_or_none(v, 6)


class SecurityContributionEntry(BaseModel):
    """Single security contribution."""

    ticker: str
    weight: float
    return_value: float
    contribution: float

    @field_serializer("weight", "return_value", "contribution")
    def _round_ratio(self, v: float) -> float:
        return round(v, 6)


class FactorAttributionEntry(BaseModel):
    """Single factor in factor attribution."""

    factor: str
    portfolio_exposure: float
    benchmark_exposure: float
    factor_return: float
    contribution: float

    @field_serializer("portfolio_exposure", "benchmark_exposure", "factor_return", "contribution")
    def _round_ratio(self, v: float) -> float:
        return round(v, 6)


class AttributionResponse(BaseModel):
    """Combined attribution result."""

    portfolio_id: UUID
    period_start: date
    period_end: date
    brinson: BrinsonResponse | None = None
    factor_detail: list[FactorAttributionEntry]
    top_contributors: list[SecurityContributionEntry]
    bottom_contributors: list[SecurityContributionEntry]
