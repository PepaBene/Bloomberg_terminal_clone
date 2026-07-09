"""Pillar 2 FI Supplement — Part 7: Cross-Asset Divergence Signals API endpoints."""

import math
import statistics
import uuid
from datetime import date, timedelta
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
from src.models.corporate_bond import BondEODPrice, CorporateBond
from src.models.credit_rating import CurrentCreditRating
from src.models.entity import Entity
from src.models.security import EODPrice, Security
from src.models.yield_curve import YieldCurveSnapshot
from src.schemas.fi_cross_asset import (
    CrossAssetRegimeResponse,
    DivergenceSignal,
    DivergenceSignalsResponse,
    EquityExposureResponse,
    RegimeFactors,
)

router = APIRouter(prefix="/v2/analytics", tags=["FI Cross-Asset Signals"])


# ── Real-data helpers for entity-scoped signals ─────────────────────


async def _entity_credit_metrics(
    session: AsyncSession, entity_id: uuid.UUID
) -> dict | None:
    """Derive real bond-market metrics for an issuer from its bonds' EOD prices.

    Returns {spread_bps, spread_change_3m_bps, spread_percentile} or None when
    the issuer has no G-spread observations.
    """
    bond_ids = (
        await session.execute(
            select(CorporateBond.bond_id).where(
                CorporateBond.issuer_entity_id == entity_id
            )
        )
    ).scalars().all()
    if not bond_ids:
        return None

    latest_spreads: list[float] = []
    change_vals: list[float] = []
    all_hist: list[float] = []

    for bid in bond_ids:
        rows = (
            await session.execute(
                select(BondEODPrice.price_date, BondEODPrice.g_spread_bps)
                .where(
                    BondEODPrice.bond_id == bid,
                    BondEODPrice.g_spread_bps.isnot(None),
                )
                .order_by(BondEODPrice.price_date.asc())
            )
        ).all()
        if not rows:
            continue
        spreads = [float(r[1]) for r in rows]
        all_hist.extend(spreads)
        latest_spreads.append(spreads[-1])
        latest_date = rows[-1][0]
        cutoff = latest_date - timedelta(days=90)
        past = [float(r[1]) for r in rows if r[0] <= cutoff]
        if past:
            change_vals.append(spreads[-1] - past[-1])

    if not latest_spreads:
        return None

    current = sum(latest_spreads) / len(latest_spreads)
    spread_change_3m = sum(change_vals) / len(change_vals) if change_vals else 0.0
    if all_hist:
        count_le = sum(1 for v in all_hist if v <= current)
        percentile = count_le / len(all_hist) * 100.0
    else:
        percentile = 50.0

    return {
        "spread_bps": current,
        "spread_change_3m_bps": spread_change_3m,
        "spread_percentile": percentile,
    }


async def _entity_equity_metrics(
    session: AsyncSession, entity_id: uuid.UUID
) -> dict | None:
    """Derive real equity metrics (returns, annualized vol) from the issuer's stock.

    Returns {return_3m, return_6m, volatility} (any may be None) or None when
    no equity price history is available.
    """
    sec_ids = (
        await session.execute(
            select(Security.security_id).where(
                Security.issuer_entity_id == entity_id,
                Security.asset_class == "EQUITY",
            )
        )
    ).scalars().all()
    if not sec_ids:
        return None

    cutoff = date.today() - timedelta(days=400)
    for sid in sec_ids:
        rows = (
            await session.execute(
                select(EODPrice.price_date, EODPrice.close)
                .where(
                    EODPrice.security_id == sid,
                    EODPrice.close.isnot(None),
                    EODPrice.price_date >= cutoff,
                )
                .order_by(EODPrice.price_date.asc())
            )
        ).all()
        pairs = [(r[0], float(r[1])) for r in rows if r[1] is not None and float(r[1]) > 0]
        if len(pairs) < 20:
            continue

        dates = [p[0] for p in pairs]
        closes = [p[1] for p in pairs]
        latest_close = closes[-1]
        latest_date = dates[-1]

        returns = [
            math.log(closes[i] / closes[i - 1])
            for i in range(1, len(closes))
            if closes[i - 1] > 0
        ]
        volatility = (
            statistics.pstdev(returns) * math.sqrt(252) if len(returns) > 1 else None
        )

        def _price_on_or_before(target: date) -> float | None:
            candidate = None
            for d, c in zip(dates, closes):
                if d <= target:
                    candidate = c
                else:
                    break
            return candidate

        p3 = _price_on_or_before(latest_date - timedelta(days=90))
        p6 = _price_on_or_before(latest_date - timedelta(days=180))
        return {
            "return_3m": (latest_close / p3 - 1.0) if p3 else None,
            "return_6m": (latest_close / p6 - 1.0) if p6 else None,
            "volatility": volatility,
        }

    return None


