"""D1 Entity Master API endpoints (Spec 3.7)."""

import uuid
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func as sa_func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_pagination, get_session
from src.api.utils.pagination import build_paginated_meta
from src.api.utils.query_filters import escape_like
from src.models.entity import (
    Entity,
    EntityHistory,
    EntityIdentifier,
    EntityName,
    EntityRelationship,
)
from src.models.security import Security
from src.schemas.common import PaginatedResponse, PaginationParams
from src.schemas.entity import (
    BulkLookupRequest,
    BulkLookupResponse,
    EntityBriefResponse,
    EntityHierarchyResponse,
    EntityHistoryResponse,
    EntityRelationshipResponse,
    EntityResolveRequest,
    EntityResolveResponse,
    EntityResponse,
    EntitySearchResponse,
    EntitySearchResult,
)
from src.schemas.security import SecurityBriefResponse

router = APIRouter(prefix="/entities", tags=["Entities"])


# ── GET /v1/entities/search ────────────────────────────────────────
# NOTE: This must be declared BEFORE the /{entity_id} route so FastAPI
# does not interpret "search" as a path parameter.

@router.get("/search", response_model=EntitySearchResponse)
async def search_entities(
    q: str = Query(..., min_length=1, description="Search query"),
    entity_type: str | None = Query(None),
    country: str | None = Query(None),
    status: str | None = Query(None),
    session: AsyncSession = Depends(get_session),
    pagination: PaginationParams = Depends(get_pagination),
):
    """Fuzzy search for entities by name.

    Uses SQL ILIKE as a placeholder until Elasticsearch is wired up.
    """
    escaped_q = escape_like(q)
    query = select(Entity).where(
        Entity.legal_name.ilike(f"%{escaped_q}%")
        | Entity.short_name.ilike(f"%{escaped_q}%")
    )

    if entity_type:
        query = query.where(Entity.entity_type == entity_type)
    if country:
        query = query.where(Entity.incorporation_country == country.upper())
    if status:
        query = query.where(Entity.status == status.upper())

    # Count
    total_result = await session.execute(
        select(sa_func.count()).select_from(query.subquery())
    )
    total_count = total_result.scalar_one()

    # Paginate
    offset = (pagination.page - 1) * pagination.page_size
    query = query.order_by(Entity.legal_name).offset(offset).limit(pagination.page_size)
    result = await session.execute(query)
    entities = result.scalars().all()

    results = [
        EntitySearchResult(
            entity_id=e.entity_id,
            legal_name=e.legal_name,
            short_name=e.short_name,
            entity_type=e.entity_type,
            status=e.status,
            incorporation_country=e.incorporation_country,
            score=1.0,  # Placeholder score; real scoring via ES later
        )
        for e in entities
    ]

    return EntitySearchResponse(results=results, total=total_count, query=q)


# ── GET /v1/entities/{entity_id} ───────────────────────────────────

@router.get("/{entity_id}", response_model=EntityResponse)
async def get_entity(
    entity_id: uuid.UUID,
    expand: list[str] = Query(default=[]),
    session: AsyncSession = Depends(get_session),
):
    """Get a single entity by ID with optional expansion.

    Supported expand values: identifiers, names, relationships
    """
    result = await session.execute(
        select(Entity).where(Entity.entity_id == entity_id)
    )
    entity = result.scalar_one_or_none()
    if not entity:
        raise HTTPException(status_code=404, detail=f"Entity '{entity_id}' not found")

    resp = EntityResponse.model_validate(entity)

    # Only include expanded fields when requested
    if "identifiers" not in expand:
        resp.identifiers = None
    if "names" not in expand:
        resp.names = None

    # Relationships require a separate query
    if "relationships" in expand:
        rel_result = await session.execute(
            select(EntityRelationship).where(
                (EntityRelationship.source_entity_id == entity_id)
                | (EntityRelationship.target_entity_id == entity_id)
            )
        )
        _ = rel_result.scalars().all()  # available for future schema extension

    return resp


# ── GET /v1/entities ───────────────────────────────────────────────

