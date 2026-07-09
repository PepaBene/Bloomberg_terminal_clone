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


class MertonComputeRequest(BaseModel):
    """Inputs for an on-demand Merton distance-to-default computation.

    ``equity_value``, ``equity_volatility`` and ``total_debt`` may all be
    omitted when ``entity_id`` is supplied — they are then auto-sourced from
    real DB data (latest EOD close x shares_outstanding for market cap, and
    annualized daily-log-return volatility over the trailing year).
    """
    equity_value: float | None = None  # market cap; auto-sourced from entity_id if omitted
    equity_volatility: float | None = None  # annualized equity vol; auto-sourced if omitted
    total_debt: float | None = None  # if omitted, resolved from entity_id
    entity_id: uuid.UUID | None = None
    risk_free_rate: float = 0.045
    horizon: float = 1.0
    # Optional extra drivers folded into the composite score
    altman_z: float | None = None
    leverage_ratio: float | None = None
    interest_coverage: float | None = None
    cash_ratio: float | None = None


class MertonComputeResponse(BaseModel):
    """Result of an on-demand Merton + composite credit-risk computation."""
    entity_id: uuid.UUID | None = None
    calculation_date: date
    merton: MertonModelResponse
    composite_score: float | None = None
    implied_rating: str | None = None
    credit_zone: str | None = None
    key_drivers: list[KeyDriverResponse] = []
    total_debt_used: float | None = None
    risk_free_rate_used: float
