"""Pydantic schemas for Layer 3 adviser chat (§5.3)."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class CreateConversationRequest(BaseModel):
    user_id: str = "default_user"
    portfolio_id: uuid.UUID
    title: str | None = None


class ConversationResponse(BaseModel):
    id: uuid.UUID
    user_id: str
    portfolio_id: uuid.UUID | None = None
    title: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class SendMessageRequest(BaseModel):
    message: str


class ConversationMessageResponse(BaseModel):
    id: uuid.UUID
    role: str
    content: str
    tool_calls: list | None = None
    citations: list | None = None
    tokens: int | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class RecommendationResponse(BaseModel):
    id: uuid.UUID
    kind: str
    action: dict | None = None
    rationale: str
    evidence: list | None = None
    whatif_impact: dict | None = None
    compliance: dict | None = None
    confidence: float | None = None
    status: str

    model_config = {"from_attributes": True}

    @classmethod
    def from_row(cls, row) -> "RecommendationResponse":
        return cls(
            id=row.id, kind=row.kind, action=row.action, rationale=row.rationale,
            evidence=row.evidence, whatif_impact=row.whatif_impact, compliance=row.compliance,
            confidence=float(row.confidence) if row.confidence is not None else None,
            status=row.status,
        )
