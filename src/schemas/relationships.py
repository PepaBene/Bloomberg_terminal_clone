"""Pydantic schemas for D10 Business Relationships endpoints."""

import uuid
from datetime import date, datetime

from pydantic import BaseModel


# --- Full relationship response ---
class BusinessRelationshipResponse(BaseModel):
    relationship_id: uuid.UUID
    source_entity_id: uuid.UUID
    target_entity_id: uuid.UUID
    relationship_type: str
    direction: str | None = None
    revenue_percentage: float | None = None
    cost_percentage: float | None = None
    contract_value: float | None = None
    contract_currency: str | None = None
    contract_start_date: date | None = None
    contract_end_date: date | None = None
    is_single_source: bool | None = None
    materiality_score: float | None = None
    confidence_score: float | None = None
    extraction_method: str | None = None
    source_document: str | None = None
    source_text: str | None = None
    effective_date: date | None = None
    termination_date: date | None = None
    is_active: bool = True
    metadata_json: dict | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


# --- Brief relationship response (for lists) ---
class BusinessRelationshipBriefResponse(BaseModel):
    relationship_id: uuid.UUID
    source_entity_id: uuid.UUID
    target_entity_id: uuid.UUID
    relationship_type: str
    direction: str | None = None
    revenue_percentage: float | None = None
    cost_percentage: float | None = None
    materiality_score: float | None = None
    confidence_score: float | None = None
    is_active: bool = True

    model_config = {"from_attributes": True}


# --- Relationship history response ---
class RelationshipHistoryResponse(BaseModel):
    history_id: uuid.UUID
    relationship_id: uuid.UUID
    change_type: str
    change_date: date | None = None
    previous_revenue_percentage: float | None = None
    new_revenue_percentage: float | None = None
    previous_materiality_score: float | None = None
    new_materiality_score: float | None = None
    change_details: dict | None = None
    source: str | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}
