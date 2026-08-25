"""Pydantic schemas for Pillar 4 Phase 3: Portfolio Risk Management endpoints."""

from datetime import date
from uuid import UUID

from pydantic import BaseModel, Field


# ── VaR ─────────────────────────────────────────────────────────────


class VaRResponse(BaseModel):
    """Portfolio Value-at-Risk summary."""

    portfolio_id: UUID
    snapshot_date: date
    var_1d_95: float | None = None
    var_1d_99: float | None = None
    var_10d_95: float | None = None
    var_10d_99: float | None = None
    undiversified_var: float | None = None
    diversification_ratio: float | None = None
    portfolio_nav: float | None = None
    method: str | None = None

    model_config = {"from_attributes": True}


class VaRDecompositionResponse(BaseModel):
    """VaR decomposition into component, marginal, incremental."""

    portfolio_id: UUID
    snapshot_date: date
    marginal_var: dict | None = None
    component_var: dict | None = None
    incremental_var: dict | None = None


# ── Concentration ───────────────────────────────────────────────────


class SectorConcentrationEntry(BaseModel):
    """Single sector concentration entry."""

    sector: str
    weight: float = 0.0
    benchmark_weight: float | None = None
    active_weight: float | None = None


class ConcentrationResponse(BaseModel):
    """Portfolio concentration analysis."""

    portfolio_id: UUID
    snapshot_date: date
    hhi_position: float | None = None
    hhi_sector: float | None = None
    hhi_industry: float | None = None
    largest_position_weight: float | None = None
    top_5_weight: float | None = None
    top_10_weight: float | None = None
    effective_num_positions: float | None = None
    concentration_classification: str | None = None
    sector_detail: list[SectorConcentrationEntry] = []
    geographic_detail: list[dict] = []
    flags: dict | None = None


# ── Factor Exposure ─────────────────────────────────────────────────


class FactorHistoryEntry(BaseModel):
    """Factor exposure at a point in time."""

    snapshot_date: date
    value_exposure: float | None = None
    growth_exposure: float | None = None
    momentum_exposure: float | None = None
    quality_exposure: float | None = None
    size_exposure: float | None = None
    low_vol_exposure: float | None = None


class FactorExposureResponse(BaseModel):
    """Current factor exposures for a portfolio."""

    portfolio_id: UUID
    snapshot_date: date
    value_exposure: float | None = None
    growth_exposure: float | None = None
    momentum_exposure: float | None = None
    quality_exposure: float | None = None
    size_exposure: float | None = None
    low_vol_exposure: float | None = None
    benchmark_value: float | None = None
    benchmark_growth: float | None = None
    benchmark_momentum: float | None = None
    benchmark_quality: float | None = None
    benchmark_size: float | None = None
    benchmark_low_vol: float | None = None
    active_exposures: dict | None = None
    factor_contributions: dict | None = None
    unintended_flags: dict | None = None


# ── Stress Testing ──────────────────────────────────────────────────


class StressTestRequest(BaseModel):
    """Request body for running a stress test."""

    scenario_name: str
    shocks: dict | None = None


class StressScenarioResponse(BaseModel):
    """Available stress scenario descriptor."""

    scenario_name: str
    scenario_type: str
    description: str | None = None


class StressTestResponse(BaseModel):
    """Result of a stress test run."""

    portfolio_id: UUID
    snapshot_date: date
    scenario_name: str
    scenario_type: str
    total_pnl_dollar: float | None = None
    total_pnl_percent: float | None = None
    max_drawdown_pct: float | None = None
    recovery_time_months: float | None = None
    per_position_pnl: dict | None = None
    worst_positions: dict | None = None
    scenario_params: dict | None = None


# ── Risk Dashboard ──────────────────────────────────────────────────


class RiskDashboardResponse(BaseModel):
    """Combined risk dashboard: VaR + concentration + factors summary."""

    portfolio_id: UUID
    snapshot_date: date | None = None
    var_summary: VaRResponse | None = None
    concentration_summary: ConcentrationResponse | None = None
    factor_summary: FactorExposureResponse | None = None


# ── What-If ─────────────────────────────────────────────────────────


class WhatIfRequest(BaseModel):
    """Named-scenario what-if request, matching the existing frontend
    What-If Analysis panel (frontend/src/pages/portfolio/PortfolioDetail.tsx)."""

    scenario: str


class WhatIfResponse(BaseModel):
    """Named-scenario what-if projection.

    Field names/casing match the frontend's pre-existing (previously
    unservable) contract exactly -- ``projectedNavChange``/``projectedPnl``,
    not this codebase's usual snake_case -- so the panel starts working
    without a frontend change.
    """

    projected_nav_change: float | None = Field(default=None, alias="projectedNavChange")
    projected_pnl: float | None = Field(default=None, alias="projectedPnl")

    model_config = {"populate_by_name": True}
