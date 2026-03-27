"""Fixed Income - Treasuries API endpoints (D11 FI Supplement P2)."""

from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func as sa_func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_pagination, get_session
from src.api.utils.pagination import build_paginated_meta
from src.engines.treasury_analytics import (
    compute_duration_convexity,
    compute_treasury_ytm,
    identify_on_the_run,
)
from src.models.treasury import TreasurySecurity
from src.schemas.common import PaginatedResponse, PaginationParams
from src.schemas.treasury import (
    TreasuryAuctionResponse,
    TreasuryOnTheRunResponse,
    TreasurySecurityResponse,
)

router = APIRouter(tags=["Fixed Income - Treasuries"])


@router.get(
    "/fixed-income/treasuries",
    response_model=PaginatedResponse,
)
async def list_treasuries(
    session: AsyncSession = Depends(get_session),
    pagination: PaginationParams = Depends(get_pagination),
    type: str | None = Query(None, description="Filter by treasury type"),
    maturity_before: date | None = Query(None, description="Maturity date before"),
    maturity_after: date | None = Query(None, description="Maturity date after"),
    is_outstanding: bool = Query(True, description="Filter by outstanding status"),
):
    """List and filter treasury securities (paginated)."""
    query = select(TreasurySecurity).where(
        TreasurySecurity.is_outstanding == is_outstanding
    )
    count_query = select(TreasurySecurity).where(
        TreasurySecurity.is_outstanding == is_outstanding
    )

    if type:
        query = query.where(TreasurySecurity.treasury_type == type.upper())
        count_query = count_query.where(TreasurySecurity.treasury_type == type.upper())
    if maturity_before:
        query = query.where(TreasurySecurity.maturity_date <= maturity_before)
        count_query = count_query.where(TreasurySecurity.maturity_date <= maturity_before)
    if maturity_after:
        query = query.where(TreasurySecurity.maturity_date >= maturity_after)
        count_query = count_query.where(TreasurySecurity.maturity_date >= maturity_after)

    total_result = await session.execute(
        select(sa_func.count()).select_from(count_query.subquery())
    )
    total_count = total_result.scalar_one()

    offset = (pagination.page - 1) * pagination.page_size
    query = (
        query.order_by(TreasurySecurity.maturity_date.desc())
        .offset(offset)
        .limit(pagination.page_size)
    )
    result = await session.execute(query)
    items = result.scalars().all()

    return PaginatedResponse(
        data=[TreasurySecurityResponse.model_validate(t) for t in items],
        meta=build_paginated_meta(total_count, pagination),
    )


@router.get(
    "/fixed-income/treasuries/on-the-run",
    response_model=list[TreasuryOnTheRunResponse],
)
async def on_the_run(
    session: AsyncSession = Depends(get_session),
):
    """Get most recently issued treasury security per tenor bucket."""
    query = select(TreasurySecurity).where(TreasurySecurity.is_outstanding == True)  # noqa: E712
    result = await session.execute(query)
    securities = result.scalars().all()

    sec_dicts = [
        {
            "cusip": s.cusip,
            "issue_date": s.issue_date,
            "maturity_date": s.maturity_date,
            "coupon_rate": float(s.coupon_rate) if s.coupon_rate is not None else 0,
            "auction_high_yield": float(s.auction_high_yield) if s.auction_high_yield is not None else None,
        }
        for s in securities
    ]

    otr = identify_on_the_run(sec_dicts)

    return [
        TreasuryOnTheRunResponse(
            tenor=tenor,
            cusip=sec["cusip"],
            ytm=sec.get("auction_high_yield"),
        )
        for tenor, sec in sorted(otr.items())
    ]


@router.get(
    "/fixed-income/treasuries/auction-calendar",
    response_model=PaginatedResponse,
)
async def auction_calendar(
    session: AsyncSession = Depends(get_session),
    pagination: PaginationParams = Depends(get_pagination),
    weeks_ahead: int = Query(4, ge=1, le=52, description="Number of weeks ahead to look"),
):
    """Get upcoming treasury auctions within a specified window."""
    today = date.today()
    end_date = today + timedelta(weeks=weeks_ahead)

    query = select(TreasurySecurity).where(
        TreasurySecurity.auction_date >= today,
        TreasurySecurity.auction_date <= end_date,
    )
    count_query = select(TreasurySecurity).where(
        TreasurySecurity.auction_date >= today,
        TreasurySecurity.auction_date <= end_date,
    )

    total_result = await session.execute(
        select(sa_func.count()).select_from(count_query.subquery())
    )
    total_count = total_result.scalar_one()

    offset = (pagination.page - 1) * pagination.page_size
    query = (
        query.order_by(TreasurySecurity.auction_date.asc())
        .offset(offset)
        .limit(pagination.page_size)
    )
    result = await session.execute(query)
    items = result.scalars().all()

    return PaginatedResponse(
        data=[TreasuryAuctionResponse.model_validate(t) for t in items],
        meta=build_paginated_meta(total_count, pagination),
    )


