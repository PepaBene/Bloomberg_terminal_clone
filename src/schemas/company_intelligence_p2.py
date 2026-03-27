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
