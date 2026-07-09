"""Default Risk Scoring API endpoints (Pillar 2 Supplement – Part 2)."""

import math
import statistics
import uuid
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_pagination, get_session
from src.api.utils.pagination import build_paginated_meta
from src.engines.default_risk import compute_composite_score, merton_distance_to_default
from src.models.capital_structure import CapitalStructure
from src.models.default_risk import DefaultRiskScore
from src.models.entity import Entity
from src.models.security import EODPrice, EquityDetails, Security
from src.schemas.common import PaginatedResponse, PaginationParams
from src.schemas.default_risk import (
    AltmanScoreResponse,
    CreditRiskAlertResponse,
    DefaultRiskDriversResponse,
    DefaultRiskHistoryPointResponse,
    DefaultRiskHistoryResponse,
    DefaultRiskScoreResponse,
    KeyDriverResponse,
    MertonComputeRequest,
    MertonComputeResponse,
    MertonModelResponse,
)

router = APIRouter(tags=["Default Risk"])

# Trailing window (~1 trading year plus buffer) used to auto-source the latest
# price and the daily-log-return volatility for the Merton model.
_EQUITY_LOOKBACK_DAYS = 400
_MIN_PRICE_OBSERVATIONS = 20


async def _auto_source_equity_inputs(
    session: AsyncSession,
    entity_id: uuid.UUID,
) -> tuple[float, float, uuid.UUID]:
    """Derive (equity_value, equity_volatility) for an entity's primary equity.

    - ``equity_value`` (market cap) = ``equity_details.shares_outstanding`` x the
      latest ``eod_prices.close``.
    - ``equity_volatility`` = annualized stdev of daily log returns over the
      trailing ~1 year (``pstdev(log returns) * sqrt(252)``).

    Mirrors the price-loading / volatility pattern in
    ``fi_cross_asset._entity_equity_metrics`` and the market-cap pattern in
    ``e2_wacc`` (latest close x shares).

    Raises ``HTTPException`` (404 when the entity has no equity security, 422
    when shares_outstanding or price history is missing) — never fabricates.
    """
    sec_rows = (
        await session.execute(
            select(Security.security_id, Security.security_type, Security.status)
            .where(
                Security.issuer_entity_id == entity_id,
                Security.asset_class == "EQUITY",
            )
        )
    ).all()
    if not sec_rows:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No equity security found for entity {entity_id}; cannot "
                "auto-source market cap / volatility"
            ),
        )

    # Prefer active common stock as the entity's primary listing.
    sec_ids = [
        r[0]
        for r in sorted(
            sec_rows,
            key=lambda r: (r[2] != "ACTIVE", r[1] != "COMMON_STOCK"),
        )
    ]

    cutoff = date.today() - timedelta(days=_EQUITY_LOOKBACK_DAYS)
    missing_shares = False
    missing_prices = False
    for sid in sec_ids:
        shares = (
            await session.execute(
                select(EquityDetails.shares_outstanding).where(
                    EquityDetails.security_id == sid
                )
            )
        ).scalar_one_or_none()

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
        closes = [float(r[1]) for r in rows if r[1] is not None and float(r[1]) > 0]

        if shares is None or float(shares) <= 0:
            missing_shares = True
            continue
        if len(closes) < _MIN_PRICE_OBSERVATIONS:
            missing_prices = True
            continue

        equity_value = float(shares) * closes[-1]
        log_returns = [
            math.log(closes[i] / closes[i - 1])
            for i in range(1, len(closes))
            if closes[i - 1] > 0
        ]
        if len(log_returns) < 2:
            missing_prices = True
            continue
        equity_volatility = statistics.pstdev(log_returns) * math.sqrt(252)
        if equity_volatility <= 0:
            missing_prices = True
            continue

        return equity_value, equity_volatility, sid

    parts = []
    if missing_shares:
        parts.append("shares_outstanding is not populated")
    if missing_prices:
        parts.append(
            "insufficient EOD price history "
            f"(need >= {_MIN_PRICE_OBSERVATIONS} daily closes over the trailing year)"
        )
    detail = "; ".join(parts) or "no usable equity market data"
    raise HTTPException(
        status_code=422,
        detail=(
            f"Cannot auto-source equity inputs for entity {entity_id}: {detail}. "
            "Supply equity_value and equity_volatility explicitly."
        ),
    )


