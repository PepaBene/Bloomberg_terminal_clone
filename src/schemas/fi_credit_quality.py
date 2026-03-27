"""Pydantic schemas for E13 Credit Quality Engine endpoints."""

from __future__ import annotations

from pydantic import BaseModel


class OhlsonScoreComponents(BaseModel):
    size: float
    leverage: float
    liquidity: float
    cl_ratio: float
    roa: float
    cash_coverage: float
    oeneg: float
    ni_change: float
    debt_ratio: float


class OhlsonScoreResponse(BaseModel):
    o_score: float
    probability_of_default: float
    components: OhlsonScoreComponents


class CreditMomentumComponents(BaseModel):
    rating_momentum: float
    rating_weight: float
    score_momentum: float
    score_weight: float
    spread_momentum: float
    spread_weight: float


class CreditMomentumResponse(BaseModel):
    entity_id: str
    momentum_score: float
    signal: str  # IMPROVING, STABLE, DETERIORATING
    components: CreditMomentumComponents


class CreditQualityResponse(BaseModel):
    cusip: str
    o_score: float | None = None
    probability_of_default: float | None = None
    credit_momentum_score: float | None = None
    credit_momentum_signal: str | None = None
    fallen_angel_probability: float | None = None
    refinancing_risk_score: float | None = None
    refinancing_risk_assessment: str | None = None


class FallenAngelWatchItem(BaseModel):
    entity_id: str
    entity_name: str | None = None
    current_rating: str | None = None
    current_rating_numeric: int | None = None
    outlook: str | None = None
    watch_status: str | None = None
    fallen_angel_probability: float
    credit_momentum_signal: str | None = None


class FallenAngelWatchResponse(BaseModel):
    entities: list[FallenAngelWatchItem]
    total: int


class RefinancingRiskComponents(BaseModel):
    maturity_wall_score: float
    spread_stress_score: float
    fcf_coverage_score: float
    credit_direction_score: float


class RefinancingRiskResponse(BaseModel):
    entity_id: str
    score: float
    assessment: str  # LOW, MODERATE, ELEVATED, HIGH
    components: RefinancingRiskComponents
    maturity_wall_pct: float | None = None
    current_spread_bps: float | None = None
