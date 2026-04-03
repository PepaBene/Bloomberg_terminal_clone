"""Corporate Actions Calendar API endpoints (Pillar 1 Supplement §8)."""

import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func as sa_func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_pagination, get_session
from src.api.utils.pagination import build_paginated_meta
from src.models.calendar import CalendarEvent
from src.schemas.calendar import CalendarEventResponse
from src.schemas.common import PaginatedResponse, PaginationParams

router = APIRouter(tags=["Calendar"])


@router.get(
    "/calendar/corporate-actions",
    response_model=PaginatedResponse,
)
async def list_corporate_action_events(
    session: AsyncSession = Depends(get_session),
    pagination: PaginationParams = Depends(get_pagination),
    date_from: date | None = Query(None, description="Start date"),
    date_to: date | None = Query(None, description="End date"),
    entity_ids: str | None = Query(None, description="Comma-separated entity UUIDs"),
    event_types: str | None = Query(None, description="Comma-separated event types"),
):
    """List calendar events for corporate actions within a date range."""
    query = select(CalendarEvent)
    count_query = select(CalendarEvent)

    if date_from:
        query = query.where(CalendarEvent.event_date >= date_from)
        count_query = count_query.where(CalendarEvent.event_date >= date_from)
    if date_to:
        query = query.where(CalendarEvent.event_date <= date_to)
        count_query = count_query.where(CalendarEvent.event_date <= date_to)
    if entity_ids:
        ids = [uuid.UUID(eid.strip()) for eid in entity_ids.split(",") if eid.strip()]
        query = query.where(CalendarEvent.entity_id.in_(ids))
        count_query = count_query.where(CalendarEvent.entity_id.in_(ids))
    if event_types:
        types = [t.strip().upper() for t in event_types.split(",") if t.strip()]
        query = query.where(CalendarEvent.event_type.in_(types))
        count_query = count_query.where(CalendarEvent.event_type.in_(types))

    total_result = await session.execute(
        select(sa_func.count()).select_from(count_query.subquery())
    )
    total_count = total_result.scalar_one()

    offset = (pagination.page - 1) * pagination.page_size
    query = (
        query.order_by(CalendarEvent.event_date.asc())
        .offset(offset)
        .limit(pagination.page_size)
    )
    result = await session.execute(query)
    events = result.scalars().all()

    return PaginatedResponse(
        data=[CalendarEventResponse.model_validate(e) for e in events],
        meta=build_paginated_meta(total_count, pagination),
    )


@router.get(
    "/calendar/events",
    response_model=PaginatedResponse,
)
async def list_all_calendar_events(
    session: AsyncSession = Depends(get_session),
    pagination: PaginationParams = Depends(get_pagination),
    date_from: date | None = Query(None, description="Start date"),
    date_to: date | None = Query(None, description="End date"),
    entity_ids: str | None = Query(None, description="Comma-separated entity UUIDs"),
    event_types: str | None = Query(None, description="Comma-separated event types"),
):
    """Unified calendar merging corporate actions, earnings, and meetings."""
    query = select(CalendarEvent)
    count_query = select(CalendarEvent)

    if date_from:
        query = query.where(CalendarEvent.event_date >= date_from)
        count_query = count_query.where(CalendarEvent.event_date >= date_from)
    if date_to:
        query = query.where(CalendarEvent.event_date <= date_to)
        count_query = count_query.where(CalendarEvent.event_date <= date_to)
    if entity_ids:
        ids = [uuid.UUID(eid.strip()) for eid in entity_ids.split(",") if eid.strip()]
        query = query.where(CalendarEvent.entity_id.in_(ids))
        count_query = count_query.where(CalendarEvent.entity_id.in_(ids))
    if event_types:
        types = [t.strip().upper() for t in event_types.split(",") if t.strip()]
        query = query.where(CalendarEvent.event_type.in_(types))
        count_query = count_query.where(CalendarEvent.event_type.in_(types))

    total_result = await session.execute(
        select(sa_func.count()).select_from(count_query.subquery())
    )
    total_count = total_result.scalar_one()

    offset = (pagination.page - 1) * pagination.page_size
    query = (
        query.order_by(CalendarEvent.event_date.asc())
        .offset(offset)
        .limit(pagination.page_size)
    )
    result = await session.execute(query)
    events = result.scalars().all()

    return PaginatedResponse(
        data=[CalendarEventResponse.model_validate(e) for e in events],
        meta=build_paginated_meta(total_count, pagination),
    )
