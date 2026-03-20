"""Pillar 2: Scenario & Sensitivity schemas (Spec §10)."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# 2D Sensitivity
# ---------------------------------------------------------------------------

class Sensitivity2DRequest(BaseModel):
    security_id: UUID
    row_variable: str
    col_variable: str
    row_min: float | None = None
    row_max: float | None = None
    col_min: float | None = None
    col_max: float | None = None
    steps: int = Field(default=7, ge=3, le=15)
    method: str = "FCFF"


class Sensitivity2DResponse(BaseModel):
    row_variable: str
    col_variable: str
    row_values: list[float]
    col_values: list[float]
    grid: list[list[float | None]]
    base_case_value: float | None = None
    current_price: float | None = None


# ---------------------------------------------------------------------------
# 3D Sensitivity
# ---------------------------------------------------------------------------

class Sensitivity3DRequest(BaseModel):
    security_id: UUID
    fixed_variable: str
    fixed_values: list[float] = Field(min_length=2, max_length=5)
    row_variable: str
    col_variable: str
    steps: int = Field(default=7, ge=3, le=15)
    method: str = "FCFF"


class Sensitivity3DTable(BaseModel):
    fixed_value: float
    base_case_value: float | None = None
    row_values: list[float]
    col_values: list[float]
    grid: list[list[float | None]]


class Sensitivity3DResponse(BaseModel):
    fixed_variable: str
    fixed_values: list[float]
    row_variable: str
    col_variable: str
    tables: list[Sensitivity3DTable]
    current_price: float | None = None


# ---------------------------------------------------------------------------
# Tornado
# ---------------------------------------------------------------------------

class TornadoRequest(BaseModel):
    security_id: UUID
    variables: list[str] | None = None
    swing_pct: float = Field(default=0.20, ge=0.01, le=1.0)
    method: str = "FCFF"


class TornadoBar(BaseModel):
    variable: str
    base_value: float
    low_value: float
    high_value: float
    low_output: float | None = None
    high_output: float | None = None
    impact_range: float


class TornadoResponse(BaseModel):
    base_case_value: float
    current_price: float | None = None
    bars: list[TornadoBar]


# ---------------------------------------------------------------------------
# Shock
# ---------------------------------------------------------------------------

class ShockRequest(BaseModel):
    security_id: UUID
    shock_vector: dict[str, float]
    method: str = "FCFF"


class CustomShockRequest(BaseModel):
    security_id: UUID
    name: str
    description: str | None = None
    shock_vector: dict[str, float]
    method: str = "FCFF"


class IndividualImpact(BaseModel):
    variable: str
    delta: float
    base_value: float
    shocked_value_individual: float | None = None
    impact: float | None = None


class ShockResponse(BaseModel):
    base_case_value: float
    shocked_value: float | None = None
    impact_pct: float | None = None
    current_price: float | None = None
    individual_impacts: list[IndividualImpact]


# ---------------------------------------------------------------------------
# Pre-built Scenario Summaries
# ---------------------------------------------------------------------------

class PrebuiltScenarioSummary(BaseModel):
    name: str
    label: str
    description: str | None = None
    shocks: dict[str, float]


# ---------------------------------------------------------------------------
# Breakeven
# ---------------------------------------------------------------------------

class BreakevenRequest(BaseModel):
    security_id: UUID
    variable: str
    target_price: float
    search_min: float | None = None
    search_max: float | None = None
    tolerance: float = 0.50
    method: str = "FCFF"


class BreakevenResponse(BaseModel):
    variable: str
    target_price: float
    breakeven_value: float | None = None
    converged: bool
    iterations: int
    base_value: float | None = None


# ---------------------------------------------------------------------------
# Portfolio Scenario
# ---------------------------------------------------------------------------

class PortfolioPosition(BaseModel):
    security_id: UUID
    weight: float


class PortfolioScenarioRequest(BaseModel):
    positions: list[PortfolioPosition]
    shock_vector: dict[str, float]
    method: str = "FCFF"


class PortfolioPositionImpact(BaseModel):
    security_id: UUID
    weight: float
    base_case_value: float | None = None
    shocked_value: float | None = None
    impact: float | None = None


class PortfolioScenarioResponse(BaseModel):
    total_base_value: float
    total_shocked_value: float
    total_impact: float
    impact_pct: float | None = None
    positions: list[PortfolioPositionImpact]
