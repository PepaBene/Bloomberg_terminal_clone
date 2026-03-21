"""Default Risk Scoring API endpoints (Pillar 2 Supplement – Part 2)."""

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_pagination, get_session
from src.api.utils.pagination import build_paginated_meta
from src.models.default_risk import DefaultRiskScore
from src.models.entity import Entity
from src.schemas.common import PaginatedResponse, PaginationParams
from src.schemas.default_risk import (
    AltmanScoreResponse,
    CreditRiskAlertResponse,
    DefaultRiskDriversResponse,
    DefaultRiskHistoryPointResponse,
    DefaultRiskHistoryResponse,
    DefaultRiskScoreResponse,
    KeyDriverResponse,
    MertonModelResponse,
)

router = APIRouter(tags=["Default Risk"])


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
