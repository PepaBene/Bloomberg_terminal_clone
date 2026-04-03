"""Credit Rating History API endpoints (Pillar 1 Supplement §4)."""

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func as sa_func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_pagination, get_session
from src.api.utils.pagination import build_paginated_meta
from src.models.credit_rating import CreditRatingEvent
from src.schemas.common import PaginatedResponse, PaginationParams
from src.schemas.credit_rating import CreditRatingEventResponse

router = APIRouter(tags=["Credit Ratings"])


@router.get(
    "/entities/{entity_id}/credit-ratings",
    response_model=PaginatedResponse,
)
async def list_credit_ratings(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    pagination: PaginationParams = Depends(get_pagination),
    agency: str | None = Query(None, description="Filter by agency (SP, MOODYS, FITCH)"),
    direction: str | None = Query(None, description="Filter by direction"),
):
    """List credit rating events for an entity."""
    query = select(CreditRatingEvent).where(CreditRatingEvent.entity_id == entity_id)
    count_query = select(CreditRatingEvent).where(CreditRatingEvent.entity_id == entity_id)

    if agency:
        query = query.where(CreditRatingEvent.agency == agency.upper())
        count_query = count_query.where(CreditRatingEvent.agency == agency.upper())
    if direction:
        query = query.where(CreditRatingEvent.direction == direction.upper())
        count_query = count_query.where(CreditRatingEvent.direction == direction.upper())

    total_result = await session.execute(
        select(sa_func.count()).select_from(count_query.subquery())
    )
    total_count = total_result.scalar_one()

    offset = (pagination.page - 1) * pagination.page_size
    query = (
        query.order_by(CreditRatingEvent.event_date.desc().nulls_last())
        .offset(offset)
        .limit(pagination.page_size)
    )
    result = await session.execute(query)
    events = result.scalars().all()

    return PaginatedResponse(
        data=[CreditRatingEventResponse.model_validate(e) for e in events],
        meta=build_paginated_meta(total_count, pagination),
    )


@router.get(
    "/entities/{entity_id}/credit-ratings/history",
    response_model=PaginatedResponse,
)
async def list_credit_rating_history(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    pagination: PaginationParams = Depends(get_pagination),
    start: date | None = Query(None, description="Start date"),
    end: date | None = Query(None, description="End date"),
):
    """Return full credit rating history over a date range."""
    query = select(CreditRatingEvent).where(CreditRatingEvent.entity_id == entity_id)
    count_query = select(CreditRatingEvent).where(CreditRatingEvent.entity_id == entity_id)

    if start:
        query = query.where(CreditRatingEvent.event_date >= start)
        count_query = count_query.where(CreditRatingEvent.event_date >= start)
    if end:
        query = query.where(CreditRatingEvent.event_date <= end)
        count_query = count_query.where(CreditRatingEvent.event_date <= end)

    total_result = await session.execute(
        select(sa_func.count()).select_from(count_query.subquery())
    )
    total_count = total_result.scalar_one()

    offset = (pagination.page - 1) * pagination.page_size
    query = (
        query.order_by(CreditRatingEvent.event_date.desc().nulls_last())
        .offset(offset)
        .limit(pagination.page_size)
    )
    result = await session.execute(query)
    events = result.scalars().all()

    return PaginatedResponse(
        data=[CreditRatingEventResponse.model_validate(e) for e in events],
        meta=build_paginated_meta(total_count, pagination),
    )
