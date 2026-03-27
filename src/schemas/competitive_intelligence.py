"""Pydantic schemas for Pillar 3 Phase 3A Competitive Intelligence endpoints."""

from typing import Any

from pydantic import BaseModel
from uuid import UUID
from datetime import date


class MoatAssessmentResponse(BaseModel):
    id: UUID
    entity_id: UUID
    as_of_date: date
    moat_width: str
    moat_stability: str | None = None
    moat_score: float | None = None
    roic_above_wacc_years: int | None = None
    roic_consistency_score: float | None = None
    gross_margin_stability: float | None = None
    gross_margin_10y_std: float | None = None
    market_share_trend: str | None = None
    market_share_5y_delta: float | None = None
    customer_retention_proxy: float | None = None
    cost_advantage_score: float | None = None
    network_effects_score: float | None = None
    switching_costs_score: float | None = None
    intangible_assets_score: float | None = None
    efficient_scale_score: float | None = None
    dominant_moat_source: str | None = None
    moat_evidence: dict | None = None
    ai_summary: str | None = None
    ai_enabled: bool = False

    model_config = {"from_attributes": True}


class MoatHistoryEntry(BaseModel):
    id: UUID
    entity_id: UUID
    period_end_date: date
    moat_width: str | None = None
    moat_score: float | None = None
    roic: float | None = None
    wacc: float | None = None
    roic_wacc_spread: float | None = None
    gross_margin: float | None = None
    market_share_est: float | None = None

    model_config = {"from_attributes": True}


class MoatHistoryResponse(BaseModel):
    entity_id: UUID
    history: list[MoatHistoryEntry] = []


class ConcentrationRiskResponse(BaseModel):
    id: UUID
    entity_id: UUID
    as_of_date: date
    customer_top1_pct: float | None = None
    customer_top5_pct: float | None = None
    customer_top10_pct: float | None = None
    customer_concentration_risk: str | None = None
    customer_details: dict | None = None
    supplier_single_source_count: int | None = None
    supplier_critical_count: int | None = None
    supplier_geographic_concentration: dict | None = None
    supplier_concentration_risk: str | None = None
    supplier_details: dict | None = None
    geographic_revenue_breakdown: dict | None = None
    geographic_top1_pct: float | None = None
    geographic_hhi: float | None = None
    fx_exposure_score: float | None = None
    geographic_concentration_risk: str | None = None
    overall_concentration_risk: str | None = None
    overall_risk_score: float | None = None

    model_config = {"from_attributes": True}


class PeerComparisonResponse(BaseModel):
    entity_id: UUID
    entity_name: str | None = None
    market_share_est_pct: float | None = None
    market_share_rank: int | None = None
    revenue_growth_vs_peers: float | None = None
    margin_vs_peers: float | None = None
    roic_vs_peers: float | None = None

    model_config = {"from_attributes": True}


class CompetitiveLandscapeResponse(BaseModel):
    id: UUID
    entity_id: UUID
    gics_code: str
    as_of_date: date
    peer_group: Any | None = None
    market_share_est_pct: float | None = None
    market_share_rank: int | None = None
    revenue_growth_vs_peers: float | None = None
    margin_vs_peers: float | None = None
    roic_vs_peers: float | None = None
    valuation_vs_peers: Any | None = None
    share_gainer: bool = False
    value_chain_position: str | None = None
    competitive_advantages: Any | None = None
    competitive_threats: Any | None = None

    model_config = {"from_attributes": True}
