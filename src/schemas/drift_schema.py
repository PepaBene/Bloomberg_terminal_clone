"""Pydantic schemas for Pillar 4 Phase 3: Drift monitoring endpoints."""

from datetime import date
from uuid import UUID

from pydantic import BaseModel


class PositionDriftEntry(BaseModel):
    """Drift detail for a single position."""

    ticker: str
    target_weight: float = 0.0
    current_weight: float = 0.0
    drift_pct: float = 0.0


class SectorDriftEntry(BaseModel):
    """Drift detail for a sector."""

    sector: str
    target_weight: float = 0.0
    current_weight: float = 0.0
    drift_pct: float = 0.0


class DriftResponse(BaseModel):
    """Current portfolio drift analysis."""

    portfolio_id: UUID
    snapshot_date: date
    total_drift_pct: float | None = None
    max_position_drift_pct: float | None = None
    max_sector_drift_pct: float | None = None
    drift_classification: str | None = None
    rebalance_needed: bool | None = None
    position_drifts: list[PositionDriftEntry] = []
    sector_drifts: list[SectorDriftEntry] = []
    target_allocation: dict | None = None


class RebalanceSuggestionResponse(BaseModel):
    """Rebalancing suggestions for a portfolio."""

    portfolio_id: UUID
    rebalance_needed: bool = False
    total_drift_pct: float | None = None
    suggestions: list[dict] = []


class DriftAlertResponse(BaseModel):
    """Drift alert notification."""

    portfolio_id: UUID
    alert_type: str = "DRIFT"
    drift_classification: str | None = None
    total_drift_pct: float | None = None
    message: str | None = None
