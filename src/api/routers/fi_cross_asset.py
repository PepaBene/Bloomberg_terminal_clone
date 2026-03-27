"""Pillar 2 FI Supplement — Part 7: Cross-Asset Divergence Signals API endpoints."""

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_session
from src.engines.e15_cross_asset import (
    compute_cross_asset_regime,
    compute_equity_exposure_adjustment,
    detect_divergence_signals,
)
from src.models.entity import Entity
from src.schemas.fi_cross_asset import (
    CrossAssetRegimeResponse,
    DivergenceSignal,
    DivergenceSignalsResponse,
    EquityExposureResponse,
    RegimeFactors,
)

router = APIRouter(prefix="/v2/analytics", tags=["FI Cross-Asset Signals"])


# ── 1. GET /cross-asset/divergence-signals ────────────────────────────


@router.get(
    "/cross-asset/divergence-signals",
    response_model=DivergenceSignalsResponse,
)
async def get_divergence_signals(
    # Equity parameters
    return_3m: float = Query(0.0, description="3-month equity return (decimal)"),
    return_6m: float = Query(0.0, description="6-month equity return (decimal)"),
    pe_ratio: Optional[float] = Query(None, description="P/E ratio"),
    pe_percentile: Optional[float] = Query(None, description="PE percentile vs history (0-100)"),
    volatility: Optional[float] = Query(None, description="Annualized equity vol (decimal)"),
    # Bond parameters
    spread_bps: float = Query(200.0, description="Credit spread in bps"),
    spread_change_3m_bps: float = Query(0.0, description="3-month spread change in bps"),
    spread_percentile: float = Query(50.0, description="Spread percentile vs history (0-100)"),
    ytw: Optional[float] = Query(None, description="Yield to worst"),
    # Rating parameters
    rating_numeric: Optional[int] = Query(None, description="Rating numeric (1=AAA to 22=D)"),
    outlook: Optional[str] = Query(None, description="Rating outlook"),
    watch_status: Optional[str] = Query(None, description="Watch status"),
    # Curve parameters
    slope_2s10s: Optional[float] = Query(None, description="2s10s slope (decimal)"),
    is_inverted: Optional[bool] = Query(None, description="Whether curve is inverted"),
):
    """Detect cross-asset divergence signals from provided market data."""
    equity_data = {
        "return_3m": return_3m,
        "return_6m": return_6m,
        "pe_ratio": pe_ratio,
        "pe_percentile": pe_percentile,
        "volatility": volatility,
    }
    bond_data = {
        "spread_bps": spread_bps,
        "spread_change_3m_bps": spread_change_3m_bps,
        "spread_percentile": spread_percentile,
        "ytw": ytw,
    }
    rating_data = {
        "rating_numeric": rating_numeric,
        "outlook": outlook,
        "watch_status": watch_status,
    }
    curve_data = {
        "slope_2s10s": slope_2s10s,
        "is_inverted": is_inverted,
    }

    signals = detect_divergence_signals(equity_data, bond_data, rating_data, curve_data)

    return DivergenceSignalsResponse(
        signals=[
            DivergenceSignal(
                signal_type=s["signal_type"],
                description=s["description"],
                severity=s["severity"],
                actionability=s["actionability"],
                confidence=s["confidence"],
            )
            for s in signals
        ],
        total=len(signals),
    )


# ── 2. GET /entities/{entity_id}/cross-asset-signals ─────────────────


