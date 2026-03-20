"""D5 Corporate Actions API endpoints (Spec 7.7)."""

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func as sa_func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_pagination, get_session
from src.api.utils.pagination import build_paginated_meta
from src.models.corporate_actions import (
    CorporateAction,
    DividendAction,
    MergerAcquisitionAction,
    SplitAction,
)
from src.schemas.common import PaginatedResponse, PaginationParams
from src.schemas.corporate_actions import (
    CorporateActionResponse,
    DividendActionResponse,
    MergerAcquisitionActionResponse,
    SplitActionResponse,
)

router = APIRouter(tags=["Corporate Actions"])


# ── GET /v1/securities/{security_id}/corporate-actions ─────────────

@router.get(
    "/securities/{security_id}/corporate-actions",
    response_model=PaginatedResponse,
)
async def list_security_corporate_actions(
    security_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    pagination: PaginationParams = Depends(get_pagination),
    action_type: str | None = Query(None, description="Filter by action type"),
    status: str | None = Query(None, description="Filter by status"),
):
    """List corporate actions for a specific security."""
    query = select(CorporateAction).where(CorporateAction.security_id == security_id)
    count_query = select(CorporateAction).where(CorporateAction.security_id == security_id)

    if action_type:
        query = query.where(CorporateAction.action_type == action_type.upper())
        count_query = count_query.where(CorporateAction.action_type == action_type.upper())
    if status:
        query = query.where(CorporateAction.status == status.upper())
        count_query = count_query.where(CorporateAction.status == status.upper())

    total_result = await session.execute(
        select(sa_func.count()).select_from(count_query.subquery())
    )
    total_count = total_result.scalar_one()

    offset = (pagination.page - 1) * pagination.page_size
    query = query.order_by(CorporateAction.ex_date.desc().nullslast()).offset(offset).limit(pagination.page_size)
    result = await session.execute(query)
    actions = result.scalars().all()

    return PaginatedResponse(
        data=[CorporateActionResponse.model_validate(a) for a in actions],
        meta=build_paginated_meta(total_count, pagination),
    )


# ── GET /v1/securities/{security_id}/dividends ────────────────────

@router.get(
    "/securities/{security_id}/dividends",
    response_model=PaginatedResponse,
)
async def list_security_dividends(
    security_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    pagination: PaginationParams = Depends(get_pagination),
    dividend_type: str | None = Query(None, description="Filter by dividend type"),
):
    """List dividend actions for a specific security."""
    query = (
        select(CorporateAction)
        .join(DividendAction, CorporateAction.action_id == DividendAction.action_id)
        .where(CorporateAction.security_id == security_id)
    )
    count_query = (
        select(CorporateAction)
        .join(DividendAction, CorporateAction.action_id == DividendAction.action_id)
        .where(CorporateAction.security_id == security_id)
    )

    if dividend_type:
        query = query.where(DividendAction.dividend_type == dividend_type.upper())
        count_query = count_query.where(DividendAction.dividend_type == dividend_type.upper())

    total_result = await session.execute(
        select(sa_func.count()).select_from(count_query.subquery())
    )
    total_count = total_result.scalar_one()

    offset = (pagination.page - 1) * pagination.page_size
    query = query.order_by(CorporateAction.ex_date.desc().nullslast()).offset(offset).limit(pagination.page_size)
    result = await session.execute(query)
    actions = result.scalars().all()

    return PaginatedResponse(
        data=[CorporateActionResponse.model_validate(a) for a in actions],
        meta=build_paginated_meta(total_count, pagination),
    )


# ── GET /v1/securities/{security_id}/splits ────────────────────────

@router.get(
    "/securities/{security_id}/splits",
    response_model=PaginatedResponse,
)
async def list_security_splits(
    security_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    pagination: PaginationParams = Depends(get_pagination),
):
    """List split actions for a specific security."""
    query = (
        select(CorporateAction)
        .join(SplitAction, CorporateAction.action_id == SplitAction.action_id)
        .where(CorporateAction.security_id == security_id)
    )
    count_query = (
        select(CorporateAction)
        .join(SplitAction, CorporateAction.action_id == SplitAction.action_id)
        .where(CorporateAction.security_id == security_id)
    )

    total_result = await session.execute(
        select(sa_func.count()).select_from(count_query.subquery())
    )
    total_count = total_result.scalar_one()

    offset = (pagination.page - 1) * pagination.page_size
    query = query.order_by(CorporateAction.ex_date.desc().nullslast()).offset(offset).limit(pagination.page_size)
    result = await session.execute(query)
    actions = result.scalars().all()

    return PaginatedResponse(
        data=[CorporateActionResponse.model_validate(a) for a in actions],
        meta=build_paginated_meta(total_count, pagination),
    )


# ── GET /v1/corporate-actions/calendar ─────────────────────────────

@router.get("/corporate-actions/calendar", response_model=PaginatedResponse)
async def corporate_actions_calendar(
    session: AsyncSession = Depends(get_session),
    pagination: PaginationParams = Depends(get_pagination),
    start_date: date | None = Query(None, description="Calendar start date"),
    end_date: date | None = Query(None, description="Calendar end date"),
    action_type: str | None = Query(None, description="Filter by action type"),
):
    """Get upcoming corporate actions calendar."""
    query = select(CorporateAction)
    count_query = select(CorporateAction)

    if start_date:
        query = query.where(CorporateAction.ex_date >= start_date)
        count_query = count_query.where(CorporateAction.ex_date >= start_date)
    if end_date:
        query = query.where(CorporateAction.ex_date <= end_date)
        count_query = count_query.where(CorporateAction.ex_date <= end_date)
    if action_type:
        query = query.where(CorporateAction.action_type == action_type.upper())
        count_query = count_query.where(CorporateAction.action_type == action_type.upper())

    total_result = await session.execute(
        select(sa_func.count()).select_from(count_query.subquery())
    )
    total_count = total_result.scalar_one()

    offset = (pagination.page - 1) * pagination.page_size
    query = query.order_by(CorporateAction.ex_date.asc().nullslast()).offset(offset).limit(pagination.page_size)
    result = await session.execute(query)
    actions = result.scalars().all()

    return PaginatedResponse(
        data=[CorporateActionResponse.model_validate(a) for a in actions],
        meta=build_paginated_meta(total_count, pagination),
    )


# ── GET /v1/corporate-actions/{action_id} ──────────────────────────

@router.get("/corporate-actions/{action_id}", response_model=CorporateActionResponse)
async def get_corporate_action(
    action_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get a single corporate action by ID."""
    result = await session.execute(
        select(CorporateAction).where(CorporateAction.action_id == action_id)
    )
    action = result.scalar_one_or_none()
    if not action:
        raise HTTPException(status_code=404, detail=f"Corporate action '{action_id}' not found")

    return CorporateActionResponse.model_validate(action)
