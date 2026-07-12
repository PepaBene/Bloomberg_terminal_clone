"""Fixed Income - Credit Spreads API endpoints (D11 FI Supplement P6)."""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func as sa_func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_pagination, get_session
from src.api.utils.pagination import build_paginated_meta
from src.engines.credit_spread_analytics import (
    compute_ig_hy_differential,
    compute_spread_percentile,
    detect_spread_regime,
)
from src.models.credit_spread import CreditSpreadIndex, CreditSpreadPercentile
from src.schemas.common import PaginatedResponse, PaginationParams
from src.schemas.fi_credit_spread import (
    CreditSpreadIndexResponse,
    CreditSpreadPercentileResponse,
    IGHYDifferentialResponse,
    SpreadRegimeResponse,
)

router = APIRouter(tags=["Fixed Income - Credit Spreads"])


# ── Static routes FIRST ────────────────────────────────────────────


@router.get(
    "/fixed-income/spreads",
    response_model=PaginatedResponse,
)
async def list_spreads(
    session: AsyncSession = Depends(get_session),
    pagination: PaginationParams = Depends(get_pagination),
    rating_category: str | None = Query(None, description="Filter by rating category"),
    source: str | None = Query(None, description="Filter by data source"),
):
    """List all credit spread index observations (paginated), latest values."""
    query = select(CreditSpreadIndex)
    count_query = select(CreditSpreadIndex)

    if rating_category:
        query = query.where(CreditSpreadIndex.rating_category == rating_category.upper())
        count_query = count_query.where(CreditSpreadIndex.rating_category == rating_category.upper())
    if source:
        query = query.where(CreditSpreadIndex.source == source)
        count_query = count_query.where(CreditSpreadIndex.source == source)

    total_result = await session.execute(
        select(sa_func.count()).select_from(count_query.subquery())
    )
    total_count = total_result.scalar_one()

    offset = (pagination.page - 1) * pagination.page_size
    query = (
        query.order_by(CreditSpreadIndex.observation_date.desc())
        .offset(offset)
        .limit(pagination.page_size)
    )
    result = await session.execute(query)
    items = result.scalars().all()

    return PaginatedResponse(
        data=[CreditSpreadIndexResponse.model_validate(i) for i in items],
        meta=build_paginated_meta(total_count, pagination),
    )


@router.get(
    "/fixed-income/spreads/ig",
    response_model=list[CreditSpreadIndexResponse],
)
async def ig_spreads(
    session: AsyncSession = Depends(get_session),
):
    """Get latest IG OAS + breakdown by AAA/AA/A/BBB."""
    ig_categories = {"IG", "AAA", "AA", "A", "BBB"}

    # Get latest observation per series in IG categories
    subq = (
        select(
            CreditSpreadIndex.series_id,
            sa_func.max(CreditSpreadIndex.observation_date).label("max_date"),
        )
        .where(CreditSpreadIndex.rating_category.in_(ig_categories))
        .group_by(CreditSpreadIndex.series_id)
        .subquery()
    )

    query = (
        select(CreditSpreadIndex)
        .join(
            subq,
            (CreditSpreadIndex.series_id == subq.c.series_id)
            & (CreditSpreadIndex.observation_date == subq.c.max_date),
        )
        .order_by(CreditSpreadIndex.rating_category)
    )

    result = await session.execute(query)
    items = result.scalars().all()

    return [CreditSpreadIndexResponse.model_validate(i) for i in items]


@router.get(
    "/fixed-income/spreads/hy",
    response_model=list[CreditSpreadIndexResponse],
)
async def hy_spreads(
    session: AsyncSession = Depends(get_session),
):
    """Get latest HY OAS + breakdown by BB/B/CCC."""
    hy_categories = {"HY", "BB", "B", "CCC"}

    subq = (
        select(
            CreditSpreadIndex.series_id,
            sa_func.max(CreditSpreadIndex.observation_date).label("max_date"),
        )
        .where(CreditSpreadIndex.rating_category.in_(hy_categories))
        .group_by(CreditSpreadIndex.series_id)
        .subquery()
    )

    query = (
        select(CreditSpreadIndex)
        .join(
            subq,
            (CreditSpreadIndex.series_id == subq.c.series_id)
            & (CreditSpreadIndex.observation_date == subq.c.max_date),
        )
        .order_by(CreditSpreadIndex.rating_category)
    )

    result = await session.execute(query)
    items = result.scalars().all()

    return [CreditSpreadIndexResponse.model_validate(i) for i in items]


@router.get(
    "/fixed-income/spreads/ig-hy-differential",
    response_model=IGHYDifferentialResponse,
)
async def ig_hy_differential(
    session: AsyncSession = Depends(get_session),
):
    """Get the current IG vs HY OAS differential (ratio + spread)."""

    async def _latest_spread(rating_category: str) -> float | None:
        result = await session.execute(
            select(CreditSpreadIndex.spread_bps)
            .where(CreditSpreadIndex.rating_category == rating_category)
            .order_by(CreditSpreadIndex.observation_date.desc())
            .limit(1)
        )
        val = result.scalar_one_or_none()
        return float(val) if val is not None else None

    ig_oas = await _latest_spread("IG")
    hy_oas = await _latest_spread("HY")

    if ig_oas is None or hy_oas is None:
        raise HTTPException(
            status_code=404,
            detail="Insufficient IG/HY spread data to compute differential",
        )

    diff = compute_ig_hy_differential(ig_oas, hy_oas)

    return IGHYDifferentialResponse(
        ig_oas=ig_oas,
        hy_oas=hy_oas,
        ratio=diff["ratio"],
        spread=diff["spread"],
    )


