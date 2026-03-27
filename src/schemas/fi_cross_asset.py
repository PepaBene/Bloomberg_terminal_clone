"""Pydantic schemas for E15 Cross-Asset Divergence Signals endpoints."""

from __future__ import annotations

from pydantic import BaseModel


class DivergenceSignal(BaseModel):
    signal_type: str
    description: str
    severity: str
    actionability: str
    confidence: float
    entity_id: str | None = None
    entity_name: str | None = None


class DivergenceSignalsResponse(BaseModel):
    signals: list[DivergenceSignal]
    total: int


class RegimeFactors(BaseModel):
    vol_signal: str
    credit_signal: str
    rate_signal: str
    curve_signal: str


class CrossAssetRegimeResponse(BaseModel):
    regime: str
    confidence: float
    factors: RegimeFactors


class EquityExposureResponse(BaseModel):
    current_weight: float
    suggested_weight: float
    adjustment_pct: float
    reason: str
    confidence: float
    regime: str
