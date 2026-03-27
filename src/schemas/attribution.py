"""Pydantic schemas for Pillar 4 Phase 2: Attribution endpoints."""

from datetime import date
from uuid import UUID

from pydantic import BaseModel


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


class SecurityContributionEntry(BaseModel):
    """Single security contribution."""

    ticker: str
    weight: float
    return_value: float
    contribution: float


class FactorAttributionEntry(BaseModel):
    """Single factor in factor attribution."""

    factor: str
    portfolio_exposure: float
    benchmark_exposure: float
    factor_return: float
    contribution: float


class AttributionResponse(BaseModel):
    """Combined attribution result."""

    portfolio_id: UUID
    period_start: date
    period_end: date
    brinson: BrinsonResponse | None = None
    factor_detail: list[FactorAttributionEntry]
    top_contributors: list[SecurityContributionEntry]
    bottom_contributors: list[SecurityContributionEntry]
