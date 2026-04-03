"""Yield Curve API endpoints (Pillar 1 Supplement – Part 2)."""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func as sa_func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_pagination, get_session
from src.api.utils.pagination import build_paginated_meta
from src.models.yield_curve import YieldCurveSnapshot, ZeroCouponCurve
from src.schemas.common import PaginatedResponse, PaginationParams
from src.schemas.yield_curve import (
    ForwardCurveResponse,
    YieldCurveSnapshotResponse,
    ZeroCouponCurveResponse,
)

router = APIRouter(tags=["Yield Curve"])


@router.get(
    "/macro/yield-curve",
    response_model=YieldCurveSnapshotResponse,
)
async def get_yield_curve(
    session: AsyncSession = Depends(get_session),
    curve_date: date | None = Query(None, description="Specific date (defaults to latest)"),
    curve_type: str = Query("TREASURY_NOMINAL", description="Curve type"),
):
    """Return the yield curve snapshot for a given date and type."""
    query = (
        select(YieldCurveSnapshot)
        .where(YieldCurveSnapshot.curve_type == curve_type.upper())
        .order_by(YieldCurveSnapshot.curve_date.desc())
    )
    if curve_date:
        query = query.where(YieldCurveSnapshot.curve_date == curve_date)
    query = query.limit(1)

    result = await session.execute(query)
    snapshot = result.scalar_one_or_none()
    if not snapshot:
        detail = (
            f"No yield curve data found for date '{curve_date}' and type '{curve_type}'"
            if curve_date
            else f"No yield curve data found for type '{curve_type}'"
        )
        raise HTTPException(status_code=404, detail=detail)
    return YieldCurveSnapshotResponse.model_validate(snapshot)


@router.get(
    "/macro/yield-curve/history",
    response_model=PaginatedResponse,
)
async def list_yield_curve_history(
    session: AsyncSession = Depends(get_session),
    pagination: PaginationParams = Depends(get_pagination),
    curve_type: str = Query("TREASURY_NOMINAL", description="Curve type"),
    start: date | None = Query(None, description="Start date"),
    end: date | None = Query(None, description="End date"),
):
    """Return historical yield curve snapshots."""
    query = select(YieldCurveSnapshot).where(
        YieldCurveSnapshot.curve_type == curve_type.upper()
    )
    count_query = select(YieldCurveSnapshot).where(
        YieldCurveSnapshot.curve_type == curve_type.upper()
    )

    if start:
        query = query.where(YieldCurveSnapshot.curve_date >= start)
        count_query = count_query.where(YieldCurveSnapshot.curve_date >= start)
    if end:
        query = query.where(YieldCurveSnapshot.curve_date <= end)
        count_query = count_query.where(YieldCurveSnapshot.curve_date <= end)

    total_result = await session.execute(
        select(sa_func.count()).select_from(count_query.subquery())
    )
    total_count = total_result.scalar_one()

    offset = (pagination.page - 1) * pagination.page_size
    query = (
        query.order_by(YieldCurveSnapshot.curve_date.desc())
        .offset(offset)
        .limit(pagination.page_size)
    )
    result = await session.execute(query)
    snapshots = result.scalars().all()

    return PaginatedResponse(
        data=[YieldCurveSnapshotResponse.model_validate(s) for s in snapshots],
        meta=build_paginated_meta(total_count, pagination),
    )


@router.get(
    "/macro/yield-curve/forwards",
    response_model=ForwardCurveResponse,
)
async def get_forward_curve(
    session: AsyncSession = Depends(get_session),
    curve_date: date | None = Query(None, description="Date (defaults to latest)"),
):
    """Return bootstrapped zero-coupon / forward curve."""
    if curve_date:
        query = (
            select(ZeroCouponCurve)
            .where(ZeroCouponCurve.curve_date == curve_date)
            .order_by(ZeroCouponCurve.tenor_years.asc())
        )
    else:
        # Use subquery to atomically find latest date and fetch data
        latest_date_subq = select(sa_func.max(ZeroCouponCurve.curve_date)).scalar_subquery()
        query = (
            select(ZeroCouponCurve)
            .where(ZeroCouponCurve.curve_date == latest_date_subq)
            .order_by(ZeroCouponCurve.tenor_years.asc())
        )

    result = await session.execute(query)
    points = result.scalars().all()
    if not points:
        raise HTTPException(status_code=404, detail="No forward curve data found")

    # If no explicit curve_date was provided, use the date from the first result
    if curve_date is None:
        curve_date = points[0].curve_date

    return ForwardCurveResponse(
        curve_date=curve_date,
        points=[ZeroCouponCurveResponse.model_validate(p) for p in points],
    )
