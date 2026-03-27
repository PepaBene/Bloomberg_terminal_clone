"""Pydantic schemas for Pillar 4 Phase 1: Corporate action endpoints."""

from pydantic import BaseModel
from uuid import UUID
from datetime import date, datetime


class CorporateActionResponse(BaseModel):
    id: UUID
    portfolio_id: UUID
    position_id: UUID | None = None
    action_type: str
    security_id: UUID | None = None
    ticker: str | None = None
    ex_date: date | None = None
    payment_date: date | None = None
    details: dict | None = None
    status: str
    applied_at: datetime | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class CorporateActionApplyRequest(BaseModel):
    notes: str | None = None