@router.get("", response_model=PaginatedResponse)
async def list_entities(
    session: AsyncSession = Depends(get_session),
    pagination: PaginationParams = Depends(get_pagination),
    lei: str | None = Query(None, description="Filter by LEI"),
    cik: str | None = Query(None, description="Filter by SEC CIK"),
    status: str | None = Query(None),
    country: str | None = Query(None, description="ISO 3166-1 alpha-2"),
    entity_type: str | None = Query(None),
):
    """List / filter entities.

    Identifier-based filters (lei, cik) join through entity_identifiers.
    """
    query = select(Entity)
    count_query = select(Entity)

    # Identifier-based filters
    if lei:
        sub = select(EntityIdentifier.entity_id).where(
            EntityIdentifier.identifier_type == "LEI",
            EntityIdentifier.identifier_value == lei,
        )
        query = query.where(Entity.entity_id.in_(sub))
        count_query = count_query.where(Entity.entity_id.in_(sub))
    if cik:
        sub = select(EntityIdentifier.entity_id).where(
            EntityIdentifier.identifier_type == "CIK",
            EntityIdentifier.identifier_value == cik,
        )
        query = query.where(Entity.entity_id.in_(sub))
        count_query = count_query.where(Entity.entity_id.in_(sub))

    # Direct column filters
    if status:
        query = query.where(Entity.status == status.upper())
        count_query = count_query.where(Entity.status == status.upper())
    if country:
        query = query.where(Entity.incorporation_country == country.upper())
        count_query = count_query.where(Entity.incorporation_country == country.upper())
    if entity_type:
        query = query.where(Entity.entity_type == entity_type)
        count_query = count_query.where(Entity.entity_type == entity_type)

    # Count
    total_result = await session.execute(
        select(sa_func.count()).select_from(count_query.subquery())
    )
    total_count = total_result.scalar_one()

    # Paginate
    offset = (pagination.page - 1) * pagination.page_size
    query = query.order_by(Entity.legal_name).offset(offset).limit(pagination.page_size)
    result = await session.execute(query)
    entities = result.scalars().all()

    return PaginatedResponse(
        data=[EntityBriefResponse.model_validate(e) for e in entities],
        meta=build_paginated_meta(total_count, pagination),
    )


# ── GET /v1/entities/{id}/hierarchy ────────────────────────────────

