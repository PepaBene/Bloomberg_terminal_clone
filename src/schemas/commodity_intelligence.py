"""Pydantic schemas for Pillar 3 Phase 3B Commodity Intelligence endpoints."""

from pydantic import BaseModel
from uuid import UUID
from datetime import date


class CommodityProfileResponse(BaseModel):
    id: UUID
    commodity_code: str
    commodity_name: str | None = None
    category: str | None = None
    unit: str | None = None
    primary_source: str | None = None

    model_config = {"from_attributes": True}


class CommodityPriceResponse(BaseModel):
    id: UUID
    commodity_code: str
    price_date: date
    close_price: float | None = None
    open_price: float | None = None
    high_price: float | None = None
    low_price: float | None = None
    volume: float | None = None
    source: str | None = None

    model_config = {"from_attributes": True}


class CommodityExposureResponse(BaseModel):
    id: UUID
    commodity_code: str
    entity_id: UUID
    exposure_type: str | None = None
    exposure_description: str | None = None
    sensitivity_score: float | None = None
    historical_correlation: float | None = None
    source: str | None = None

    model_config = {"from_attributes": True}


class CommodityDashboardResponse(BaseModel):
    commodity_code: str
    commodity_name: str | None = None
    category: str | None = None
    latest_price: float | None = None
    price_date: date | None = None

    model_config = {"from_attributes": True}


class CommodityScenarioRequest(BaseModel):
    price_change_pct: float
    description: str | None = None


class CommodityScenarioResponse(BaseModel):
    commodity_code: str
    scenario_price_change_pct: float
    affected_companies: list[dict] = []


class CommoditySupplyDemandResponse(BaseModel):
    id: UUID
    commodity_code: str
    as_of_date: date
    supply_value: float | None = None
    demand_value: float | None = None
    inventory_value: float | None = None
    unit: str | None = None
    source: str | None = None
    balance_classification: str | None = None

    model_config = {"from_attributes": True}
