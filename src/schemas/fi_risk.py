"""Pillar 2 FI Supplement -- Part 5: FI Risk Analytics schemas."""

from __future__ import annotations

from pydantic import BaseModel


class PortfolioRiskPosition(BaseModel):
    cusip: str | None = None
    market_value: float
    modified_duration: float
    convexity: float = 0.0
    spread_duration: float | None = None
    rating_numeric: int | None = None
    seniority: str = "SENIOR_UNSECURED"
    is_investment_grade: bool | None = None


class PortfolioRiskRequest(BaseModel):
    positions: list[PortfolioRiskPosition]


class PositionPnl(BaseModel):
    cusip: str | None = None
    pnl: float
    pnl_pct: float


class PortfolioRiskResponse(BaseModel):
    portfolio_dv01: float
    total_market_value: float
    credit_distribution: dict
    expected_loss: float
    expected_loss_pct: float
    position_count: int


class RateScenarioRequest(BaseModel):
    positions: list[PortfolioRiskPosition]
    rate_shift_bps: float


class ScenarioPnlResponse(BaseModel):
    total_pnl: float
    total_pnl_pct: float
    shift_bps: float
    by_position: list[PositionPnl]


class SpreadScenarioRequest(BaseModel):
    positions: list[PortfolioRiskPosition]
    spread_shift_bps: float


class BondRiskMetricsResponse(BaseModel):
    cusip: str
    dv01: float
    rate_pnl_100bps: float
    spread_pnl_100bps: float
    expected_loss: float | None = None
    pd_1y: float | None = None
    lgd: float | None = None
    rating_numeric: int | None = None
