"""Pydantic schemas for Pillar 4 Phase 1: Portfolio Management endpoints."""

from pydantic import BaseModel
from uuid import UUID
from datetime import date, datetime
from decimal import Decimal


class PortfolioCreateRequest(BaseModel):
    portfolio_name: str
    portfolio_type: str = "REAL"
    benchmark_id: str | None = None
    inception_date: date
    initial_cash: Decimal
    tags: dict | None = None
    notes: str | None = None


class PortfolioResponse(BaseModel):
    id: UUID
    user_id: str
    portfolio_name: str
    portfolio_type: str
    benchmark_id: str | None = None
    inception_date: date
    base_currency: str
    initial_cash: float
    current_cash: float
    status: str
    tags: dict | None = None
    notes: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class PortfolioListResponse(BaseModel):
    portfolios: list[PortfolioResponse]


class PortfolioUpdateRequest(BaseModel):
    portfolio_name: str | None = None
    benchmark_id: str | None = None
    status: str | None = None
    tags: dict | None = None
    notes: str | None = None
