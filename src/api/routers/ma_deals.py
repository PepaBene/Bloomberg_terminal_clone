"""M&A Deal Database API endpoints (Pillar 1 Supplement – Part 3)."""

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func as sa_func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_pagination, get_session
from src.api.utils.pagination import build_paginated_meta
from src.models.ma_deals import MandADeal
from src.schemas.common import PaginatedResponse, PaginationParams
from src.schemas.ma_deals import DealStatisticsResponse, MandADealResponse

router = APIRouter(tags=["M&A Deals"])


@router.get(
    "/deals",
    response_model=PaginatedResponse,
)
async def list_deals(
    session: AsyncSession = Depends(get_session),
    pagination: PaginationParams = Depends(get_pagination),
    status: str | None = Query(None, description="Filter by deal status"),
    deal_type: str | None = Query(None, description="Filter by deal type"),
    sector: str | None = Query(None, description="Filter by target GICS sector"),
    start: date | None = Query(None, description="Announcement date start"),
    end: date | None = Query(None, description="Announcement date end"),
):
    """List M&A deals with filters."""
    query = select(MandADeal)
    count_query = select(MandADeal)

    if status:
        query = query.where(MandADeal.deal_status == status.upper())
        count_query = count_query.where(MandADeal.deal_status == status.upper())
    if deal_type:
        query = query.where(MandADeal.deal_type == deal_type.upper())
        count_query = count_query.where(MandADeal.deal_type == deal_type.upper())
    if sector:
        query = query.where(MandADeal.target_gics_sector == sector)
        count_query = count_query.where(MandADeal.target_gics_sector == sector)
    if start:
        query = query.where(MandADeal.announcement_date >= start)
        count_query = count_query.where(MandADeal.announcement_date >= start)
    if end:
        query = query.where(MandADeal.announcement_date <= end)
        count_query = count_query.where(MandADeal.announcement_date <= end)

    total_result = await session.execute(
        select(sa_func.count()).select_from(count_query.subquery())
    )
    total_count = total_result.scalar_one()

    offset = (pagination.page - 1) * pagination.page_size
    query = (
        query.order_by(MandADeal.announcement_date.desc().nullslast())
        .offset(offset)
        .limit(pagination.page_size)
    )
    result = await session.execute(query)
    deals = result.scalars().all()

    return PaginatedResponse(
        data=[MandADealResponse.model_validate(d) for d in deals],
        meta=build_paginated_meta(total_count, pagination),
    )


@router.get(
    "/deals/statistics",
    response_model=DealStatisticsResponse,
)
async def get_deal_statistics(
    session: AsyncSession = Depends(get_session),
    start: date | None = Query(None, description="Start date"),
    end: date | None = Query(None, description="End date"),
):
    """Return aggregate deal statistics."""
    query = select(
        sa_func.count(MandADeal.deal_id).label("total_deals"),
        sa_func.sum(MandADeal.total_value).label("total_value"),
        sa_func.avg(MandADeal.premium_to_undisturbed).label("avg_premium"),
        sa_func.avg(MandADeal.ev_to_ebitda).label("avg_ev_to_ebitda"),
    )
    if start:
        query = query.where(MandADeal.announcement_date >= start)
    if end:
        query = query.where(MandADeal.announcement_date <= end)

    result = await session.execute(query)
    row = result.one()
    return DealStatisticsResponse(
        total_deals=row.total_deals or 0,
        total_value=float(row.total_value) if row.total_value else None,
        avg_premium=float(row.avg_premium) if row.avg_premium else None,
        avg_ev_to_ebitda=float(row.avg_ev_to_ebitda) if row.avg_ev_to_ebitda else None,
    )


@router.get(
    "/deals/{deal_id}",
    response_model=MandADealResponse,
)
async def get_deal(
    deal_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Return a single M&A deal by ID."""
    result = await session.execute(
        select(MandADeal).where(MandADeal.deal_id == deal_id)
    )
    deal = result.scalar_one_or_none()
    if not deal:
        raise HTTPException(status_code=404, detail=f"Deal '{deal_id}' not found")
    return MandADealResponse.model_validate(deal)


@router.get(
    "/entities/{entity_id}/deals",
    response_model=PaginatedResponse,
)
async def list_entity_deals(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    pagination: PaginationParams = Depends(get_pagination),
):
    """List deals where the entity is acquirer or target."""
    query = select(MandADeal).where(
        (MandADeal.acquirer_entity_id == entity_id) | (MandADeal.target_entity_id == entity_id)
    )
    count_query = select(MandADeal).where(
        (MandADeal.acquirer_entity_id == entity_id) | (MandADeal.target_entity_id == entity_id)
    )

    total_result = await session.execute(
        select(sa_func.count()).select_from(count_query.subquery())
    )
    total_count = total_result.scalar_one()

    offset = (pagination.page - 1) * pagination.page_size
    query = (
        query.order_by(MandADeal.announcement_date.desc().nullslast())
        .offset(offset)
        .limit(pagination.page_size)
    )
    result = await session.execute(query)
    deals = result.scalars().all()

    return PaginatedResponse(
        data=[MandADealResponse.model_validate(d) for d in deals],
        meta=build_paginated_meta(total_count, pagination),
    )