@router.get(
    "/fixed-income/treasuries/auction-results",
    response_model=PaginatedResponse,
)
async def auction_results(
    session: AsyncSession = Depends(get_session),
    pagination: PaginationParams = Depends(get_pagination),
    type: str | None = Query(None, description="Filter by treasury type"),
    start: date | None = Query(None, description="Auction date start"),
    end: date | None = Query(None, description="Auction date end"),
):
    """Historical auction results filtered by type and date range."""
    query = select(TreasurySecurity).where(TreasurySecurity.auction_date.isnot(None))
    count_query = select(TreasurySecurity).where(TreasurySecurity.auction_date.isnot(None))

    if type:
        query = query.where(TreasurySecurity.treasury_type == type.upper())
        count_query = count_query.where(TreasurySecurity.treasury_type == type.upper())
    if start:
        query = query.where(TreasurySecurity.auction_date >= start)
        count_query = count_query.where(TreasurySecurity.auction_date >= start)
    if end:
        query = query.where(TreasurySecurity.auction_date <= end)
        count_query = count_query.where(TreasurySecurity.auction_date <= end)

    total_result = await session.execute(
        select(sa_func.count()).select_from(count_query.subquery())
    )
    total_count = total_result.scalar_one()

    offset = (pagination.page - 1) * pagination.page_size
    query = (
        query.order_by(TreasurySecurity.auction_date.desc())
        .offset(offset)
        .limit(pagination.page_size)
    )
    result = await session.execute(query)
    items = result.scalars().all()

    return PaginatedResponse(
        data=[TreasuryAuctionResponse.model_validate(t) for t in items],
        meta=build_paginated_meta(total_count, pagination),
    )


@router.get(
    "/fixed-income/treasuries/{cusip}",
    response_model=TreasurySecurityResponse,
)
async def get_treasury_by_cusip(
    cusip: str,
    session: AsyncSession = Depends(get_session),
):
    """Get a single treasury security by CUSIP."""
    query = select(TreasurySecurity).where(TreasurySecurity.cusip == cusip)
    result = await session.execute(query)
    treasury = result.scalar_one_or_none()

    if treasury is None:
        raise HTTPException(status_code=404, detail=f"Treasury with CUSIP {cusip} not found")

    return TreasurySecurityResponse.model_validate(treasury)


@router.get(
    "/fixed-income/treasuries/{cusip}/analytics",
)
async def treasury_analytics(
    cusip: str,
    price: float = Query(..., description="Current market price"),
    session: AsyncSession = Depends(get_session),
):
    """Compute YTM, duration, and convexity for a treasury security."""
    query = select(TreasurySecurity).where(TreasurySecurity.cusip == cusip)
    result = await session.execute(query)
    treasury = result.scalar_one_or_none()

    if treasury is None:
        raise HTTPException(status_code=404, detail=f"Treasury with CUSIP {cusip} not found")

    coupon = float(treasury.coupon_rate) if treasury.coupon_rate is not None else 0.0
    freq = treasury.coupon_frequency if treasury.coupon_frequency is not None else 2
    if coupon == 0:
        freq = 0

    today = date.today()
    years_to_maturity = (treasury.maturity_date - today).days / 365.25
    if years_to_maturity < 0:
        years_to_maturity = 0.0

    ytm = compute_treasury_ytm(
        coupon_rate=coupon,
        face_value=100.0,
        price=price,
        years_to_maturity=years_to_maturity,
        frequency=freq if freq > 0 else 2,
    )

    dur_conv = compute_duration_convexity(
        ytm=ytm,
        coupon_rate=coupon,
        years_to_maturity=years_to_maturity,
        frequency=freq if freq > 0 else 2,
    )

    return {
        "cusip": cusip,
        "price": price,
        "ytm": ytm,
        "modified_duration": dur_conv["modified_duration"],
        "macaulay_duration": dur_conv["macaulay_duration"],
        "convexity": dur_conv["convexity"],
        "years_to_maturity": round(years_to_maturity, 4),
    }