@router.get("/{entity_id}/hierarchy", response_model=EntityHierarchyResponse)
async def get_entity_hierarchy(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get the corporate tree for an entity.

    Returns the ultimate parent, immediate parent, and direct subsidiaries.
    Uses simple parent lookups (not a recursive CTE) for clarity.
    """
    # Fetch the entity itself
    result = await session.execute(
        select(Entity).where(Entity.entity_id == entity_id)
    )
    entity = result.scalar_one_or_none()
    if not entity:
        raise HTTPException(status_code=404, detail=f"Entity '{entity_id}' not found")

    # Ultimate parent
    ultimate_parent = None
    if entity.ultimate_parent_id and entity.ultimate_parent_id != entity_id:
        up_result = await session.execute(
            select(Entity).where(Entity.entity_id == entity.ultimate_parent_id)
        )
        up = up_result.scalar_one_or_none()
        if up:
            ultimate_parent = EntityBriefResponse.model_validate(up)

    # Immediate parent
    immediate_parent = None
    if entity.immediate_parent_id and entity.immediate_parent_id != entity_id:
        ip_result = await session.execute(
            select(Entity).where(Entity.entity_id == entity.immediate_parent_id)
        )
        ip = ip_result.scalar_one_or_none()
        if ip:
            immediate_parent = EntityBriefResponse.model_validate(ip)

    # Direct subsidiaries (entities whose immediate_parent_id == this entity)
    sub_result = await session.execute(
        select(Entity)
        .where(Entity.immediate_parent_id == entity_id)
        .order_by(Entity.legal_name)
    )
    subsidiaries = [
        EntityBriefResponse.model_validate(s) for s in sub_result.scalars().all()
    ]

    return EntityHierarchyResponse(
        entity_id=entity.entity_id,
        legal_name=entity.legal_name,
        ultimate_parent=ultimate_parent,
        immediate_parent=immediate_parent,
        subsidiaries=subsidiaries,
    )


# ── GET /v1/entities/{id}/securities ───────────────────────────────

@router.get("/{entity_id}/securities", response_model=PaginatedResponse)
async def get_entity_securities(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    pagination: PaginationParams = Depends(get_pagination),
    asset_class: str | None = Query(None),
    status: str | None = Query(None),
):
    """Get securities issued by an entity."""
    # Verify entity exists
    ent_result = await session.execute(
        select(Entity.entity_id).where(Entity.entity_id == entity_id)
    )
    if not ent_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail=f"Entity '{entity_id}' not found")

    query = select(Security).where(Security.issuer_entity_id == entity_id)
    count_query = select(Security).where(Security.issuer_entity_id == entity_id)

    if asset_class:
        query = query.where(Security.asset_class == asset_class.upper())
        count_query = count_query.where(Security.asset_class == asset_class.upper())
    if status:
        query = query.where(Security.status == status.upper())
        count_query = count_query.where(Security.status == status.upper())

    total_result = await session.execute(
        select(sa_func.count()).select_from(count_query.subquery())
    )
    total_count = total_result.scalar_one()

    offset = (pagination.page - 1) * pagination.page_size
    query = query.order_by(Security.name).offset(offset).limit(pagination.page_size)
    result = await session.execute(query)
    securities = result.scalars().all()

    return PaginatedResponse(
        data=[SecurityBriefResponse.model_validate(s) for s in securities],
        meta=build_paginated_meta(total_count, pagination),
    )


# ── GET /v1/entities/{id}/history ──────────────────────────────────

@router.get("/{entity_id}/history", response_model=PaginatedResponse)
async def get_entity_history(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    pagination: PaginationParams = Depends(get_pagination),
    as_of: datetime | None = Query(None, description="Point-in-time snapshot"),
):
    """Get entity change history, optionally filtered to a point in time."""
    # Verify entity exists
    ent_result = await session.execute(
        select(Entity.entity_id).where(Entity.entity_id == entity_id)
    )
    if not ent_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail=f"Entity '{entity_id}' not found")

    query = select(EntityHistory).where(EntityHistory.entity_id == entity_id)
    count_query = select(EntityHistory).where(EntityHistory.entity_id == entity_id)

    if as_of:
        query = query.where(
            EntityHistory.valid_from <= as_of,
            (EntityHistory.valid_to.is_(None)) | (EntityHistory.valid_to > as_of),
        )
        count_query = count_query.where(
            EntityHistory.valid_from <= as_of,
            (EntityHistory.valid_to.is_(None)) | (EntityHistory.valid_to > as_of),
        )

    total_result = await session.execute(
        select(sa_func.count()).select_from(count_query.subquery())
    )
    total_count = total_result.scalar_one()

    offset = (pagination.page - 1) * pagination.page_size
    query = (
        query.order_by(EntityHistory.valid_from.desc())
        .offset(offset)
        .limit(pagination.page_size)
    )
    result = await session.execute(query)
    history = result.scalars().all()

    return PaginatedResponse(
        data=[EntityHistoryResponse.model_validate(h) for h in history],
        meta=build_paginated_meta(total_count, pagination),
    )


# ── GET /v1/entities/{id}/relationships ────────────────────────────

@router.get("/{entity_id}/relationships", response_model=PaginatedResponse)
async def get_entity_relationships(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    pagination: PaginationParams = Depends(get_pagination),
    type: str | None = Query(None, description="Relationship type filter"),
    active: bool | None = Query(None, description="Active-only filter"),
):
    """Get relationships for an entity, optionally filtered by type and active status."""
    # Verify entity exists
    ent_result = await session.execute(
        select(Entity.entity_id).where(Entity.entity_id == entity_id)
    )
    if not ent_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail=f"Entity '{entity_id}' not found")

    query = select(EntityRelationship).where(
        (EntityRelationship.source_entity_id == entity_id)
        | (EntityRelationship.target_entity_id == entity_id)
    )
    count_query = select(EntityRelationship).where(
        (EntityRelationship.source_entity_id == entity_id)
        | (EntityRelationship.target_entity_id == entity_id)
    )

    if type:
        query = query.where(EntityRelationship.relationship_type == type)
        count_query = count_query.where(EntityRelationship.relationship_type == type)

    if active is True:
        query = query.where(EntityRelationship.termination_date.is_(None))
        count_query = count_query.where(EntityRelationship.termination_date.is_(None))
    elif active is False:
        query = query.where(EntityRelationship.termination_date.isnot(None))
        count_query = count_query.where(EntityRelationship.termination_date.isnot(None))

    total_result = await session.execute(
        select(sa_func.count()).select_from(count_query.subquery())
    )
    total_count = total_result.scalar_one()

    offset = (pagination.page - 1) * pagination.page_size
    query = (
        query.order_by(EntityRelationship.effective_date.desc().nullslast())
        .offset(offset)
        .limit(pagination.page_size)
    )
    result = await session.execute(query)
    relationships = result.scalars().all()

    return PaginatedResponse(
        data=[EntityRelationshipResponse.model_validate(r) for r in relationships],
        meta=build_paginated_meta(total_count, pagination),
    )


# ── POST /v1/entities/resolve ──────────────────────────────────────

@router.post("/resolve", response_model=EntityResolveResponse)
async def resolve_entity(
    body: EntityResolveRequest,
    session: AsyncSession = Depends(get_session),
):
    """Submit a record for entity resolution.

    Delegates to the resolution engine which returns a match verdict.
    """
    from src.resolution.resolver import resolve

    result = await resolve(
        legal_name=body.legal_name,
        country=body.country,
        identifiers=body.identifiers,
        session=session,
    )
    return EntityResolveResponse(
        matched_entity_id=result.entity_id,
        confidence=result.confidence,
        match_method=result.match_method,
        status=result.status,
    )


# ── POST /v1/entities/bulk-lookup ──────────────────────────────────

@router.post("/bulk-lookup", response_model=BulkLookupResponse)
async def bulk_lookup_entities(
    body: BulkLookupRequest,
    session: AsyncSession = Depends(get_session),
):
    """Batch identifier lookup.

    Accepts a list of (type, value) pairs and returns the corresponding
    entities (or null for unmatched identifiers).
    """
    results: list[EntityResponse | None] = []

    for lookup in body.identifiers:
        # Find entity via identifier table
        ident_result = await session.execute(
            select(EntityIdentifier).where(
                EntityIdentifier.identifier_type == lookup.type,
                EntityIdentifier.identifier_value == lookup.value,
            )
        )
        ident = ident_result.scalar_one_or_none()

        if ident is None:
            results.append(None)
            continue

        entity_result = await session.execute(
            select(Entity).where(Entity.entity_id == ident.entity_id)
        )
        entity = entity_result.scalar_one_or_none()
        if entity:
            results.append(EntityResponse.model_validate(entity))
        else:
            results.append(None)

    return BulkLookupResponse(results=results)
