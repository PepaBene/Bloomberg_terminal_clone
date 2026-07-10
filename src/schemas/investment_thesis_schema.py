"""Pydantic schemas for Pillar 3 Phase 4B: Investment Thesis."""

from pydantic import BaseModel
from uuid import UUID
from datetime import datetime


class ThesisCreateRequest(BaseModel):
    """Thesis content is analyst-authored free-form JSON by design (this is a
    research-authoring tool, not an auto-writer) -- key_drivers/primary_risks/
    valuation_scenarios/catalysts have no enforced schema. There is one
    documented (but not validated) convention that unlocks the auto-generated
    slide_outline (see research_thesis.py::_build_slide_outline) when followed:

        key_drivers / primary_risks / catalysts:
            {"items": [{"driver"|"risk"|"description": str, ...}, ...]}
        valuation_scenarios:
            {"current_price": float,
             "bull"/"base"/"bear": {"target_price": float, "implied_return": float}}

    Any section not in this shape is simply omitted from the slide outline
    rather than rejected -- the CRUD endpoints accept any dict.
    """

    analyst_id: str
    thesis_title: str | None = None
    investment_horizon: str | None = None
    conviction_level: str | None = None
    executive_summary: str | None = None
    key_drivers: dict | None = None
    primary_risks: dict | None = None
    valuation_scenarios: dict | None = None
    catalysts: dict | None = None


class ThesisResponse(BaseModel):
    id: UUID
    entity_id: UUID
    analyst_id: str
    version: int
    thesis_title: str | None = None
    investment_horizon: str | None = None
    conviction_level: str | None = None
    executive_summary: str | None = None
    key_drivers: dict | None = None
    primary_risks: dict | None = None
    valuation_scenarios: dict | None = None
    catalysts: dict | None = None
    quality_metrics: dict | None = None
    elevator_pitch: str | None = None
    slide_outline: dict | None = None
    ai_enabled: bool = False
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class ThesisVersionResponse(BaseModel):
    id: UUID
    thesis_id: UUID
    version: int
    conviction_change: float | None = None
    updated_drivers: dict | None = None
    analyst_note: str | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class ThesisDiffResponse(BaseModel):
    thesis_id: UUID
    current_version: int
    previous_version: int | None = None
    conviction_change: float | None = None
    updated_drivers: dict | None = None
    analyst_note: str | None = None


class ThesisListResponse(BaseModel):
    id: UUID
    entity_id: UUID
    analyst_id: str
    version: int
    thesis_title: str | None = None
    conviction_level: str | None = None
    executive_summary: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class ThesisUpdateRequest(BaseModel):
    conviction_level: str | None = None
    executive_summary: str | None = None
    key_drivers: dict | None = None
    primary_risks: dict | None = None
    valuation_scenarios: dict | None = None
    catalysts: dict | None = None
    analyst_note: str | None = None


class ThesisQualityReportResponse(BaseModel):
    total_theses: int
    avg_quality_score: float | None = None
    by_conviction: dict
    by_horizon: dict


class ThesisSlideOutlineResponse(BaseModel):
    thesis_id: UUID
    thesis_title: str | None = None
    slide_outline: dict | None = None


class ThesisElevatorPitchResponse(BaseModel):
    thesis_id: UUID
    thesis_title: str | None = None
    elevator_pitch: str | None = None
