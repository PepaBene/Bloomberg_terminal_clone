"""Money Market Rates API endpoints (Pillar 1 Supplement – Part 2)."""

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func as sa_func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_pagination, get_session
from src.api.utils.pagination import build_paginated_meta
from src.models.fed_meeting import MoneyMarketRate
from src.schemas.common import PaginatedResponse, PaginationParams
from src.schemas.money_market import MoneyMarketRateResponse

router = APIRouter(tags=["Money Markets"])


@router.get(
    "/macro/money-markets",
    response_model=PaginatedResponse,
)
async def list_money_market_rates(
    session: AsyncSession = Depends(get_session),
    pagination: PaginationParams = Depends(get_pagination),
    rate_type: str | None = Query(None, description="Filter by rate type (e.g. SOFR, PRIME)"),
    rate_date: date | None = Query(None, description="Specific date"),
    start: date | None = Query(None, description="Start date"),
    end: date | None = Query(None, description="End date"),
):
    """List money market rates with optional filters."""
    query = select(MoneyMarketRate)
    count_query = select(MoneyMarketRate)

    if rate_type:
        query = query.where(MoneyMarketRate.rate_type == rate_type.upper())
        count_query = count_query.where(MoneyMarketRate.rate_type == rate_type.upper())
    if rate_date:
        # Exact date wins — ignore start/end range parameters
        query = query.where(MoneyMarketRate.rate_date == rate_date)
        count_query = count_query.where(MoneyMarketRate.rate_date == rate_date)
    else:
        if start:
            query = query.where(MoneyMarketRate.rate_date >= start)
            count_query = count_query.where(MoneyMarketRate.rate_date >= start)
        if end:
            query = query.where(MoneyMarketRate.rate_date <= end)
            count_query = count_query.where(MoneyMarketRate.rate_date <= end)

    total_result = await session.execute(
        select(sa_func.count()).select_from(count_query.subquery())
    )
    total_count = total_result.scalar_one()

    offset = (pagination.page - 1) * pagination.page_size
    query = (
        query.order_by(MoneyMarketRate.rate_date.desc())
        .offset(offset)
        .limit(pagination.page_size)
    )
    result = await session.execute(query)
    rates = result.scalars().all()

    return PaginatedResponse(
        data=[MoneyMarketRateResponse.model_validate(r) for r in rates],
        meta=build_paginated_meta(total_count, pagination),
    )
