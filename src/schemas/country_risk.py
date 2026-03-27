"""Pydantic schemas for Pillar 3 Phase 3B Country Risk endpoints."""

from pydantic import BaseModel
from uuid import UUID
from datetime import date


class CountryProfileResponse(BaseModel):
    id: UUID
    country_code: str
    country_name: str
    region: str | None = None
    income_group: str | None = None
    is_g20: bool = False
    is_eu: bool = False
    population: float | None = None
    gdp_usd: float | None = None

    model_config = {"from_attributes": True}


class CountryRiskScoreResponse(BaseModel):
    id: UUID
    country_code: str
    as_of_date: date
    political_risk_score: float | None = None
    economic_risk_score: float | None = None
    sanctions_risk_score: float | None = None
    composite_risk_score: float | None = None
    risk_classification: str | None = None
    risk_trend: str | None = None
    political_components: dict | None = None
    economic_components: dict | None = None
    sanctions_components: dict | None = None

    model_config = {"from_attributes": True}


class CompanyExposureResponse(BaseModel):
    id: UUID
    entity_id: UUID
    country_code: str
    exposure_type: str | None = None
    exposure_pct: float | None = None
    source: str | None = None
    as_of_date: date | None = None

    model_config = {"from_attributes": True}


class GeopoliticalEventResponse(BaseModel):
    id: UUID
    event_type: str | None = None
    title: str
    description: str | None = None
    countries_involved: list | None = None
    severity: str | None = None
    status: str | None = None
    start_date: date | None = None
    commodity_impact: list | dict | None = None
    sector_impact: list | dict | None = None
    affected_entity_ids: list | None = None

    model_config = {"from_attributes": True}


class CountryRiskRankingResponse(BaseModel):
    country_code: str
    country_name: str
    composite_risk_score: float | None = None
    risk_classification: str | None = None
    rank: int

    model_config = {"from_attributes": True}
