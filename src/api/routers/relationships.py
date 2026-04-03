"""D10 Business Relationships API endpoints (Spec 12.7)."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func as sa_func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_pagination, get_session
from src.api.utils.pagination import build_paginated_meta
from src.models.relationships import BusinessRelationship, RelationshipHistory
from src.schemas.common import PaginatedResponse, PaginationParams
from src.schemas.relationships import (
    BusinessRelationshipBriefResponse,
    BusinessRelationshipResponse,
    RelationshipHistoryResponse,
)

router = APIRouter(tags=["Business Relationships"])


# Customer relationship types
_CUSTOMER_TYPES = {"MAJOR_CUSTOMER", "SIGNIFICANT_CUSTOMER", "KNOWN_CUSTOMER"}

# Supplier relationship types
_SUPPLIER_TYPES = {"CRITICAL_SUPPLIER", "MAJOR_SUPPLIER", "KNOWN_SUPPLIER", "DISTRIBUTOR"}

# Competitor relationship types
_COMPETITOR_TYPES = {"DIRECT_COMPETITOR", "INDIRECT_COMPETITOR"}


# ── GET /v1/entities/{entity_id}/business-relationships ────────────

@router.get(
    "/entities/{entity_id}/business-relationships",
    response_model=PaginatedResponse,
)
async def list_business_relationships(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    pagination: PaginationParams = Depends(get_pagination),
    relationship_type: str | None = Query(None, description="Filter by relationship type"),
    active: bool | None = Query(None, description="Filter by active status"),
):
    """List all business relationships for an entity."""
    query = select(BusinessRelationship).where(
        (BusinessRelationship.source_entity_id == entity_id)
        | (BusinessRelationship.target_entity_id == entity_id)
    )
    count_query = select(BusinessRelationship).where(
        (BusinessRelationship.source_entity_id == entity_id)
        | (BusinessRelationship.target_entity_id == entity_id)
    )

    if relationship_type:
        query = query.where(BusinessRelationship.relationship_type == relationship_type.upper())
        count_query = count_query.where(
            BusinessRelationship.relationship_type == relationship_type.upper()
        )

    if active is True:
        query = query.where(BusinessRelationship.is_active.is_(True))
        count_query = count_query.where(BusinessRelationship.is_active.is_(True))
    elif active is False:
        query = query.where(BusinessRelationship.is_active.is_(False))
        count_query = count_query.where(BusinessRelationship.is_active.is_(False))

    total_result = await session.execute(
        select(sa_func.count()).select_from(count_query.subquery())
    )
    total_count = total_result.scalar_one()

    offset = (pagination.page - 1) * pagination.page_size
    query = (
        query.order_by(BusinessRelationship.effective_date.desc().nulls_last())
        .offset(offset)
        .limit(pagination.page_size)
    )
    result = await session.execute(query)
    relationships = result.scalars().all()

    return PaginatedResponse(
        data=[BusinessRelationshipBriefResponse.model_validate(r) for r in relationships],
        meta=build_paginated_meta(total_count, pagination),
    )


# ── GET /v1/entities/{entity_id}/business-relationships/customers ──

@router.get(
    "/entities/{entity_id}/business-relationships/customers",
    response_model=PaginatedResponse,
)
async def list_customers(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    pagination: PaginationParams = Depends(get_pagination),
    active: bool | None = Query(None, description="Filter by active status"),
):
    """List customer relationships for an entity."""
    query = select(BusinessRelationship).where(
        or_(
            BusinessRelationship.source_entity_id == entity_id,
            BusinessRelationship.target_entity_id == entity_id,
        )
    ).where(BusinessRelationship.relationship_type.in_(_CUSTOMER_TYPES))
    count_query = select(BusinessRelationship).where(
        or_(
            BusinessRelationship.source_entity_id == entity_id,
            BusinessRelationship.target_entity_id == entity_id,
        )
    ).where(BusinessRelationship.relationship_type.in_(_CUSTOMER_TYPES))

    if active is True:
        query = query.where(BusinessRelationship.is_active.is_(True))
        count_query = count_query.where(BusinessRelationship.is_active.is_(True))
    elif active is False:
        query = query.where(BusinessRelationship.is_active.is_(False))
        count_query = count_query.where(BusinessRelationship.is_active.is_(False))

    total_result = await session.execute(
        select(sa_func.count()).select_from(count_query.subquery())
    )
    total_count = total_result.scalar_one()

    offset = (pagination.page - 1) * pagination.page_size
    query = (
        query.order_by(BusinessRelationship.effective_date.desc().nulls_last())
        .offset(offset)
        .limit(pagination.page_size)
    )
    result = await session.execute(query)
    relationships = result.scalars().all()

    return PaginatedResponse(
        data=[BusinessRelationshipBriefResponse.model_validate(r) for r in relationships],
        meta=build_paginated_meta(total_count, pagination),
    )


# ── GET /v1/entities/{entity_id}/business-relationships/suppliers ──

@router.get(
    "/entities/{entity_id}/business-relationships/suppliers",
    response_model=PaginatedResponse,
)
async def list_suppliers(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    pagination: PaginationParams = Depends(get_pagination),
    active: bool | None = Query(None, description="Filter by active status"),
):
    """List supplier relationships for an entity."""
    query = select(BusinessRelationship).where(
        or_(
            BusinessRelationship.source_entity_id == entity_id,
            BusinessRelationship.target_entity_id == entity_id,
        )
    ).where(BusinessRelationship.relationship_type.in_(_SUPPLIER_TYPES))
    count_query = select(BusinessRelationship).where(
        or_(
            BusinessRelationship.source_entity_id == entity_id,
            BusinessRelationship.target_entity_id == entity_id,
        )
    ).where(BusinessRelationship.relationship_type.in_(_SUPPLIER_TYPES))

    if active is True:
        query = query.where(BusinessRelationship.is_active.is_(True))
        count_query = count_query.where(BusinessRelationship.is_active.is_(True))
    elif active is False:
        query = query.where(BusinessRelationship.is_active.is_(False))
        count_query = count_query.where(BusinessRelationship.is_active.is_(False))

    total_result = await session.execute(
        select(sa_func.count()).select_from(count_query.subquery())
    )
    total_count = total_result.scalar_one()

    offset = (pagination.page - 1) * pagination.page_size
    query = (
        query.order_by(BusinessRelationship.effective_date.desc().nulls_last())
        .offset(offset)
        .limit(pagination.page_size)
    )
    result = await session.execute(query)
    relationships = result.scalars().all()

    return PaginatedResponse(
        data=[BusinessRelationshipBriefResponse.model_validate(r) for r in relationships],
        meta=build_paginated_meta(total_count, pagination),
    )


# ── GET /v1/entities/{entity_id}/business-relationships/competitors ─

@router.get(
    "/entities/{entity_id}/business-relationships/competitors",
    response_model=PaginatedResponse,
)
async def list_competitors(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    pagination: PaginationParams = Depends(get_pagination),
    active: bool | None = Query(None, description="Filter by active status"),
):
    """List competitor relationships for an entity."""
    query = select(BusinessRelationship).where(
        or_(
            BusinessRelationship.source_entity_id == entity_id,
            BusinessRelationship.target_entity_id == entity_id,
        )
    ).where(BusinessRelationship.relationship_type.in_(_COMPETITOR_TYPES))
    count_query = select(BusinessRelationship).where(
        or_(
            BusinessRelationship.source_entity_id == entity_id,
            BusinessRelationship.target_entity_id == entity_id,
        )
    ).where(BusinessRelationship.relationship_type.in_(_COMPETITOR_TYPES))

    if active is True:
        query = query.where(BusinessRelationship.is_active.is_(True))
        count_query = count_query.where(BusinessRelationship.is_active.is_(True))
    elif active is False:
        query = query.where(BusinessRelationship.is_active.is_(False))
        count_query = count_query.where(BusinessRelationship.is_active.is_(False))

    total_result = await session.execute(
        select(sa_func.count()).select_from(count_query.subquery())
    )
    total_count = total_result.scalar_one()

    offset = (pagination.page - 1) * pagination.page_size
    query = (
        query.order_by(BusinessRelationship.effective_date.desc().nulls_last())
        .offset(offset)
        .limit(pagination.page_size)
    )
    result = await session.execute(query)
    relationships = result.scalars().all()

    return PaginatedResponse(
        data=[BusinessRelationshipBriefResponse.model_validate(r) for r in relationships],
        meta=build_paginated_meta(total_count, pagination),
    )


# ── GET /v1/business-relationships/{relationship_id} ───────────────

@router.get(
    "/business-relationships/{relationship_id}",
    response_model=BusinessRelationshipResponse,
)
async def get_business_relationship(
    relationship_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get a single business relationship by ID."""
    result = await session.execute(
        select(BusinessRelationship).where(
            BusinessRelationship.relationship_id == relationship_id
        )
    )
    relationship = result.scalar_one_or_none()
    if not relationship:
        raise HTTPException(
            status_code=404,
            detail=f"Business relationship '{relationship_id}' not found",
        )
    return BusinessRelationshipResponse.model_validate(relationship)


