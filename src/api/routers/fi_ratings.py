"""Fixed Income - Credit Ratings API endpoints (D11 FI Supplement P5)."""

import uuid
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func as sa_func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_pagination, get_session
from src.api.utils.pagination import build_paginated_meta
from src.engines.credit_rating_analytics import compute_migration_matrix
from src.models.credit_rating import CreditRatingEvent, CurrentCreditRating
from src.schemas.common import PaginatedResponse, PaginationParams
from src.schemas.fi_credit_rating import (
    CreditRatingEventResponse,
    CurrentCreditRatingResponse,
    FallenAngelResponse,
    RatingActionResponse,
    RatingMigrationMatrixResponse,
    RisingStarResponse,
)

router = APIRouter(tags=["Fixed Income - Credit Ratings"])


# ── Static routes FIRST ────────────────────────────────────────────


@router.get(
    "/fixed-income/ratings/fallen-angels",
    response_model=PaginatedResponse,
)
async def get_fallen_angels(
    session: AsyncSession = Depends(get_session),
    pagination: PaginationParams = Depends(get_pagination),
    date_from: date | None = Query(None, description="Filter events from this date"),
):
    """List fallen angel events (IG to HY downgrades)."""
    query = select(CreditRatingEvent).where(
        CreditRatingEvent.is_fallen_angel == True  # noqa: E712
    )
    count_query = select(CreditRatingEvent).where(
        CreditRatingEvent.is_fallen_angel == True  # noqa: E712
    )

    if date_from:
        query = query.where(CreditRatingEvent.event_date >= date_from)
        count_query = count_query.where(CreditRatingEvent.event_date >= date_from)

    total_result = await session.execute(
        select(sa_func.count()).select_from(count_query.subquery())
    )
    total_count = total_result.scalar_one()

    offset = (pagination.page - 1) * pagination.page_size
    query = (
        query.order_by(CreditRatingEvent.event_date.desc())
        .offset(offset)
        .limit(pagination.page_size)
    )
    result = await session.execute(query)
    events = result.scalars().all()

    return PaginatedResponse(
        data=[FallenAngelResponse.model_validate(e) for e in events],
        meta=build_paginated_meta(total_count, pagination),
    )


@router.get(
    "/fixed-income/ratings/rising-stars",
    response_model=PaginatedResponse,
)
async def get_rising_stars(
    session: AsyncSession = Depends(get_session),
    pagination: PaginationParams = Depends(get_pagination),
    date_from: date | None = Query(None, description="Filter events from this date"),
):
    """List rising star events (HY to IG upgrades)."""
    query = select(CreditRatingEvent).where(
        CreditRatingEvent.is_rising_star == True  # noqa: E712
    )
    count_query = select(CreditRatingEvent).where(
        CreditRatingEvent.is_rising_star == True  # noqa: E712
    )

    if date_from:
        query = query.where(CreditRatingEvent.event_date >= date_from)
        count_query = count_query.where(CreditRatingEvent.event_date >= date_from)

    total_result = await session.execute(
        select(sa_func.count()).select_from(count_query.subquery())
    )
    total_count = total_result.scalar_one()

    offset = (pagination.page - 1) * pagination.page_size
    query = (
        query.order_by(CreditRatingEvent.event_date.desc())
        .offset(offset)
        .limit(pagination.page_size)
    )
    result = await session.execute(query)
    events = result.scalars().all()

    return PaginatedResponse(
        data=[RisingStarResponse.model_validate(e) for e in events],
        meta=build_paginated_meta(total_count, pagination),
    )


