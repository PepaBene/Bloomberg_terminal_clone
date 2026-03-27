"""Pydantic schemas for Pillar 3 Governance Intelligence (proxy, compensation, board)."""

from pydantic import BaseModel
from uuid import UUID
from datetime import date


class ProxyFilingResponse(BaseModel):
    id: UUID
    entity_id: UUID
    fiscal_year: int
    filing_date: date
    meeting_date: date | None = None
    filing_url: str | None = None

    model_config = {"from_attributes": True}


class ExecutiveCompensationResponse(BaseModel):
    person_name: str
    role: str
    fiscal_year: int
    total_compensation: float | None = None
    base_salary: float | None = None
    bonus: float | None = None
    stock_awards: float | None = None
    option_awards: float | None = None
    yoy_change_pct: float | None = None
    pay_ratio_to_median: float | None = None

    model_config = {"from_attributes": True}


class BoardMemberResponse(BaseModel):
    person_name: str
    is_independent: bool
    is_chair: bool
    tenure_years: int | None = None
    age: int | None = None
    gender: str | None = None
    committees: list | None = None
    expertise_areas: list | None = None

    model_config = {"from_attributes": True}


class ShareholderProposalResponse(BaseModel):
    proposal_number: int
    topic: str | None = None
    description: str | None = None
    management_recommendation: str | None = None
    vote_for_pct: float | None = None
    vote_against_pct: float | None = None
    passed: bool | None = None

    model_config = {"from_attributes": True}


class GovernanceRedFlagResponse(BaseModel):
    flag: str
    severity: str
    detail: str
    weight: int


class GovernanceAssessmentResponse(BaseModel):
    entity_id: UUID
    assessment_date: date
    governance_score: int
    classification: str | None = None
    red_flags: list[GovernanceRedFlagResponse] = []
    board_independence_pct: float | None = None
    board_diversity_pct: float | None = None
    ceo_is_chair: bool = False

    model_config = {"from_attributes": True}
