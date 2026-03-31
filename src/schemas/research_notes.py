"""Pydantic schemas for Research Notes."""

from pydantic import BaseModel
from uuid import UUID
from datetime import datetime


class ResearchNoteCreateRequest(BaseModel):
    title: str
    content: str
    note_type: str = "GENERAL"
    entity_id: str | None = None
    portfolio_id: UUID | None = None
    security_id: str | None = None
    ticker: str | None = None
    tags: list[str] | None = None
    sentiment: str | None = None
    priority: str = "NORMAL"


class ResearchNoteResponse(BaseModel):
    id: UUID
    user_id: str
    title: str
    content: str
    note_type: str
    entity_id: str | None = None
    portfolio_id: UUID | None = None
    security_id: str | None = None
    ticker: str | None = None
    tags: list[str] | None = None
    sentiment: str | None = None
    priority: str | None = None
    is_pinned: bool | None = None
    is_archived: bool | None = None
    attachments: dict | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class ResearchNoteUpdateRequest(BaseModel):
    title: str | None = None
    content: str | None = None
    note_type: str | None = None
    entity_id: str | None = None
    portfolio_id: UUID | None = None
    security_id: str | None = None
    ticker: str | None = None
    tags: list[str] | None = None
    sentiment: str | None = None
    priority: str | None = None
    is_pinned: bool | None = None
    is_archived: bool | None = None


class ResearchNoteListResponse(BaseModel):
    notes: list[ResearchNoteResponse]
    total: int
