"""Executive/Director Database API endpoints (Pillar 1 Supplement – Part 4)."""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func as sa_func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_pagination, get_session
from src.api.utils.pagination import build_paginated_meta
from src.api.utils.query_filters import escape_like
from src.models.executives import Executive, ExecutiveRole
from src.schemas.common import PaginatedResponse, PaginationParams
from src.schemas.executives import ExecutiveResponse

router = APIRouter(tags=["Executives"])


@router.get(
    "/entities/{entity_id}/executives",
    response_model=PaginatedResponse,
)
async def list_entity_executives(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    pagination: PaginationParams = Depends(get_pagination),
    role_type: str | None = Query(None, description="Filter by role type (EXECUTIVE, DIRECTOR, BOTH)"),
):
    """List executives and directors for an entity."""
    # Find executive IDs that have roles at this entity
    role_query = select(ExecutiveRole.executive_id).where(
        ExecutiveRole.entity_id == entity_id
    )
    if role_type:
        role_query = role_query.where(ExecutiveRole.role_type == role_type.upper())

    exec_ids_subq = role_query.distinct().subquery()

    query = select(Executive).where(Executive.executive_id.in_(select(exec_ids_subq.c.executive_id)))
    count_query = select(Executive).where(Executive.executive_id.in_(select(exec_ids_subq.c.executive_id)))

    total_result = await session.execute(
        select(sa_func.count()).select_from(count_query.subquery())
    )
    total_count = total_result.scalar_one()

    offset = (pagination.page - 1) * pagination.page_size
    query = query.order_by(Executive.person_name).offset(offset).limit(pagination.page_size)
    result = await session.execute(query)
    executives = result.scalars().all()

    return PaginatedResponse(
        data=[ExecutiveResponse.model_validate(e) for e in executives],
        meta=build_paginated_meta(total_count, pagination),
    )


@router.get(
    "/executives/search",
    response_model=PaginatedResponse,
)
async def search_executives(
    session: AsyncSession = Depends(get_session),
    pagination: PaginationParams = Depends(get_pagination),
    name: str | None = Query(None, description="Search by name (case-insensitive contains)"),
):
    """Search executives by name."""
    query = select(Executive)
    count_query = select(Executive)

    if name:
        escaped_name = escape_like(name)
        query = query.where(Executive.person_name.ilike(f"%{escaped_name}%"))
        count_query = count_query.where(Executive.person_name.ilike(f"%{escaped_name}%"))

    total_result = await session.execute(
        select(sa_func.count()).select_from(count_query.subquery())
    )
    total_count = total_result.scalar_one()

    offset = (pagination.page - 1) * pagination.page_size
    query = query.order_by(Executive.person_name).offset(offset).limit(pagination.page_size)
    result = await session.execute(query)
    executives = result.scalars().all()

    return PaginatedResponse(
        data=[ExecutiveResponse.model_validate(e) for e in executives],
        meta=build_paginated_meta(total_count, pagination),
    )
