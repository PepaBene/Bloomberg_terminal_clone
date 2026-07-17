"""Pydantic schemas for Pillar 3 Phase 2: Deep Company Intelligence."""

from pydantic import BaseModel
from uuid import UUID


class CompanyIntelligenceResponse(BaseModel):
    entity_id: UUID
    business_model: dict | None = None
    capital_allocation: dict | None = None
    management_quality: dict | None = None
    balance_sheet_risk: dict | None = None
    governance_score: float | None = None
    ai_summary: str | None = None


class BusinessModelResponse(BaseModel):
    entity_id: UUID
    revenue_quality: dict | None = None
    unit_economics: dict | None = None
    scaling: dict | None = None
    durability: dict | None = None
    ai_summary: str | None = None


class CapitalAllocationResponse(BaseModel):
    entity_id: UUID
    fcf_conversion: float | None = None
    working_capital: dict | None = None
    roic_vs_wacc: dict | None = None
    ma_discipline: dict | None = None
    buyback_effectiveness: dict | None = None
    dividend_sustainability: dict | None = None
    overall_score: float | None = None


class BalanceSheetRiskResponse(BaseModel):
    entity_id: UUID
    leverage: dict | None = None
    liquidity: dict | None = None
    refinancing_risk_score: float | None = None
    z_score: float | None = None
    fi_profile: dict | None = None
    ai_summary: str | None = None


class ManagementQualityResponse(BaseModel):
    entity_id: UUID
    execution_score: float | None = None
    governance_score: float | None = None
    accounting_flags: list[dict] | None = None
    compensation_alignment: dict | None = None
    overall_score: float | None = None
    red_flags: list[dict] | None = None


# ── Previously-missing endpoints (real engines, computed on-the-fly from
# the same _assemble_fundamentals()/real signals the four responses above
# use -- no new persistence tables, these are cheap deterministic
# transforms recomputed per request) ───────────────────────────────────


class RevenueDriversResponse(BaseModel):
    entity_id: UUID
    drivers: list[dict] = []
    revenue_concentration_hhi: float | None = None
    total_revenue_yoy_growth_pct: float | None = None
    periods_analyzed: int = 0


class CostStructureResponse(BaseModel):
    entity_id: UUID
    items: list[dict] = []
    periods_analyzed: int = 0


class MarginAnalysisResponse(BaseModel):
    entity_id: UUID
    margins: list[dict] = []
    periods_analyzed: int = 0


class GrowthProfileResponse(BaseModel):
    entity_id: UUID
    growth_series: list[dict] = []
    periods_analyzed: int = 0


class OperatingLeverageResponse(BaseModel):
    entity_id: UUID
    avg_operating_leverage: float | None = None
    operating_leverage_stability: float | None = None
    operating_leverage_trend: list[dict] = []
    incremental_margin_trend: list[dict] = []


class QualityMetricsResponse(BaseModel):
    entity_id: UUID
    piotroski_f_score: float | None = None
    altman_z_score: float | None = None
    beneish_m_score: float | None = None
    accruals_quality: float | None = None
    as_of_date: str | None = None


class RiskProfileResponse(BaseModel):
    entity_id: UUID
    credit_risk_score: float | None = None
    earnings_quality_risk_score: float | None = None
    market_risk_score: float | None = None
    overall_risk_score: float | None = None
    overall_risk_tier: str = "UNKNOWN"
    data_completeness: float = 0.0
    risk_factors: list[dict] = []


class WorkingCapitalResponse(BaseModel):
    entity_id: UUID
    working_capital: dict | None = None
    as_of_date: str | None = None
