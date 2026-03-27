"""Pydantic schemas for Pillar 3 Phase 3A Industry Intelligence endpoints."""

from pydantic import BaseModel
from uuid import UUID
from datetime import date


class IndustryProfileResponse(BaseModel):
    id: UUID
    gics_code: str
    gics_level: str
    gics_name: str
    as_of_date: date
    company_count: int | None = None
    total_market_cap: float | None = None
    median_market_cap: float | None = None
    revenue_growth_3y_cagr: float | None = None
    revenue_growth_5y_cagr: float | None = None
    revenue_dispersion: float | None = None
    median_gross_margin: float | None = None
    median_operating_margin: float | None = None
    median_capex_to_revenue: float | None = None
    median_rd_to_revenue: float | None = None
    median_roic: float | None = None
    median_wacc: float | None = None
    roic_wacc_spread: float | None = None
    roic_dispersion: float | None = None
    capital_cycle_indicator: str | None = None

    model_config = {"from_attributes": True}


class IndustryCycleResponse(BaseModel):
    id: UUID
    gics_code: str
    as_of_date: date
    revenue_growth_acceleration: float | None = None
    capacity_utilization_proxy: float | None = None
    inventory_dynamics: str | None = None
    inventory_to_sales_trend: float | None = None
    margin_cycle_direction: str | None = None
    operating_margin_momentum: float | None = None
    cycle_position: str
    cycle_confidence: float | None = None
    prior_cycle_position: str | None = None
    cycle_duration_quarters: int | None = None

    model_config = {"from_attributes": True}


class IndustryStructureResponse(BaseModel):
    id: UUID
    gics_code: str
    as_of_date: date
    hhi_index: float | None = None
    hhi_classification: str | None = None
    top3_market_share: float | None = None
    top5_market_share: float | None = None
    top10_market_share: float | None = None
    consolidation_trend: str | None = None
    consolidation_5y_delta: float | None = None
    barrier_to_entry: str | None = None
    barrier_factors: dict | None = None
    pricing_power: str | None = None
    pricing_power_evidence: dict | None = None
    competitive_dynamics: str | None = None
    market_share_data: dict | None = None

    model_config = {"from_attributes": True}


class IndustryCompareResponse(BaseModel):
    gics_code: str
    gics_name: str
    company_count: int | None = None
    total_market_cap: float | None = None
    median_gross_margin: float | None = None
    median_operating_margin: float | None = None
    median_roic: float | None = None
    revenue_growth_3y_cagr: float | None = None
    capital_cycle_indicator: str | None = None

    model_config = {"from_attributes": True}


class IndustryRankingEntry(BaseModel):
    gics_code: str
    gics_name: str
    metric_value: float | None = None
    rank: int

    model_config = {"from_attributes": True}


class IndustryRankingResponse(BaseModel):
    metric: str
    rankings: list[IndustryRankingEntry] = []
