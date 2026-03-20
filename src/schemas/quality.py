"""Pydantic schemas for Data Quality Framework endpoints."""

import uuid
from datetime import datetime

from pydantic import BaseModel


class DataQualityScoreResponse(BaseModel):
    score_id: uuid.UUID
    domain: str
    entity_id: uuid.UUID | None = None
    measured_at: datetime
    overall_score: float
    accuracy_score: float | None = None
    completeness_score: float | None = None
    timeliness_score: float | None = None
    consistency_score: float | None = None
    issues_count: int
    critical_issues: int

    model_config = {"from_attributes": True}


class DataQualityIssueResponse(BaseModel):
    issue_id: uuid.UUID
    domain: str
    entity_id: uuid.UUID | None = None
    record_id: uuid.UUID | None = None
    issue_type: str
    severity: str
    field_name: str | None = None
    issue_description: str | None = None
    detected_at: datetime
    resolved_at: datetime | None = None
    resolution: str | None = None

    model_config = {"from_attributes": True}