@router.get(
    "/fixed-income/ratings/recent",
    response_model=PaginatedResponse,
)
async def get_recent_actions(
    session: AsyncSession = Depends(get_session),
    pagination: PaginationParams = Depends(get_pagination),
    days: int = Query(30, ge=1, le=3650, description="Look back N days"),
    direction: str | None = Query(None, description="Filter by direction (UPGRADE, DOWNGRADE, etc.)"),
    agency: str | None = Query(None, description="Filter by agency (SP, MOODYS, FITCH)"),
):
    """List recent credit rating actions."""
    cutoff = date.today() - timedelta(days=days)

    query = select(CreditRatingEvent).where(CreditRatingEvent.event_date >= cutoff)
    count_query = select(CreditRatingEvent).where(CreditRatingEvent.event_date >= cutoff)

    if direction:
        query = query.where(CreditRatingEvent.direction == direction.upper())
        count_query = count_query.where(CreditRatingEvent.direction == direction.upper())
    if agency:
        query = query.where(CreditRatingEvent.agency == agency.upper())
        count_query = count_query.where(CreditRatingEvent.agency == agency.upper())

    total_result = await session.execute(
        select(sa_func.count()).select_from(count_query.subquery())
    )
    total_count = total_result.scalar_one()

    offset = (pagination.page - 1) * pagination.page_size
    query = (
        query.order_by(CreditRatingEvent.event_date.desc())
        .offset(offset)
        .limit(pagination.page_size)
    )
    result = await session.execute(query)
    events = result.scalars().all()

    return PaginatedResponse(
        data=[RatingActionResponse.model_validate(e) for e in events],
        meta=build_paginated_meta(total_count, pagination),
    )


@router.get(
    "/fixed-income/ratings/migration-matrix",
    response_model=RatingMigrationMatrixResponse,
)
async def get_migration_matrix(
    session: AsyncSession = Depends(get_session),
    start: date | None = Query(None, description="Start date"),
    end: date | None = Query(None, description="End date"),
):
    """Compute a rating migration/transition matrix over a date range."""
    query = select(CreditRatingEvent).where(
        CreditRatingEvent.old_rating.isnot(None),
        CreditRatingEvent.new_rating.isnot(None),
    )

    if start:
        query = query.where(CreditRatingEvent.event_date >= start)
    if end:
        query = query.where(CreditRatingEvent.event_date <= end)

    result = await session.execute(query)
    events = result.scalars().all()

    event_dicts = [
        {"old_rating": e.old_rating, "new_rating": e.new_rating}
        for e in events
    ]
    matrix = compute_migration_matrix(event_dicts)
    total = sum(sum(row.values()) for row in matrix.values())

    return RatingMigrationMatrixResponse(
        matrix=matrix,
        total_transitions=total,
        start_date=start,
        end_date=end,
    )


# ── Dynamic routes (with path params) AFTER static ─────────────────


@router.get(
    "/fixed-income/ratings/entity/{entity_id}",
    response_model=list[CurrentCreditRatingResponse],
)
async def get_entity_current_ratings(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get current credit ratings for an entity across all agencies."""
    query = select(CurrentCreditRating).where(
        CurrentCreditRating.entity_id == entity_id
    )
    result = await session.execute(query)
    ratings = result.scalars().all()

    if not ratings:
        raise HTTPException(
            status_code=404,
            detail=f"No current ratings found for entity {entity_id}",
        )

    return [CurrentCreditRatingResponse.model_validate(r) for r in ratings]


@router.get(
    "/fixed-income/ratings/entity/{entity_id}/history",
    response_model=PaginatedResponse,
)
async def get_entity_rating_history(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    pagination: PaginationParams = Depends(get_pagination),
    agency: str | None = Query(None, description="Filter by agency"),
    start: date | None = Query(None, description="Start date"),
    end: date | None = Query(None, description="End date"),
):
    """Get full credit rating event history for an entity (paginated)."""
    query = select(CreditRatingEvent).where(
        CreditRatingEvent.entity_id == entity_id
    )
    count_query = select(CreditRatingEvent).where(
        CreditRatingEvent.entity_id == entity_id
    )

    if agency:
        query = query.where(CreditRatingEvent.agency == agency.upper())
        count_query = count_query.where(CreditRatingEvent.agency == agency.upper())
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
        query.order_by(CreditRatingEvent.event_date.desc())
        .offset(offset)
        .limit(pagination.page_size)
    )
    result = await session.execute(query)
    events = result.scalars().all()

    return PaginatedResponse(
        data=[CreditRatingEventResponse.model_validate(e) for e in events],
        meta=build_paginated_meta(total_count, pagination),
    )