@router.post(
    "/analytics/credit-risk/merton",
    response_model=MertonComputeResponse,
)
async def compute_merton_default_risk(
    body: MertonComputeRequest,
    session: AsyncSession = Depends(get_session),
):
    """Compute Merton distance-to-default (and a composite score) on demand.

    ``equity_value``, ``equity_volatility`` and ``total_debt`` may each be
    supplied directly, or auto-sourced from ``entity_id``:
    - ``equity_value`` = latest EOD close x shares_outstanding.
    - ``equity_volatility`` = annualized daily-log-return volatility (~1y).
    - ``total_debt`` = latest capital-structure snapshot.
    Supplied values always override the auto-sourced ones.
    """
    # --- Auto-source equity inputs when either is omitted ---------------
    equity_value = body.equity_value
    equity_volatility = body.equity_volatility
    if equity_value is None or equity_volatility is None:
        if body.entity_id is None:
            raise HTTPException(
                status_code=422,
                detail=(
                    "equity_value and equity_volatility are required unless an "
                    "entity_id is provided to auto-source them from market data"
                ),
            )
        derived_value, derived_vol, _sid = await _auto_source_equity_inputs(
            session, body.entity_id
        )
        if equity_value is None:
            equity_value = derived_value
        if equity_volatility is None:
            equity_volatility = derived_vol

    total_debt = body.total_debt
    if total_debt is None and body.entity_id is not None:
        row = (
            await session.execute(
                select(CapitalStructure.total_debt)
                .where(
                    CapitalStructure.entity_id == body.entity_id,
                    CapitalStructure.total_debt.isnot(None),
                )
                .order_by(CapitalStructure.as_of_date.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        total_debt = float(row) if row is not None else None

    if total_debt is None or total_debt <= 0:
        raise HTTPException(
            status_code=400,
            detail=(
                "total_debt is required — provide it directly or pass an entity_id "
                "that has capital-structure data with a positive total_debt"
            ),
        )

    try:
        merton = merton_distance_to_default(
            equity_value=equity_value,
            equity_volatility=equity_volatility,
            total_debt=total_debt,
            risk_free_rate=body.risk_free_rate,
            horizon=body.horizon,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    composite = compute_composite_score(
        altman_z=body.altman_z,
        merton_dd=merton.distance_to_default,
        merton_pd=merton.probability_of_default,
        leverage_ratio=body.leverage_ratio,
        interest_coverage=body.interest_coverage,
        cash_ratio=body.cash_ratio,
    )

    return MertonComputeResponse(
        entity_id=body.entity_id,
        calculation_date=date.today(),
        merton=MertonModelResponse(
            distance_to_default=merton.distance_to_default,
            probability_of_default=merton.probability_of_default,
            asset_value=merton.asset_value,
            asset_volatility=merton.asset_volatility,
            equity_volatility=equity_volatility,
        ),
        composite_score=composite.score,
        implied_rating=composite.implied_rating,
        credit_zone=composite.credit_zone,
        key_drivers=[
            KeyDriverResponse(
                driver=d["driver"],
                contribution=d["contribution"],
                description=d.get("description"),
            )
            for d in composite.drivers
        ],
        total_debt_used=total_debt,
        risk_free_rate_used=body.risk_free_rate,
    )


def _build_score_response(row: DefaultRiskScore) -> DefaultRiskScoreResponse:
    """Convert a DB row to the full score response."""
    altman = None
    if row.altman_z_score is not None:
        altman = AltmanScoreResponse(
            z_score=float(row.altman_z_score),
            zone=row.altman_zone,
        )

    merton = None
    if row.merton_dd is not None:
        merton = MertonModelResponse(
            distance_to_default=float(row.merton_dd),
            probability_of_default=float(row.merton_pd) if row.merton_pd else None,
            asset_value=float(row.merton_asset_value) if row.merton_asset_value else None,
            asset_volatility=float(row.merton_asset_vol) if row.merton_asset_vol else None,
            equity_volatility=float(row.equity_volatility) if row.equity_volatility else None,
        )

    drivers = []
    if row.key_drivers and isinstance(row.key_drivers, list):
        for d in row.key_drivers:
            drivers.append(KeyDriverResponse(
                driver=d.get("driver", ""),
                contribution=d.get("contribution", 0.0),
                description=d.get("description"),
            ))

    return DefaultRiskScoreResponse(
        score_id=row.score_id,
        entity_id=row.entity_id,
        security_id=row.security_id,
        calculation_date=row.calculation_date,
        altman=altman,
        merton=merton,
        composite_score=float(row.composite_score) if row.composite_score else None,
        implied_rating=row.implied_rating,
        credit_zone=row.credit_zone,
        key_drivers=drivers,
        prior_score=float(row.prior_score) if row.prior_score else None,
        score_change=float(row.score_change) if row.score_change else None,
        trend=row.trend,
        data_quality=row.data_quality,
    )


# NOTE: /alerts must be defined BEFORE /{entity_id} to avoid path conflict
@router.get(
    "/analytics/credit-risk/alerts",
    response_model=list[CreditRiskAlertResponse],
)
async def get_credit_risk_alerts(
    session: AsyncSession = Depends(get_session),
    min_score_change: float = Query(-5.0, description="Minimum score change (negative = deterioration)"),
    limit: int = Query(50, ge=1, le=500, description="Max alerts"),
):
    """Return entities with deteriorating credit risk scores."""
    query = (
        select(DefaultRiskScore)
        .where(
            DefaultRiskScore.score_change != None,  # noqa: E711
            DefaultRiskScore.score_change <= min_score_change,
        )
        .order_by(DefaultRiskScore.score_change.asc())
        .limit(limit)
    )
    result = await session.execute(query)
    rows = result.scalars().all()

    alerts = []
    for row in rows:
        alerts.append(CreditRiskAlertResponse(
            entity_id=row.entity_id,
            calculation_date=row.calculation_date,
            composite_score=float(row.composite_score) if row.composite_score else None,
            prior_score=float(row.prior_score) if row.prior_score else None,
            score_change=float(row.score_change) if row.score_change else None,
            trend=row.trend,
            implied_rating=row.implied_rating,
            credit_zone=row.credit_zone,
        ))

    return alerts


@router.get(
    "/analytics/credit-risk/{entity_id}",
    response_model=DefaultRiskScoreResponse,
)
async def get_default_risk_score(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    calculation_date: date | None = Query(None, description="Specific date (defaults to latest)"),
):
    """Return the latest (or date-specific) composite default risk score."""
    query = (
        select(DefaultRiskScore)
        .where(DefaultRiskScore.entity_id == entity_id)
        .order_by(DefaultRiskScore.calculation_date.desc())
    )
    if calculation_date:
        query = query.where(DefaultRiskScore.calculation_date == calculation_date)
    query = query.limit(1)

    result = await session.execute(query)
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="No default risk score found for this entity")

    return _build_score_response(row)


@router.get(
    "/analytics/credit-risk/{entity_id}/history",
    response_model=DefaultRiskHistoryResponse,
)
async def get_default_risk_history(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    start: date | None = Query(None, description="Start date"),
    end: date | None = Query(None, description="End date"),
    limit: int = Query(100, ge=1, le=1000, description="Max records"),
):
    """Return historical default risk scores for an entity."""
    query = (
        select(DefaultRiskScore)
        .where(DefaultRiskScore.entity_id == entity_id)
        .order_by(DefaultRiskScore.calculation_date.desc())
    )
    if start:
        query = query.where(DefaultRiskScore.calculation_date >= start)
    if end:
        query = query.where(DefaultRiskScore.calculation_date <= end)
    query = query.limit(limit)

    result = await session.execute(query)
    rows = result.scalars().all()

    points = []
    for row in reversed(rows):  # chronological order
        points.append(DefaultRiskHistoryPointResponse(
            calculation_date=row.calculation_date,
            composite_score=float(row.composite_score) if row.composite_score else None,
            implied_rating=row.implied_rating,
            credit_zone=row.credit_zone,
            altman_z_score=float(row.altman_z_score) if row.altman_z_score else None,
            merton_dd=float(row.merton_dd) if row.merton_dd else None,
            merton_pd=float(row.merton_pd) if row.merton_pd else None,
        ))

    return DefaultRiskHistoryResponse(entity_id=entity_id, points=points)


@router.get(
    "/analytics/credit-risk/{entity_id}/drivers",
    response_model=DefaultRiskDriversResponse,
)
async def get_default_risk_drivers(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    calculation_date: date | None = Query(None, description="Specific date (defaults to latest)"),
):
    """Return the driver decomposition for an entity's risk score."""
    query = (
        select(DefaultRiskScore)
        .where(DefaultRiskScore.entity_id == entity_id)
        .order_by(DefaultRiskScore.calculation_date.desc())
    )
    if calculation_date:
        query = query.where(DefaultRiskScore.calculation_date == calculation_date)
    query = query.limit(1)

    result = await session.execute(query)
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="No default risk score found for this entity")

    drivers = []
    if row.key_drivers and isinstance(row.key_drivers, list):
        for d in row.key_drivers:
            drivers.append(KeyDriverResponse(
                driver=d.get("driver", ""),
                contribution=d.get("contribution", 0.0),
                description=d.get("description"),
            ))

    return DefaultRiskDriversResponse(
        entity_id=entity_id,
        calculation_date=row.calculation_date,
        composite_score=float(row.composite_score) if row.composite_score else None,
        drivers=drivers,
    )
