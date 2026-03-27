"""Pydantic schemas for FI Screening, Rate Scenarios, and Sensitivity endpoints."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Bond Screening
# ---------------------------------------------------------------------------


class BondScreenFilterInput(BaseModel):
    """A single filter criterion for bond screening."""

    field: str
    op: str = "GTE"
    value: float | str | None = None
    value2: float | str | None = None


class BondScreenRequest(BaseModel):
    """Request body for the bond screening endpoint."""

    filters: list[BondScreenFilterInput] = []
    sort_by: str = "spread_bps"
    ascending: bool = False
    limit: int = 50


class BondScreenResult(BaseModel):
    """A single bond in the screening results."""

    cusip: str
    name: str | None = None
    coupon_rate: float | None = None
    maturity_date: date | None = None
    spread_bps: int | None = None
    yield_to_worst: float | None = None
    liquidity_score: int | None = None
    is_investment_grade: bool | None = None


class BondScreenResponse(BaseModel):
    """Response for the bond screening endpoint."""

    results: list[BondScreenResult]
    total: int


# ---------------------------------------------------------------------------
# Rate Scenarios
# ---------------------------------------------------------------------------


class RateScenarioInfo(BaseModel):
    """Summary of a single rate shock scenario."""

    scenario_id: str
    label: str
    rate_shift_bps: int
    spread_impact_ig_bps: int
    spread_impact_hy_bps: int
    description: str


class RateScenarioListResponse(BaseModel):
    """Response listing all available rate scenarios."""

    scenarios: list[RateScenarioInfo]


class PortfolioPositionInput(BaseModel):
    """A single position in a portfolio for stress testing."""

    cusip: str | None = None
    market_value: float
    modified_duration: float
    convexity: float = 0.0
    spread_duration: float | None = None
    is_investment_grade: bool = True


class RateScenarioPortfolioRequest(BaseModel):
    """Request body for applying a rate scenario to a portfolio."""

    positions: list[PortfolioPositionInput]


class ScenarioPositionPnl(BaseModel):
    """P&L breakdown for a single position."""

    cusip: str | None = None
    total_pnl: float
    rate_pnl: float
    spread_pnl: float


class RateScenarioResponse(BaseModel):
    """Response from applying a rate scenario."""

    scenario_id: str
    scenario_label: str
    total_pnl: float
    total_pnl_pct: float
    rate_pnl: float
    spread_pnl: float
    by_position: list[ScenarioPositionPnl]


# ---------------------------------------------------------------------------
# Sensitivity
# ---------------------------------------------------------------------------


class SensitivityRequest(BaseModel):
    """Request body for the sensitivity table endpoint."""

    base_price: float = 100.0
    modified_duration: float
    convexity: float = 0.0
    var1_name: str = "yield_shift_bps"
    var1_range: list[float] | None = None
    var2_name: str | None = None
    var2_range: list[float] | None = None


class SensitivityCell(BaseModel):
    """A single cell in the sensitivity table."""

    var1_value: float
    var2_value: float | None = None
    price: float
    price_change_pct: float


class SensitivityResponse(BaseModel):
    """Response for the sensitivity table endpoint."""

    var1_name: str
    var2_name: str | None = None
    results: list[SensitivityCell]


# ---------------------------------------------------------------------------
# Scenario Analysis (multi-variable shift)
# ---------------------------------------------------------------------------


class ScenarioAnalysisRequest(BaseModel):
    """Request body for multi-variable scenario shift."""

    positions: list[PortfolioPositionInput]
    yield_shift_bps: float = 0.0
    spread_shift_bps: float = 0.0
    rating_migration_notches: int = 0


class ScenarioAnalysisResponse(BaseModel):
    """Response from the multi-variable scenario shift."""

    total_pnl: float
    total_pnl_pct: float
    yield_impact: float
    spread_impact: float
    migration_impact: float
    position_count: int
