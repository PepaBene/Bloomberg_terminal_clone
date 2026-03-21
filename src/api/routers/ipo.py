"""IPO Monitor API endpoints (Pillar 1 Supplement – Part 3)."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func as sa_func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_pagination, get_session
from src.api.utils.pagination import build_paginated_meta
from src.models.ipo import IPOEvent
from src.schemas.common import PaginatedResponse, PaginationParams
from src.schemas.ipo import IPOEventResponse

router = APIRouter(tags=["IPO"])


@router.get(
    "/ipos",
    response_model=PaginatedResponse,
)
async def list_ipos(
    session: AsyncSession = Depends(get_session),
    pagination: PaginationParams = Depends(get_pagination),
    status: str | None = Query(None, description="Filter by status"),
    sector: str | None = Query(None, description="Filter by GICS sector"),
):
    """List IPO events with filters."""
    query = select(IPOEvent)
    count_query = select(IPOEvent)

    if status:
        query = query.where(IPOEvent.status == status.upper())
        count_query = count_query.where(IPOEvent.status == status.upper())
    if sector:
        query = query.where(IPOEvent.gics_sector == sector)
        count_query = count_query.where(IPOEvent.gics_sector == sector)

    total_result = await session.execute(
        select(sa_func.count()).select_from(count_query.subquery())
    )
    total_count = total_result.scalar_one()

    offset = (pagination.page - 1) * pagination.page_size
    query = (
        query.order_by(IPOEvent.pricing_date.desc().nullslast())
        .offset(offset)
        .limit(pagination.page_size)
    )
    result = await session.execute(query)
    ipos = result.scalars().all()

    return PaginatedResponse(
        data=[IPOEventResponse.model_validate(i) for i in ipos],
        meta=build_paginated_meta(total_count, pagination),
    )


@router.get(
    "/ipos/pipeline",
    response_model=PaginatedResponse,
)
async def list_ipo_pipeline(
    session: AsyncSession = Depends(get_session),
    pagination: PaginationParams = Depends(get_pagination),
):
    """List upcoming/filed IPOs (pipeline view)."""
    query = select(IPOEvent).where(IPOEvent.status.in_(["FILED", "AMENDED"]))
    count_query = select(IPOEvent).where(IPOEvent.status.in_(["FILED", "AMENDED"]))

    total_result = await session.execute(
        select(sa_func.count()).select_from(count_query.subquery())
    )
    total_count = total_result.scalar_one()

    offset = (pagination.page - 1) * pagination.page_size
    query = (
        query.order_by(IPOEvent.s1_filing_date.desc().nullslast())
        .offset(offset)
        .limit(pagination.page_size)
    )
    result = await session.execute(query)
    ipos = result.scalars().all()

    return PaginatedResponse(
        data=[IPOEventResponse.model_validate(i) for i in ipos],
        meta=build_paginated_meta(total_count, pagination),
    )


@router.get(
    "/ipos/{ipo_id}",
    response_model=IPOEventResponse,
)
async def get_ipo(
    ipo_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Return a single IPO event by ID."""
    result = await session.execute(
        select(IPOEvent).where(IPOEvent.ipo_id == ipo_id)
    )
    ipo = result.scalar_one_or_none()
    if not ipo:
        raise HTTPException(status_code=404, detail=f"IPO '{ipo_id}' not found")
    return IPOEventResponse.model_validate(ipo)
