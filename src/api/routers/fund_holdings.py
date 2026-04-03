"""Fund Holdings API endpoints (Pillar 1 Supplement – Part 4)."""

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func as sa_func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_pagination, get_session
from src.api.utils.pagination import build_paginated_meta
from src.models.fund_holdings import Fund, FundHolding
from src.schemas.common import PaginatedResponse, PaginationParams
from src.schemas.fund_holdings import FundHoldingResponse, FundResponse

router = APIRouter(tags=["Fund Holdings"])


@router.get(
    "/funds",
    response_model=PaginatedResponse,
)
async def list_funds(
    session: AsyncSession = Depends(get_session),
    pagination: PaginationParams = Depends(get_pagination),
    fund_type: str | None = Query(None, description="Filter by fund type"),
):
    """List investment funds."""
    query = select(Fund)
    count_query = select(Fund)

    if fund_type:
        query = query.where(Fund.fund_type == fund_type.upper())
        count_query = count_query.where(Fund.fund_type == fund_type.upper())

    total_result = await session.execute(
        select(sa_func.count()).select_from(count_query.subquery())
    )
    total_count = total_result.scalar_one()

    offset = (pagination.page - 1) * pagination.page_size
    query = query.order_by(Fund.fund_name).offset(offset).limit(pagination.page_size)
    result = await session.execute(query)
    funds = result.scalars().all()

    return PaginatedResponse(
        data=[FundResponse.model_validate(f) for f in funds],
        meta=build_paginated_meta(total_count, pagination),
    )


@router.get(
    "/funds/{fund_id}",
    response_model=FundResponse,
)
async def get_fund(
    fund_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Return a single fund by ID."""
    result = await session.execute(select(Fund).where(Fund.fund_id == fund_id))
    fund = result.scalar_one_or_none()
    if not fund:
        raise HTTPException(status_code=404, detail=f"Fund '{fund_id}' not found")
    return FundResponse.model_validate(fund)


@router.get(
    "/funds/{fund_id}/holdings",
    response_model=PaginatedResponse,
)
async def list_fund_holdings(
    fund_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    pagination: PaginationParams = Depends(get_pagination),
    report_date: date | None = Query(None, description="Specific report date"),
    asset_type: str | None = Query(None, description="Filter by asset type"),
):
    """List holdings for a fund."""
    query = select(FundHolding).where(FundHolding.fund_id == fund_id)
    count_query = select(FundHolding).where(FundHolding.fund_id == fund_id)

    if report_date:
        query = query.where(FundHolding.report_date == report_date)
        count_query = count_query.where(FundHolding.report_date == report_date)
    if asset_type:
        query = query.where(FundHolding.asset_type == asset_type.upper())
        count_query = count_query.where(FundHolding.asset_type == asset_type.upper())

    total_result = await session.execute(
        select(sa_func.count()).select_from(count_query.subquery())
    )
    total_count = total_result.scalar_one()

    offset = (pagination.page - 1) * pagination.page_size
    query = (
        query.order_by(FundHolding.pct_of_nav.desc().nulls_last())
        .offset(offset)
        .limit(pagination.page_size)
    )
    result = await session.execute(query)
    holdings = result.scalars().all()

    return PaginatedResponse(
        data=[FundHoldingResponse.model_validate(h) for h in holdings],
        meta=build_paginated_meta(total_count, pagination),
    )


@router.get(
    "/securities/{security_id}/fund-holders",
    response_model=PaginatedResponse,
)
async def list_fund_holders(
    security_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    pagination: PaginationParams = Depends(get_pagination),
):
    """List funds that hold a given security."""
    query = select(FundHolding).where(FundHolding.security_id == security_id)
    count_query = select(FundHolding).where(FundHolding.security_id == security_id)

    total_result = await session.execute(
        select(sa_func.count()).select_from(count_query.subquery())
    )
    total_count = total_result.scalar_one()

    offset = (pagination.page - 1) * pagination.page_size
    query = (
        query.order_by(FundHolding.market_value.desc().nulls_last())
        .offset(offset)
        .limit(pagination.page_size)
    )
    result = await session.execute(query)
    holdings = result.scalars().all()

    return PaginatedResponse(
        data=[FundHoldingResponse.model_validate(h) for h in holdings],
        meta=build_paginated_meta(total_count, pagination),
    )