# ── GET /v1/business-relationships/{relationship_id}/history ───────

@router.get(
    "/business-relationships/{relationship_id}/history",
    response_model=PaginatedResponse,
)
async def get_business_relationship_history(
    relationship_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    pagination: PaginationParams = Depends(get_pagination),
):
    """Get change history for a business relationship."""
    # Verify relationship exists
    rel_result = await session.execute(
        select(BusinessRelationship.relationship_id).where(
            BusinessRelationship.relationship_id == relationship_id
        )
    )
    if not rel_result.scalar_one_or_none():
        raise HTTPException(
            status_code=404,
            detail=f"Business relationship '{relationship_id}' not found",
        )

    query = select(RelationshipHistory).where(
        RelationshipHistory.relationship_id == relationship_id
    )
    count_query = select(RelationshipHistory).where(
        RelationshipHistory.relationship_id == relationship_id
    )

    total_result = await session.execute(
        select(sa_func.count()).select_from(count_query.subquery())
    )
    total_count = total_result.scalar_one()

    offset = (pagination.page - 1) * pagination.page_size
    query = (
        query.order_by(RelationshipHistory.created_at.desc())
        .offset(offset)
        .limit(pagination.page_size)
    )
    result = await session.execute(query)
    history = result.scalars().all()

    return PaginatedResponse(
        data=[RelationshipHistoryResponse.model_validate(h) for h in history],
        meta=build_paginated_meta(total_count, pagination),
    )
