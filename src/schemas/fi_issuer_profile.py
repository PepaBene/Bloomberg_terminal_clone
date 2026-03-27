"""Pydantic schemas for E14 Issuer FI Profile endpoints."""

from __future__ import annotations

from pydantic import BaseModel


class MaturityWallItem(BaseModel):
    year: int
    amount_maturing: float
    pct_of_total: float
    bond_count: int


class MaturityWallResponse(BaseModel):
    entity_id: str
    maturity_wall: list[MaturityWallItem]
    total_outstanding: float
    years_forward: int


class DebtStackItem(BaseModel):
    seniority: str
    total_outstanding: float
    pct_of_total: float
    avg_coupon: float
    avg_maturity_years: float
    bond_count: int


class DebtStackResponse(BaseModel):
    entity_id: str
    debt_stack: list[DebtStackItem]
    total_outstanding: float


class IssuerFIProfileResponse(BaseModel):
    entity_id: str
    entity_name: str | None = None
    total_debt_outstanding: float
    bond_count: int
    weighted_avg_coupon: float
    weighted_avg_maturity_years: float
    maturity_wall: list[MaturityWallItem]
    debt_stack: list[DebtStackItem]
    refinancing_risk_score: float | None = None
    refinancing_risk_assessment: str | None = None


class RefinancingRiskResponse(BaseModel):
    entity_id: str
    score: float
    assessment: str
    maturity_wall_pct_2y: float
    current_spread_bps: float | None = None
