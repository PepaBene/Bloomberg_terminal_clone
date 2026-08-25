"""Pydantic schemas for Layer 1 (Interpreter) endpoints."""
from __future__ import annotations

import uuid
from datetime import date

from pydantic import BaseModel


class MetricInterpretationResponse(BaseModel):
    metric_key: str
    interpretation: str
    trend: str | None = None
    direction: str | None = None
    drivers: list | None = None
    confidence: float | None = None
    citations: list | None = None
    ai_enabled: bool

    model_config = {"from_attributes": True}


class SubjectInterpretationResponse(BaseModel):
    interpretation: str
    trend: str | None = None
    direction: str | None = None
    drivers: list | None = None
    consequences: list | None = None
    connections: list | None = None
    confidence: float | None = None
    citations: list | None = None
    ai_enabled: bool

    model_config = {"from_attributes": True}


class EntityInterpretationResponse(BaseModel):
    entity_id: uuid.UUID
    as_of: date
    analytics_version: str
    metrics: dict[str, MetricInterpretationResponse]
    subject: SubjectInterpretationResponse | None = None
