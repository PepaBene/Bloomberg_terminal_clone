"""Debt Maturity Profile API endpoints (Pillar 1 Supplement §3)."""

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func as sa_func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_pagination, get_session
from src.models.debt_maturity import DebtMaturityProfile
from src.api.utils.pagination import build_paginated_meta
from src.schemas.common import PaginatedResponse, PaginationParams
from src.schemas.debt_maturity import (
    DebtMaturityAlertResponse,
    DebtMaturityMetricsResponse,
    DebtMaturityResponse,
)

router = APIRouter(tags=["Debt Maturity"])


@router.get(
    "/entities/{entity_id}/debt-maturity",
    response_model=PaginatedResponse,
)
async def get_debt_maturity(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    pagination: PaginationParams = Depends(get_pagination),
    as_of: date | None = Query(None, description="Point-in-time date"),
):
    """Return debt maturity profiles with annual buckets (paginated)."""
    query = select(DebtMaturityProfile).where(
        DebtMaturityProfile.entity_id == entity_id
    )
    count_query = select(DebtMaturityProfile).where(
        DebtMaturityProfile.entity_id == entity_id
    )

    if as_of:
        query = query.where(DebtMaturityProfile.as_of_date <= as_of)
        count_query = count_query.where(DebtMaturityProfile.as_of_date <= as_of)

    total_result = await session.execute(
        select(sa_func.count()).select_from(count_query.subquery())
    )
    total_count = total_result.scalar_one()

    offset = (pagination.page - 1) * pagination.page_size
    query = (
        query.order_by(DebtMaturityProfile.as_of_date.desc())
        .offset(offset)
        .limit(pagination.page_size)
    )

    result = await session.execute(query)
    profiles = result.scalars().all()

    return PaginatedResponse(
        data=[DebtMaturityResponse.model_validate(p) for p in profiles],
        meta=build_paginated_meta(total_count, pagination),
    )


@router.get(
    "/entities/{entity_id}/debt-maturity/metrics",
    response_model=PaginatedResponse,
)
async def get_debt_maturity_metrics(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    pagination: PaginationParams = Depends(get_pagination),
):
    """Return derived maturity risk metrics (paginated)."""
    query = select(DebtMaturityProfile).where(
        DebtMaturityProfile.entity_id == entity_id
    )
    count_query = select(DebtMaturityProfile).where(
        DebtMaturityProfile.entity_id == entity_id
    )

    total_result = await session.execute(
        select(sa_func.count()).select_from(count_query.subquery())
    )
    total_count = total_result.scalar_one()

    offset = (pagination.page - 1) * pagination.page_size
    query = (
        query.order_by(DebtMaturityProfile.as_of_date.desc())
        .offset(offset)
        .limit(pagination.page_size)
    )
    result = await session.execute(query)
    profiles = result.scalars().all()

    return PaginatedResponse(
        data=[DebtMaturityMetricsResponse.model_validate(p) for p in profiles],
        meta=build_paginated_meta(total_count, pagination),
    )


@router.get(
    "/entities/{entity_id}/debt-maturity/alerts",
    response_model=PaginatedResponse,
)
async def get_debt_maturity_alerts(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    pagination: PaginationParams = Depends(get_pagination),
):
    """Return refinancing risk alerts (paginated)."""
    query = select(DebtMaturityProfile).where(
        DebtMaturityProfile.entity_id == entity_id
    )
    count_query = select(DebtMaturityProfile).where(
        DebtMaturityProfile.entity_id == entity_id
    )

    total_result = await session.execute(
        select(sa_func.count()).select_from(count_query.subquery())
    )
    total_count = total_result.scalar_one()

    offset = (pagination.page - 1) * pagination.page_size
    query = (
        query.order_by(DebtMaturityProfile.as_of_date.desc())
        .offset(offset)
        .limit(pagination.page_size)
    )
    result = await session.execute(query)
    profiles = result.scalars().all()

    return PaginatedResponse(
        data=[DebtMaturityAlertResponse.model_validate(p) for p in profiles],
        meta=build_paginated_meta(total_count, pagination),
    )
