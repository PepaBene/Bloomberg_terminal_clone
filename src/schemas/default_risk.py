"""Pydantic schemas for default risk scoring."""

import uuid
from datetime import date

from pydantic import BaseModel


class MertonModelResponse(BaseModel):
    """Merton Distance-to-Default model outputs."""
    distance_to_default: float | None = None
    probability_of_default: float | None = None
    asset_value: float | None = None
    asset_volatility: float | None = None
    equity_volatility: float | None = None


class AltmanScoreResponse(BaseModel):
    """Altman Z-Score component."""
    z_score: float | None = None
    zone: str | None = None  # SAFE, GREY, DISTRESS


class KeyDriverResponse(BaseModel):
    """Single driver in credit risk decomposition."""
    driver: str
    contribution: float
    description: str | None = None


class DefaultRiskScoreResponse(BaseModel):
    """Full default risk score for an entity."""

    model_config = {"from_attributes": True}

    score_id: uuid.UUID | None = None
    entity_id: uuid.UUID
    security_id: uuid.UUID | None = None
    calculation_date: date
    altman: AltmanScoreResponse | None = None
    merton: MertonModelResponse | None = None
    composite_score: float | None = None
    implied_rating: str | None = None
    credit_zone: str | None = None
    key_drivers: list[KeyDriverResponse] = []
    prior_score: float | None = None
    score_change: float | None = None
    trend: str | None = None
    data_quality: str | None = None


class DefaultRiskHistoryPointResponse(BaseModel):
    """Single point in default risk history."""
    calculation_date: date
    composite_score: float | None = None
    implied_rating: str | None = None
    credit_zone: str | None = None
    altman_z_score: float | None = None
    merton_dd: float | None = None
    merton_pd: float | None = None


class DefaultRiskHistoryResponse(BaseModel):
    """Default risk history for an entity."""
    entity_id: uuid.UUID
    points: list[DefaultRiskHistoryPointResponse] = []


class DefaultRiskDriversResponse(BaseModel):
    """Driver decomposition for an entity's risk score."""
    entity_id: uuid.UUID
    calculation_date: date
    composite_score: float | None = None
    drivers: list[KeyDriverResponse] = []


class CreditRiskAlertResponse(BaseModel):
    """Entity with deteriorating credit risk."""
    entity_id: uuid.UUID
    entity_name: str | None = None
    calculation_date: date
    composite_score: float | None = None
    prior_score: float | None = None
    score_change: float | None = None
    trend: str | None = None
    implied_rating: str | None = None
    credit_zone: str | None = None
