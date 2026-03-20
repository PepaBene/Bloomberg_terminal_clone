"""Pillar 2: Risk Analytics schemas (Spec §7)."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# VaR
# ---------------------------------------------------------------------------

class VaRResponse(BaseModel):
    """Value at Risk summary for a single security."""
    security_id: UUID
    calculation_date: date | None = None
    historical_var: dict[str, float | None] = {}
    parametric_var: dict[str, float | None] = {}
    expected_shortfall: dict[str, float | None] = {}
    volatility: dict[str, float | None] = {}
    max_drawdown: float | None = None


class PortfolioVaRRequest(BaseModel):
    """Portfolio VaR request with position weights."""
    positions: list[dict]  # [{security_id, weight}]
    confidence: float = 0.95
    holding_period_days: int = 1


# ---------------------------------------------------------------------------
# Stress Testing
# ---------------------------------------------------------------------------

class StressScenarioSummary(BaseModel):
    """Summary of an available stress scenario."""
    name: str
    label: str
    scenario_type: str
    description: str | None = None


class StressTestRequest(BaseModel):
    """Run a stress test on a security."""
    security_id: UUID
    scenario_name: str
    shock_pct: float | None = None


class StressTestScenarioResult(BaseModel):
    """Result of a single stress scenario."""
    scenario_name: str
    scenario_type: str
    pnl_percent: float | None = None
    max_drawdown: float | None = None
    worst_day: float | None = None
    best_day: float | None = None


class StressTestResponse(BaseModel):
    """Full stress test results for a security."""
    security_id: UUID
    scenarios: list[StressTestScenarioResult] = []


# ---------------------------------------------------------------------------
# Factor Exposures
# ---------------------------------------------------------------------------

class FactorDetail(BaseModel):
    """Single factor exposure detail."""
    z_score: float | None = None
    raw_value: float | None = None
    percentile_rank: float | None = None


class FactorExposureResponse(BaseModel):
    """Style-factor exposure summary for a security."""
    security_id: UUID
    calculation_date: date | None = None
    factors: dict[str, FactorDetail] = {}


# ---------------------------------------------------------------------------
# Fundamental Risk
# ---------------------------------------------------------------------------

class FundamentalRiskResponse(BaseModel):
    """Fundamental risk dashboard for a security."""
    security_id: UUID
    leverage_risk: dict[str, float | None] = {}
    earnings_risk: dict[str, float | None] = {}
    liquidity_risk: dict[str, float | None] = {}
    leverage_score: float | None = None


class LeverageRiskResponse(BaseModel):
    """Detailed leverage risk breakdown."""
    security_id: UUID
    net_debt_to_ebitda: float | None = None
    interest_coverage: float | None = None
    debt_to_equity: float | None = None
    current_ratio: float | None = None
    leverage_score: float | None = None


class LiquidityRiskResponse(BaseModel):
    """Detailed liquidity risk metrics."""
    security_id: UUID
    avg_volume_20d: float | None = None
    avg_volume_60d: float | None = None
    bid_ask_proxy: float | None = None
    amihud_illiquidity: float | None = None


# ---------------------------------------------------------------------------
# Volatility & Beta
# ---------------------------------------------------------------------------

class VolatilityResponse(BaseModel):
    """Historical volatility metrics."""
    security_id: UUID
    annualized_volatility: float | None = None
    daily_volatility: float | None = None
    skewness: float | None = None
    kurtosis: float | None = None
    max_drawdown: float | None = None


class BetaResponse(BaseModel):
    """Beta calculation result."""
    security_id: UUID
    beta: float | None = None
    beta_blume_adjusted: float | None = None
    r_squared: float | None = None
    benchmark: str = "SPY"


# ---------------------------------------------------------------------------
# Drawdown
# ---------------------------------------------------------------------------

class DrawdownResponse(BaseModel):
    """Max drawdown analysis."""
    security_id: UUID
    max_drawdown: float | None = None
    annualized_volatility: float | None = None
    risk_level: str | None = None
