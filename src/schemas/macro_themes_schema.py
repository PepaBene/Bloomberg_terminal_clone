"""Pydantic schemas for Pillar 3 Phase 4C: Macro Themes & Scenarios."""

from pydantic import BaseModel
from uuid import UUID
from datetime import date, datetime


class ThemeScoreResponse(BaseModel):
    id: UUID
    entity_id: UUID
    theme: str
    exposure_score: float | None = None
    sensitivity_direction: str | None = None
    evidence: dict | None = None
    quantified_exposure: str | None = None
    as_of_date: date
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class ThemeScreenRequest(BaseModel):
    theme: str
    min_exposure: float | None = None
    max_exposure: float | None = None
    sensitivity_direction: str | None = None
    limit: int = 50


class ThemeScreenResponse(BaseModel):
    entity_id: UUID
    theme: str
    exposure_score: float | None = None
    sensitivity_direction: str | None = None
    quantified_exposure: str | None = None
    as_of_date: date

    model_config = {"from_attributes": True}


class ScenarioResponse(BaseModel):
    id: UUID
    scenario_name: str
    scenario_type: str | None = None
    description: str | None = None
    assumptions: dict | None = None
    is_active: bool | None = True
    created_by: str | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class ScenarioImpactResponse(BaseModel):
    id: UUID
    scenario_id: UUID
    entity_id: UUID
    base_eps: float | None = None
    scenario_eps: float | None = None
    eps_change_pct: float | None = None
    margin_impact_bps: float | None = None
    rating_implication: str | None = None
    price_target_scenario: float | None = None
    narrative: str | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class ScenarioCreateRequest(BaseModel):
    scenario_name: str
    scenario_type: str | None = None
    description: str | None = None
    assumptions: dict | None = None
    created_by: str | None = None
