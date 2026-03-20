"""Pydantic schemas for D1 Entity Master endpoints."""

import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field


# --- Entity Identifier ---
class EntityIdentifierResponse(BaseModel):
    identifier_type: str
    identifier_value: str
    source: str | None = None
    is_primary: bool = False

    model_config = {"from_attributes": True}


# --- Entity Name ---
class EntityNameResponse(BaseModel):
    name_type: str
    name_value: str
    effective_date: date | None = None
    end_date: date | None = None
    source: str | None = None

    model_config = {"from_attributes": True}


# --- Entity (full) ---
class EntityResponse(BaseModel):
    entity_id: uuid.UUID
    entity_type: str
    entity_subtype: str | None = None
    legal_name: str
    legal_name_local: str | None = None
    short_name: str | None = None
    status: str
    status_date: date | None = None
    status_reason: str | None = None
    incorporation_country: str | None = None
    incorporation_state: str | None = None
    incorporation_date: date | None = None
    jurisdiction_type: str | None = None
    domicile_country: str | None = None
    domicile_address: dict | None = None
    fiscal_year_end: str | None = None
    reporting_currency: str | None = None
    accounting_standard: str | None = None
    primary_sic: str | None = None
    primary_naics: str | None = None
    gics_sector: str | None = None
    gics_industry_group: str | None = None
    gics_industry: str | None = None
    gics_sub_industry: str | None = None
    ultimate_parent_id: uuid.UUID | None = None
    immediate_parent_id: uuid.UUID | None = None
    ownership_percentage: float | None = None
    consolidation_type: str | None = None
    source: str
    confidence_score: float | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    # Expandable
    identifiers: list[EntityIdentifierResponse] | None = None
    names: list[EntityNameResponse] | None = None

    model_config = {"from_attributes": True}


# --- Entity Brief (for lists) ---
class EntityBriefResponse(BaseModel):
    entity_id: uuid.UUID
    legal_name: str
    short_name: str | None = None
    entity_type: str
    status: str
    incorporation_country: str | None = None

    model_config = {"from_attributes": True}


# --- Entity Relationship ---
class EntityRelationshipResponse(BaseModel):
    relationship_id: uuid.UUID
    source_entity_id: uuid.UUID
    target_entity_id: uuid.UUID
    relationship_type: str
    effective_date: date | None = None
    termination_date: date | None = None
    ownership_percentage: float | None = None
    relationship_details: dict | None = None
    source: str | None = None
    source_document: str | None = None

    model_config = {"from_attributes": True}


# --- Entity History ---
class EntityHistoryResponse(BaseModel):
    history_id: uuid.UUID
    entity_id: uuid.UUID
    entity_type: str
    legal_name: str
    short_name: str | None = None
    status: str
    incorporation_country: str | None = None
    domicile_country: str | None = None
    fiscal_year_end: str | None = None
    reporting_currency: str | None = None
    accounting_standard: str | None = None
    primary_sic: str | None = None
    gics_sub_industry: str | None = None
    ultimate_parent_id: uuid.UUID | None = None
    immediate_parent_id: uuid.UUID | None = None
    source: str | None = None
    confidence_score: float | None = None
    valid_from: datetime
    valid_to: datetime | None = None
    revision_number: int

    model_config = {"from_attributes": True}


# --- Entity Hierarchy ---
class EntityHierarchyNode(BaseModel):
    entity_id: uuid.UUID
    legal_name: str
    entity_type: str
    status: str
    relationship_type: str | None = None
    ownership_percentage: float | None = None
    children: list["EntityHierarchyNode"] = []


class EntityHierarchyResponse(BaseModel):
    entity_id: uuid.UUID
    legal_name: str
    ultimate_parent: EntityBriefResponse | None = None
    immediate_parent: EntityBriefResponse | None = None
    subsidiaries: list[EntityBriefResponse] = []


# --- Entity Search ---
class EntitySearchResult(BaseModel):
    entity_id: uuid.UUID
    legal_name: str
    short_name: str | None = None
    entity_type: str
    status: str
    incorporation_country: str | None = None
    score: float = 0.0


class EntitySearchResponse(BaseModel):
    results: list[EntitySearchResult]
    total: int
    query: str


# --- Resolution ---
class EntityResolveRequest(BaseModel):
    legal_name: str
    country: str | None = None
    identifiers: dict[str, str] = Field(default_factory=dict)


class EntityResolveResponse(BaseModel):
    matched_entity_id: uuid.UUID | None = None
    confidence: float
    match_method: str | None = None
    status: str  # MATCHED, UNCERTAIN, NEW


# --- Bulk Lookup ---
class IdentifierLookup(BaseModel):
    type: str
    value: str


class BulkLookupRequest(BaseModel):
    identifiers: list[IdentifierLookup]


class BulkLookupResponse(BaseModel):
    results: list[EntityResponse | None]
