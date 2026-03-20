"""D6 Ownership API endpoints (Spec 8.7)."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func as sa_func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_pagination, get_session
from src.api.utils.pagination import build_paginated_meta
from src.models.ownership import (
    InsiderHolding,
    InstitutionalHolding,
    InstitutionProfile,
    OwnershipSummary,
    ShortInterest,
)
from src.models.security import Security
from src.schemas.common import PaginatedResponse, PaginationParams
from src.schemas.ownership import (
    InsiderHoldingResponse,
    InstitutionalHoldingResponse,
    InstitutionProfileResponse,
    OwnershipSummaryResponse,
    ShortInterestResponse,
)

router = APIRouter(tags=["Ownership"])


# ── GET /v1/institutions ──────────────────────────────────────────

@router.get("/institutions", response_model=PaginatedResponse)
async def list_institutions(
    session: AsyncSession = Depends(get_session),
    pagination: PaginationParams = Depends(get_pagination),
    institution_type: str | None = Query(None, description="Filter by institution type"),
    tier: str | None = Query(None, description="Filter by tier (WHALE, MAJOR, NOTABLE, SMALL)"),
):
    """List institutional investor profiles."""
    query = select(InstitutionProfile)
    count_query = select(InstitutionProfile)

    if institution_type:
        query = query.where(InstitutionProfile.institution_type == institution_type.upper())
        count_query = count_query.where(InstitutionProfile.institution_type == institution_type.upper())
    if tier:
        query = query.where(InstitutionProfile.tier == tier.upper())
        count_query = count_query.where(InstitutionProfile.tier == tier.upper())

    total_result = await session.execute(
        select(sa_func.count()).select_from(count_query.subquery())
    )
    total_count = total_result.scalar_one()

    offset = (pagination.page - 1) * pagination.page_size
    query = query.order_by(InstitutionProfile.institution_name).offset(offset).limit(pagination.page_size)
    result = await session.execute(query)
    institutions = result.scalars().all()

    return PaginatedResponse(
        data=[InstitutionProfileResponse.model_validate(i) for i in institutions],
        meta=build_paginated_meta(total_count, pagination),
    )


# ── GET /v1/institutions/{institution_id} ─────────────────────────

@router.get("/institutions/{institution_id}", response_model=InstitutionProfileResponse)
async def get_institution(
    institution_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get a single institution profile by ID."""
    result = await session.execute(
        select(InstitutionProfile).where(
            InstitutionProfile.institution_id == institution_id
        )
    )
    institution = result.scalar_one_or_none()
    if not institution:
        raise HTTPException(status_code=404, detail=f"Institution '{institution_id}' not found")
    return InstitutionProfileResponse.model_validate(institution)


# ── GET /v1/securities/{id}/ownership/institutional ───────────────

@router.get("/securities/{security_id}/ownership/institutional", response_model=PaginatedResponse)
async def get_institutional_holdings(
    security_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    pagination: PaginationParams = Depends(get_pagination),
):
    """Get institutional holders for a security."""
    # Verify security exists
    sec_result = await session.execute(
        select(Security.security_id).where(Security.security_id == security_id)
    )
    if not sec_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail=f"Security '{security_id}' not found")

    query = select(InstitutionalHolding).where(
        InstitutionalHolding.security_id == security_id
    )
    count_query = select(InstitutionalHolding).where(
        InstitutionalHolding.security_id == security_id
    )

    total_result = await session.execute(
        select(sa_func.count()).select_from(count_query.subquery())
    )
    total_count = total_result.scalar_one()

    offset = (pagination.page - 1) * pagination.page_size
    query = (
        query.order_by(InstitutionalHolding.report_date.desc())
        .offset(offset)
        .limit(pagination.page_size)
    )
    result = await session.execute(query)
    holdings = result.scalars().all()

    return PaginatedResponse(
        data=[InstitutionalHoldingResponse.model_validate(h) for h in holdings],
        meta=build_paginated_meta(total_count, pagination),
    )


# ── GET /v1/securities/{id}/ownership/insider ─────────────────────

@router.get("/securities/{security_id}/ownership/insider", response_model=PaginatedResponse)
async def get_insider_holdings(
    security_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    pagination: PaginationParams = Depends(get_pagination),
    transaction_type: str | None = Query(None, description="Filter by transaction type"),
):
    """Get insider transactions for a security."""
    # Verify security exists
    sec_result = await session.execute(
        select(Security.security_id).where(Security.security_id == security_id)
    )
    if not sec_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail=f"Security '{security_id}' not found")

    query = select(InsiderHolding).where(InsiderHolding.security_id == security_id)
    count_query = select(InsiderHolding).where(InsiderHolding.security_id == security_id)

    if transaction_type:
        query = query.where(InsiderHolding.transaction_type == transaction_type.upper())
        count_query = count_query.where(InsiderHolding.transaction_type == transaction_type.upper())

    total_result = await session.execute(
        select(sa_func.count()).select_from(count_query.subquery())
    )
    total_count = total_result.scalar_one()

    offset = (pagination.page - 1) * pagination.page_size
    query = (
        query.order_by(InsiderHolding.transaction_date.desc())
        .offset(offset)
        .limit(pagination.page_size)
    )
    result = await session.execute(query)
    holdings = result.scalars().all()

    return PaginatedResponse(
        data=[InsiderHoldingResponse.model_validate(h) for h in holdings],
        meta=build_paginated_meta(total_count, pagination),
    )


# ── GET /v1/securities/{id}/ownership/summary ─────────────────────

@router.get("/securities/{security_id}/ownership/summary", response_model=OwnershipSummaryResponse)
async def get_ownership_summary(
    security_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get the latest ownership summary for a security."""
    # Verify security exists
    sec_result = await session.execute(
        select(Security.security_id).where(Security.security_id == security_id)
    )
    if not sec_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail=f"Security '{security_id}' not found")

    result = await session.execute(
        select(OwnershipSummary)
        .where(OwnershipSummary.security_id == security_id)
        .order_by(OwnershipSummary.report_date.desc())
        .limit(1)
    )
    summary = result.scalar_one_or_none()
    if not summary:
        raise HTTPException(
            status_code=404,
            detail=f"No ownership summary found for security '{security_id}'",
        )
    return OwnershipSummaryResponse.model_validate(summary)


# ── GET /v1/securities/{id}/short-interest ────────────────────────

@router.get("/securities/{security_id}/short-interest", response_model=PaginatedResponse)
async def get_short_interest(
    security_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    pagination: PaginationParams = Depends(get_pagination),
):
    """Get short interest data for a security."""
    # Verify security exists
    sec_result = await session.execute(
        select(Security.security_id).where(Security.security_id == security_id)
    )
    if not sec_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail=f"Security '{security_id}' not found")

    query = select(ShortInterest).where(ShortInterest.security_id == security_id)
    count_query = select(ShortInterest).where(ShortInterest.security_id == security_id)

    total_result = await session.execute(
        select(sa_func.count()).select_from(count_query.subquery())
    )
    total_count = total_result.scalar_one()

    offset = (pagination.page - 1) * pagination.page_size
    query = (
        query.order_by(ShortInterest.settlement_date.desc())
        .offset(offset)
        .limit(pagination.page_size)
    )
    result = await session.execute(query)
    records = result.scalars().all()

    return PaginatedResponse(
        data=[ShortInterestResponse.model_validate(r) for r in records],
        meta=build_paginated_meta(total_count, pagination),
    )
