"""Pydantic schemas for Pillar 3 Phase 4A: Anomaly Detection."""

from pydantic import BaseModel
from uuid import UUID
from datetime import date, datetime


class AnomalyResponse(BaseModel):
    id: UUID
    entity_id: UUID
    anomaly_type: str
    severity_score: float
    detected_at: datetime | None = None
    anomaly_window_start: date | None = None
    anomaly_window_end: date | None = None
    lookback_period: str | None = None
    observed_value: float | None = None
    expected_value: float | None = None
    z_score: float | None = None
    percentile_rank: float | None = None
    contextual_analysis: dict | None = None
    related_data: dict | None = None
    ai_narrative: str | None = None
    recommended_actions: dict | None = None
    confidence_level: float | None = None
    is_acknowledged: bool = False
    acknowledged_by: str | None = None

    model_config = {"from_attributes": True}


class AnomalyListResponse(BaseModel):
    anomalies: list[AnomalyResponse]
    total_count: int


class AnomalyRuleResponse(BaseModel):
    id: UUID
    anomaly_type: str
    rule_name: str
    description: str | None = None
    threshold_config: dict | None = None
    is_enabled: bool = True

    model_config = {"from_attributes": True}


class AnomalyRuleCreateRequest(BaseModel):
    anomaly_type: str
    rule_name: str
    description: str | None = None
    threshold_config: dict | None = None
    is_enabled: bool = True