@router.get(
    "/fixed-income/spreads/regime",
    response_model=list[SpreadRegimeResponse],
)
async def spread_regime(
    session: AsyncSession = Depends(get_session),
):
    """Get current spread regime per rating category."""
    # Get latest observation per series
    subq = (
        select(
            CreditSpreadIndex.series_id,
            sa_func.max(CreditSpreadIndex.observation_date).label("max_date"),
        )
        .group_by(CreditSpreadIndex.series_id)
        .subquery()
    )

    latest_query = (
        select(CreditSpreadIndex)
        .join(
            subq,
            (CreditSpreadIndex.series_id == subq.c.series_id)
            & (CreditSpreadIndex.observation_date == subq.c.max_date),
        )
    )
    latest_result = await session.execute(latest_query)
    latest_items = latest_result.scalars().all()

    regimes = []
    for item in latest_items:
        if item.spread_bps is None or item.rating_category is None:
            continue

        # Get all historical values for this series
        hist_query = select(CreditSpreadIndex.spread_bps).where(
            CreditSpreadIndex.series_id == item.series_id,
            CreditSpreadIndex.spread_bps.isnot(None),
        )
        hist_result = await session.execute(hist_query)
        hist_values = [float(r[0]) for r in hist_result.all()]

        if not hist_values:
            continue

        try:
            stats = compute_spread_percentile(hist_values, float(item.spread_bps))
        except (ValueError, ZeroDivisionError):
            continue
        regime = detect_spread_regime(stats["percentile"])

        regimes.append(
            SpreadRegimeResponse(
                regime=regime,
                percentile=stats["percentile"],
                current_oas=float(item.spread_bps),
                category=item.rating_category,
            )
        )

    return regimes


@router.get(
    "/fixed-income/spreads/history",
    response_model=PaginatedResponse,
)
async def spread_history(
    session: AsyncSession = Depends(get_session),
    pagination: PaginationParams = Depends(get_pagination),
    series_id: str | None = Query(None, description="FRED series ID"),
    start: date | None = Query(None, description="Start date"),
    end: date | None = Query(None, description="End date"),
):
    """Time series of credit spread observations."""
    query = select(CreditSpreadIndex)
    count_query = select(CreditSpreadIndex)

    if series_id:
        query = query.where(CreditSpreadIndex.series_id == series_id)
        count_query = count_query.where(CreditSpreadIndex.series_id == series_id)
    if start:
        query = query.where(CreditSpreadIndex.observation_date >= start)
        count_query = count_query.where(CreditSpreadIndex.observation_date >= start)
    if end:
        query = query.where(CreditSpreadIndex.observation_date <= end)
        count_query = count_query.where(CreditSpreadIndex.observation_date <= end)

    total_result = await session.execute(
        select(sa_func.count()).select_from(count_query.subquery())
    )
    total_count = total_result.scalar_one()

    offset = (pagination.page - 1) * pagination.page_size
    query = (
        query.order_by(CreditSpreadIndex.observation_date.desc())
        .offset(offset)
        .limit(pagination.page_size)
    )
    result = await session.execute(query)
    items = result.scalars().all()

    return PaginatedResponse(
        data=[CreditSpreadIndexResponse.model_validate(i) for i in items],
        meta=build_paginated_meta(total_count, pagination),
    )


# ── Dynamic routes (with path params) AFTER static ─────────────────


@router.get(
    "/fixed-income/spreads/{series_id}",
    response_model=PaginatedResponse,
)
async def get_series_history(
    series_id: str,
    session: AsyncSession = Depends(get_session),
    pagination: PaginationParams = Depends(get_pagination),
    start: date | None = Query(None, description="Start date"),
    end: date | None = Query(None, description="End date"),
):
    """Get historical spread data for a single series."""
    query = select(CreditSpreadIndex).where(
        CreditSpreadIndex.series_id == series_id
    )
    count_query = select(CreditSpreadIndex).where(
        CreditSpreadIndex.series_id == series_id
    )

    if start:
        query = query.where(CreditSpreadIndex.observation_date >= start)
        count_query = count_query.where(CreditSpreadIndex.observation_date >= start)
    if end:
        query = query.where(CreditSpreadIndex.observation_date <= end)
        count_query = count_query.where(CreditSpreadIndex.observation_date <= end)

    total_result = await session.execute(
        select(sa_func.count()).select_from(count_query.subquery())
    )
    total_count = total_result.scalar_one()

    if total_count == 0:
        raise HTTPException(
            status_code=404,
            detail=f"No data found for series {series_id}",
        )

    offset = (pagination.page - 1) * pagination.page_size
    query = (
        query.order_by(CreditSpreadIndex.observation_date.desc())
        .offset(offset)
        .limit(pagination.page_size)
    )
    result = await session.execute(query)
    items = result.scalars().all()

    return PaginatedResponse(
        data=[CreditSpreadIndexResponse.model_validate(i) for i in items],
        meta=build_paginated_meta(total_count, pagination),
    )


@router.get(
    "/fixed-income/spreads/{series_id}/percentile",
    response_model=list[CreditSpreadPercentileResponse],
)
async def get_series_percentile(
    series_id: str,
    session: AsyncSession = Depends(get_session),
):
    """Get percentile ranks for a series across lookback periods."""
    query = (
        select(CreditSpreadPercentile)
        .where(CreditSpreadPercentile.series_id == series_id)
        .order_by(CreditSpreadPercentile.as_of_date.desc())
    )
    result = await session.execute(query)
    items = result.scalars().all()

    if not items:
        raise HTTPException(
            status_code=404,
            detail=f"No percentile data found for series {series_id}",
        )

    return [CreditSpreadPercentileResponse.model_validate(i) for i in items]
