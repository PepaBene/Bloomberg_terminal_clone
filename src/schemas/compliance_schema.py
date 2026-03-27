"""Pydantic schemas for Pillar 4 Phase 3: Compliance endpoints."""

from datetime import date
from uuid import UUID

from pydantic import BaseModel


class ComplianceRuleCreateRequest(BaseModel):
    """Request body for creating a compliance rule."""

    rule_name: str
    rule_type: str
    rule_definition: dict
    threshold: float | None = None
    upper_threshold: float | None = None
    comparison: str = "LTE"
    severity: str = "WARNING"
    is_active: bool = True


class ComplianceRuleUpdateRequest(BaseModel):
    """Request body for updating a compliance rule."""

    rule_name: str | None = None
    rule_type: str | None = None
    rule_definition: dict | None = None
    threshold: float | None = None
    upper_threshold: float | None = None
    comparison: str | None = None
    severity: str | None = None
    is_active: bool | None = None


class ComplianceRuleResponse(BaseModel):
    """Response schema for a compliance rule."""

    rule_id: UUID
    portfolio_id: UUID
    rule_name: str
    rule_type: str
    rule_definition: dict
    threshold: float | None = None
    upper_threshold: float | None = None
    comparison: str
    severity: str | None = None
    is_active: bool | None = None

    model_config = {"from_attributes": True}


class ComplianceResultResponse(BaseModel):
    """Single compliance check result."""

    result_id: UUID
    portfolio_id: UUID
    rule_id: UUID
    check_date: date
    status: str
    current_value: float | None = None
    threshold_value: float | None = None
    breach_positions: dict | None = None
    notes: str | None = None


class ComplianceSummaryResponse(BaseModel):
    """Overall compliance summary for a portfolio."""

    portfolio_id: UUID
    total_rules: int = 0
    passing: int = 0
    warning: int = 0
    breaching: int = 0
    rules: list[ComplianceRuleResponse] = []
    latest_results: list[ComplianceResultResponse] = []


class PreTradeCheckRequest(BaseModel):
    """Request body for pre-trade compliance check."""

    ticker: str
    action: str  # BUY / SELL
    shares: float
    price: float


class PreTradeCheckResponse(BaseModel):
    """Result of a pre-trade compliance check."""

    portfolio_id: UUID
    ticker: str
    action: str
    approved: bool = True
    violations: list[dict] = []
    warnings: list[dict] = []
