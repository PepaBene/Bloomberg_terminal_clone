"""Pydantic schemas for Pillar 3 Phase 3B Political Intelligence endpoints."""

from pydantic import BaseModel
from uuid import UUID
from datetime import date


class LegislativeBillResponse(BaseModel):
    id: UUID
    bill_id: str
    title: str
    summary: str | None = None
    bill_type: str | None = None
    status: str | None = None
    sponsor_count: int | None = None
    passage_probability: float | None = None
    affected_sectors: list | dict | None = None
    affected_entity_ids: list | dict | None = None
    introduced_date: date | None = None
    last_action_date: date | None = None
    source_url: str | None = None

    model_config = {"from_attributes": True}


class RegulatoryActionResponse(BaseModel):
    id: UUID
    agency: str | None = None
    action_type: str | None = None
    title: str
    description: str | None = None
    affected_entity_ids: list | dict | None = None
    affected_sectors: list | dict | None = None
    severity: str | None = None
    financial_impact: float | None = None
    action_date: date | None = None
    source_url: str | None = None

    model_config = {"from_attributes": True}


class SanctionsEntryResponse(BaseModel):
    id: UUID
    program: str | None = None
    country_code: str | None = None
    target_name: str | None = None
    target_type: str | None = None
    status: str | None = None
    effective_date: date | None = None
    description: str | None = None
    affected_sectors: list | dict | None = None
    source_url: str | None = None

    model_config = {"from_attributes": True}


class ElectionResponse(BaseModel):
    country_code: str
    election_type: str | None = None
    election_date: date | None = None
    description: str | None = None
    market_impact: str | None = None

    model_config = {"from_attributes": True}
