"""Pydantic schemas for Pillar 3 Filing Intelligence (filing diffs, 8-K events)."""

from pydantic import BaseModel
from uuid import UUID
from datetime import date
from typing import Optional


class EightKEventResponse(BaseModel):
    id: UUID
    entity_id: UUID
    filing_date: date
    item_number: str
    item_description: str | None = None
    priority: int
    monetary_figures: list[dict] | None = None
    key_dates: list[dict] | None = None
    key_people: list[dict] | None = None
    ai_summary: str | None = None
    materiality: str | None = None
    filing_url: str | None = None

    model_config = {"from_attributes": True}


class EightKEventsListResponse(BaseModel):
    events: list[EightKEventResponse]
    total_count: int


class FilingDiffSectionResponse(BaseModel):
    section_key: str
    section_name: str | None = None
    change_pct: float | None = None
    classification: str | None = None
    materiality: str | None = None
    substantive_count: int = 0
    added_count: int = 0
    removed_count: int = 0
    modified_count: int = 0
    added_paragraphs: list[dict] | None = None
    removed_paragraphs: list[dict] | None = None
    modified_paragraphs: list[dict] | None = None


class FilingDiffResponse(BaseModel):
    entity_id: UUID
    year_old: int
    year_new: int
    overall_materiality: str | None = None
    section_diffs: list[FilingDiffSectionResponse] = []
    ai_summary: str | None = None


class FilingDiffSummaryResponse(BaseModel):
    entity_id: UUID
    year_old: int
    year_new: int
    overall_materiality: str | None = None
    ai_summary: str | None = None
    top_changes: list[dict] = []
