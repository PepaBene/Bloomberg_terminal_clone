"""Security Finder API endpoints (Pillar 2 Supplement – Part 5)."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func as sa_func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_session
from src.models.security import Security
from src.schemas.security_finder import (
    SecurityFinderResponse,
    SecurityFinderResult,
    SecuritySuggestion,
)

router = APIRouter(tags=["Security Finder"])


@router.get(
    "/securities/find",
    response_model=SecurityFinderResponse,
)
async def find_securities(
    session: AsyncSession = Depends(get_session),
    q: str = Query(..., min_length=1, description="Search query"),
    security_type: str | None = Query(None),
    asset_class: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
):
    """Search for securities by name, ticker, or identifier."""
    pattern = f"%{q}%"
    query = select(Security).where(
        or_(
            Security.name.ilike(pattern),
            Security.short_name.ilike(pattern),
        )
    )

    if security_type:
        query = query.where(Security.security_type == security_type.upper())
    if asset_class:
        query = query.where(Security.asset_class == asset_class.upper())

    query = query.order_by(Security.name).limit(limit)
    result = await session.execute(query)
    securities = result.scalars().all()

    return SecurityFinderResponse(
        query=q,
        total_results=len(securities),
        results=[
            SecurityFinderResult(
                security_id=s.security_id,
                name=s.name,
                short_name=s.short_name,
                security_type=s.security_type,
                asset_class=getattr(s, "asset_class", None),
                status=s.status,
                relevance_score=1.0,
            )
            for s in securities
        ],
    )


@router.get(
    "/securities/find/suggest",
    response_model=list[SecuritySuggestion],
)
async def suggest(
    session: AsyncSession = Depends(get_session),
    q: str = Query(..., min_length=1, description="Search query prefix"),
    limit: int = Query(10, ge=1, le=50),
):
    """Return autocomplete suggestions for security search."""
    pattern = f"{q}%"
    query = (
        select(Security)
        .where(
            or_(
                Security.name.ilike(pattern),
                Security.short_name.ilike(pattern),
            )
        )
        .order_by(Security.name)
        .limit(limit)
    )
    result = await session.execute(query)
    securities = result.scalars().all()

    return [
        SecuritySuggestion(
            security_id=str(s.security_id),
            name=s.name,
            short_name=s.short_name,
            security_type=s.security_type,
        )
        for s in securities
    ]
