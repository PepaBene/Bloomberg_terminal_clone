"""Earnings Intelligence API endpoints (Pillar 1 Supplement – Part 3)."""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func as sa_func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_pagination, get_session
from src.api.utils.pagination import build_paginated_meta
from src.models.earnings_intelligence import EarningsSurprise, GuidanceTracking
from src.schemas.common import PaginatedResponse, PaginationParams
from src.schemas.earnings_intelligence import (
    EarningsSurpriseResponse,
    GuidanceTrackingResponse,
)

router = APIRouter(tags=["Earnings Intelligence"])


@router.get(
    "/entities/{entity_id}/earnings-surprises",
    response_model=PaginatedResponse,
)
async def list_earnings_surprises(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    pagination: PaginationParams = Depends(get_pagination),
    fiscal_year: int | None = Query(None, description="Filter by fiscal year"),
):
    """List earnings surprises for an entity."""
    query = select(EarningsSurprise).where(EarningsSurprise.entity_id == entity_id)
    count_query = select(EarningsSurprise).where(EarningsSurprise.entity_id == entity_id)

    if fiscal_year:
        query = query.where(EarningsSurprise.fiscal_year == fiscal_year)
        count_query = count_query.where(EarningsSurprise.fiscal_year == fiscal_year)

    total_result = await session.execute(
        select(sa_func.count()).select_from(count_query.subquery())
    )
    total_count = total_result.scalar_one()

    offset = (pagination.page - 1) * pagination.page_size
    query = (
        query.order_by(
            EarningsSurprise.fiscal_year.desc(),
            EarningsSurprise.fiscal_quarter.desc(),
        )
        .offset(offset)
        .limit(pagination.page_size)
    )
    result = await session.execute(query)
    surprises = result.scalars().all()

    return PaginatedResponse(
        data=[EarningsSurpriseResponse.model_validate(s) for s in surprises],
        meta=build_paginated_meta(total_count, pagination),
    )


@router.get(
    "/entities/{entity_id}/guidance-tracking",
    response_model=PaginatedResponse,
)
async def list_guidance(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    pagination: PaginationParams = Depends(get_pagination),
    fiscal_year: int | None = Query(None, description="Filter by guidance fiscal year"),
    metric: str | None = Query(None, description="Filter by metric (EPS, REVENUE, EBITDA)"),
):
    """List guidance tracking for an entity."""
    query = select(GuidanceTracking).where(GuidanceTracking.entity_id == entity_id)
    count_query = select(GuidanceTracking).where(GuidanceTracking.entity_id == entity_id)

    if fiscal_year:
        query = query.where(GuidanceTracking.guidance_fiscal_year == fiscal_year)
        count_query = count_query.where(GuidanceTracking.guidance_fiscal_year == fiscal_year)
    if metric:
        query = query.where(GuidanceTracking.metric == metric.upper())
        count_query = count_query.where(GuidanceTracking.metric == metric.upper())

    total_result = await session.execute(
        select(sa_func.count()).select_from(count_query.subquery())
    )
    total_count = total_result.scalar_one()

    offset = (pagination.page - 1) * pagination.page_size
    query = (
        query.order_by(GuidanceTracking.guidance_date.desc())
        .offset(offset)
        .limit(pagination.page_size)
    )
    result = await session.execute(query)
    records = result.scalars().all()

    return PaginatedResponse(
        data=[GuidanceTrackingResponse.model_validate(r) for r in records],
        meta=build_paginated_meta(total_count, pagination),
    )
