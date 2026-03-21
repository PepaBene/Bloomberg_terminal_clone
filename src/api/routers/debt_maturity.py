"""Debt Maturity Profile API endpoints (Pillar 1 Supplement §3)."""

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_session
from src.models.debt_maturity import DebtMaturityProfile
from src.schemas.debt_maturity import (
    DebtMaturityAlertResponse,
    DebtMaturityMetricsResponse,
    DebtMaturityResponse,
)

router = APIRouter(tags=["Debt Maturity"])


@router.get(
    "/entities/{entity_id}/debt-maturity",
    response_model=DebtMaturityResponse,
)
async def get_debt_maturity(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    as_of: date | None = Query(None, description="Point-in-time date"),
):
    """Return the latest debt maturity profile with annual buckets."""
    query = (
        select(DebtMaturityProfile)
        .where(DebtMaturityProfile.entity_id == entity_id)
        .order_by(DebtMaturityProfile.as_of_date.desc())
    )
    if as_of:
        query = query.where(DebtMaturityProfile.as_of_date <= as_of)
    query = query.limit(1)

    result = await session.execute(query)
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail=f"No debt maturity profile found for entity '{entity_id}'")
    return DebtMaturityResponse.model_validate(profile)


@router.get(
    "/entities/{entity_id}/debt-maturity/metrics",
    response_model=DebtMaturityMetricsResponse,
)
async def get_debt_maturity_metrics(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Return derived maturity risk metrics."""
    query = (
        select(DebtMaturityProfile)
        .where(DebtMaturityProfile.entity_id == entity_id)
        .order_by(DebtMaturityProfile.as_of_date.desc())
        .limit(1)
    )
    result = await session.execute(query)
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail=f"No debt maturity data for entity '{entity_id}'")
    return DebtMaturityMetricsResponse.model_validate(profile)


@router.get(
    "/entities/{entity_id}/debt-maturity/alerts",
    response_model=DebtMaturityAlertResponse,
)
async def get_debt_maturity_alerts(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Return refinancing risk alerts."""
    query = (
        select(DebtMaturityProfile)
        .where(DebtMaturityProfile.entity_id == entity_id)
        .order_by(DebtMaturityProfile.as_of_date.desc())
        .limit(1)
    )
    result = await session.execute(query)
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail=f"No debt maturity data for entity '{entity_id}'")
    return DebtMaturityAlertResponse.model_validate(profile)
