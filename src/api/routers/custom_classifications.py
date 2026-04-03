"""Custom Classifications API endpoints (Pillar 1 Supplement §14)."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func as sa_func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_pagination, get_session
from src.api.utils.pagination import build_paginated_meta
from src.models.custom_classifications import ClassificationMember, CustomClassification
from src.schemas.common import PaginatedResponse, PaginationParams
from src.schemas.custom_classifications import (
    ClassificationCreateRequest,
    ClassificationMemberRequest,
    ClassificationResponse,
)

router = APIRouter(tags=["Custom Classifications"])


@router.post("/classifications", response_model=ClassificationResponse, status_code=201)
async def create_classification(
    body: ClassificationCreateRequest,
    session: AsyncSession = Depends(get_session),
    user_id: uuid.UUID | None = Query(None, description="Owner user_id (dev shortcut)"),
):
    """Create a new custom classification."""
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id is required")
    obj = CustomClassification(
        classification_id=uuid.uuid4(),
        user_id=user_id,
        name=body.name,
        description=body.description,
        visibility=body.visibility,
    )
    session.add(obj)
    await session.commit()
    await session.refresh(obj)
    return ClassificationResponse.model_validate(obj)


@router.get("/classifications", response_model=PaginatedResponse)
async def list_classifications(
    session: AsyncSession = Depends(get_session),
    pagination: PaginationParams = Depends(get_pagination),
    user_id: uuid.UUID | None = Query(None, description="Filter by owner"),
    visibility: str | None = Query(None),
):
    """List custom classifications."""
    base = select(CustomClassification)
    count_q = base
    if user_id:
        base = base.where(CustomClassification.user_id == user_id)
        count_q = count_q.where(CustomClassification.user_id == user_id)
    if visibility:
        base = base.where(CustomClassification.visibility == visibility.upper())
        count_q = count_q.where(CustomClassification.visibility == visibility.upper())

    total = (await session.execute(
        select(sa_func.count()).select_from(count_q.subquery())
    )).scalar_one()

    offset = (pagination.page - 1) * pagination.page_size
    rows = (await session.execute(
        base.order_by(CustomClassification.name).offset(offset).limit(pagination.page_size)
    )).scalars().all()

    return PaginatedResponse(
        data=[ClassificationResponse.model_validate(r) for r in rows],
        meta=build_paginated_meta(total, pagination),
    )


@router.get("/classifications/{classification_id}", response_model=ClassificationResponse)
async def get_classification(
    classification_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Fetch a single classification with its members."""
    result = await session.execute(
        select(CustomClassification).where(
            CustomClassification.classification_id == classification_id
        )
    )
    obj = result.scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail="Classification not found")
    return ClassificationResponse.model_validate(obj)


@router.put(
    "/classifications/{classification_id}/members",
    response_model=ClassificationResponse,
)
async def add_member(
    classification_id: uuid.UUID,
    body: ClassificationMemberRequest,
    session: AsyncSession = Depends(get_session),
):
    """Add an entity to a classification."""
    result = await session.execute(
        select(CustomClassification).where(
            CustomClassification.classification_id == classification_id
        )
    )
    obj = result.scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail="Classification not found")

    member = ClassificationMember(
        id=uuid.uuid4(),
        classification_id=classification_id,
        entity_id=body.entity_id,
        tags=body.tags,
    )
    session.add(member)
    await session.commit()
    await session.refresh(obj)
    return ClassificationResponse.model_validate(obj)