async def _latest_curve_data(session: AsyncSession) -> dict:
    """Latest treasury curve slope + inversion flag."""
    snapshot = (
        await session.execute(
            select(YieldCurveSnapshot)
            .where(YieldCurveSnapshot.curve_type == "TREASURY_NOMINAL")
            .order_by(YieldCurveSnapshot.curve_date.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if snapshot is None:
        return {"slope_2s10s": None, "is_inverted": None}
    return {
        "slope_2s10s": float(snapshot.spread_2s10s)
        if snapshot.spread_2s10s is not None
        else None,
        "is_inverted": snapshot.is_inverted,
    }


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
    # Overrides — all default to the entity's real data when not supplied.
    return_3m: Optional[float] = Query(None, description="Override 3-month equity return (decimal)"),
    return_6m: Optional[float] = Query(None, description="Override 6-month equity return (decimal)"),
    pe_percentile: Optional[float] = Query(None, description="PE percentile vs history (0-100)"),
    volatility: Optional[float] = Query(None, description="Override annualized equity vol (decimal)"),
    spread_bps: Optional[float] = Query(None, description="Override credit spread in bps"),
    spread_change_3m_bps: Optional[float] = Query(None, description="Override 3-month spread change in bps"),
    spread_percentile: Optional[float] = Query(None, description="Override spread percentile vs history (0-100)"),
    slope_2s10s: Optional[float] = Query(None, description="Override 2s10s slope (decimal)"),
    is_inverted: Optional[bool] = Query(None, description="Override curve inversion flag"),
):
    """Get cross-asset divergence signals for a specific entity.

    Equity metrics (returns, volatility) come from the issuer's stock EOD prices,
    credit metrics (spread level/change/percentile) from its bonds' EOD spreads,
    rating from the current-rating snapshot, and the curve from the latest
    treasury snapshot. Any value may be overridden via a query param.
    """
    # Verify entity exists
    query = select(Entity).where(Entity.entity_id == entity_id)
    result = await session.execute(query)
    entity = result.scalars().unique().one_or_none()
    if entity is None:
        raise HTTPException(status_code=404, detail=f"Entity {entity_id} not found")

    # Pull the entity's real data, then apply any explicit overrides.
    real_equity = await _entity_equity_metrics(session, entity_id) or {}
    real_credit = await _entity_credit_metrics(session, entity_id) or {}
    real_curve = await _latest_curve_data(session)

    def _pick(override, real_value, default):
        if override is not None:
            return override
        return real_value if real_value is not None else default

    equity_data = {
        # return_3m / return_6m must be numeric (engine does `> 0.15`); volatility
        # may legitimately be None (engine guards for it).
        "return_3m": _pick(return_3m, real_equity.get("return_3m"), 0.0),
        "return_6m": _pick(return_6m, real_equity.get("return_6m"), 0.0),
        "pe_percentile": pe_percentile,
        "volatility": volatility if volatility is not None else real_equity.get("volatility"),
    }
    bond_data = {
        "spread_bps": _pick(spread_bps, real_credit.get("spread_bps"), 200.0),
        "spread_change_3m_bps": _pick(
            spread_change_3m_bps, real_credit.get("spread_change_3m_bps"), 0.0
        ),
        "spread_percentile": _pick(
            spread_percentile, real_credit.get("spread_percentile"), 50.0
        ),
    }
    curve_data = {
        "slope_2s10s": slope_2s10s if slope_2s10s is not None else real_curve.get("slope_2s10s"),
        "is_inverted": is_inverted if is_inverted is not None else real_curve.get("is_inverted"),
    }

    # Look up rating data for entity if available.
    rating_stmt = (
        select(CurrentCreditRating)
        .where(CurrentCreditRating.entity_id == entity_id)
        .order_by(CurrentCreditRating.agency)
        .limit(1)
    )
    rating_result = await session.execute(rating_stmt)
    rating_row = rating_result.scalars().first()
    rating_data = None
    if rating_row is not None:
        rating_data = {
            # NOTE: the model field is current_rating_numeric (the old code read a
            # nonexistent `rating_numeric` attribute, so this was always None).
            "rating_numeric": rating_row.current_rating_numeric,
            "outlook": rating_row.outlook,
            "watch_status": rating_row.watch_status,
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