@router.get(
    "/entities/{entity_id}/cross-asset-signals",
    response_model=DivergenceSignalsResponse,
)
async def get_entity_cross_asset_signals(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    # Equity params (would normally come from DB; accept overrides)
    return_3m: float = Query(0.0, description="3-month equity return (decimal)"),
    return_6m: float = Query(0.0, description="6-month equity return (decimal)"),
    pe_percentile: Optional[float] = Query(None, description="PE percentile vs history (0-100)"),
    volatility: Optional[float] = Query(None, description="Annualized equity vol (decimal)"),
    # Bond params
    spread_bps: float = Query(200.0, description="Credit spread in bps"),
    spread_change_3m_bps: float = Query(0.0, description="3-month spread change in bps"),
    spread_percentile: float = Query(50.0, description="Spread percentile vs history (0-100)"),
    # Curve params
    slope_2s10s: Optional[float] = Query(None, description="2s10s slope (decimal)"),
    is_inverted: Optional[bool] = Query(None, description="Whether curve is inverted"),
):
    """Get cross-asset divergence signals for a specific entity."""
    # Verify entity exists
    query = select(Entity).where(Entity.entity_id == entity_id)
    result = await session.execute(query)
    entity = result.scalars().unique().one_or_none()
    if entity is None:
        raise HTTPException(status_code=404, detail=f"Entity {entity_id} not found")

    equity_data = {
        "return_3m": return_3m,
        "return_6m": return_6m,
        "pe_percentile": pe_percentile,
        "volatility": volatility,
    }
    bond_data = {
        "spread_bps": spread_bps,
        "spread_change_3m_bps": spread_change_3m_bps,
        "spread_percentile": spread_percentile,
    }
    curve_data = {
        "slope_2s10s": slope_2s10s,
        "is_inverted": is_inverted,
    }

    # Look up rating data for entity if available
    from src.models.credit_rating import CurrentCreditRating
    rating_stmt = (
        select(CurrentCreditRating)
        .where(CurrentCreditRating.entity_id == entity_id)
        .limit(1)
    )
    rating_result = await session.execute(rating_stmt)
    rating_row = rating_result.scalars().first()
    rating_data = None
    if rating_row is not None:
        rating_data = {
            "rating_numeric": rating_row.rating_numeric if hasattr(rating_row, "rating_numeric") else None,
            "outlook": getattr(rating_row, "outlook", None),
            "watch_status": getattr(rating_row, "watch_status", None),
        }

    signals = detect_divergence_signals(equity_data, bond_data, rating_data=rating_data, curve_data=curve_data)

    return DivergenceSignalsResponse(
        signals=[
            DivergenceSignal(
                signal_type=s["signal_type"],
                description=s["description"],
                severity=s["severity"],
                actionability=s["actionability"],
                confidence=s["confidence"],
                entity_id=str(entity_id),
                entity_name=entity.legal_name,
            )
            for s in signals
        ],
        total=len(signals),
    )


# ── 3. GET /cross-asset/regime ───────────────────────────────────────


@router.get(
    "/cross-asset/regime",
    response_model=CrossAssetRegimeResponse,
)
async def get_cross_asset_regime(
    equity_vol: float = Query(0.15, description="Annualized equity volatility (decimal)"),
    credit_spread: float = Query(200.0, description="Credit spread in bps"),
    rate_level: float = Query(0.04, description="10Y yield (decimal)"),
    curve_slope: float = Query(0.01, description="2s10s spread (decimal)"),
):
    """Classify the current cross-asset regime."""
    result = compute_cross_asset_regime(
        equity_vol=equity_vol,
        credit_spread=credit_spread,
        rate_level=rate_level,
        curve_slope=curve_slope,
    )

    return CrossAssetRegimeResponse(
        regime=result["regime"],
        confidence=result["confidence"],
        factors=RegimeFactors(**result["factors"]),
    )


# ── 4. GET /cross-asset/regime/equity-exposure ───────────────────────


@router.get(
    "/cross-asset/regime/equity-exposure",
    response_model=EquityExposureResponse,
)
async def get_equity_exposure_suggestion(
    equity_vol: float = Query(0.15, description="Annualized equity volatility (decimal)"),
    credit_spread: float = Query(200.0, description="Credit spread in bps"),
    rate_level: float = Query(0.04, description="10Y yield (decimal)"),
    curve_slope: float = Query(0.01, description="2s10s spread (decimal)"),
    current_equity_weight: float = Query(0.60, ge=0.0, le=1.0, description="Current equity weight"),
):
    """Get suggested equity exposure adjustment based on cross-asset regime."""
    # First determine regime
    regime_result = compute_cross_asset_regime(
        equity_vol=equity_vol,
        credit_spread=credit_spread,
        rate_level=rate_level,
        curve_slope=curve_slope,
    )

    # Then compute exposure adjustment (no entity-specific signals here)
    exposure_result = compute_equity_exposure_adjustment(
        regime=regime_result["regime"],
        signals=[],
        current_equity_weight=current_equity_weight,
    )

    return EquityExposureResponse(
        current_weight=current_equity_weight,
        suggested_weight=exposure_result["suggested_weight"],
        adjustment_pct=exposure_result["adjustment_pct"],
        reason=exposure_result["reason"],
        confidence=exposure_result["confidence"],
        regime=regime_result["regime"],
    )
