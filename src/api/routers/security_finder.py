"""Security Finder API endpoints (Pillar 2 Supplement – Part 5)."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func as sa_func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_session
from src.models.security import Security, SecurityIdentifier
from src.schemas.security_finder import (
    SecurityFinderResponse,
    SecurityFinderResult,
    SecuritySuggestion,
)

router = APIRouter(tags=["Security Finder"])


def _relevance(name: str | None, short_name: str | None, query: str) -> float:
    """Cheap heuristic relevance score so we don't hand back identical 1.0
    on every result. Exact ticker / name match scores highest, prefix
    matches next, substring last.
    """
    if not query:
        return 0.0
    q = query.lower().strip()
    n = (name or "").lower()
    s = (short_name or "").lower()
    if q == n or q == s:
        return 1.0
    if n.startswith(q) or s.startswith(q):
        return 0.85
    if q in n or q in s:
        return 0.6
    return 0.4


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
    """Search for securities by name, ticker, or identifier (CUSIP/ISIN/FIGI)."""
    pattern = f"%{q}%"
    # Match anything in the SecurityIdentifier table by exact value (so a
    # CUSIP/ISIN/ticker hit pulls in its parent security).
    ident_subq = select(SecurityIdentifier.security_id).where(
        SecurityIdentifier.identifier_value.ilike(pattern)
    )
    query = select(Security).where(
        or_(
            Security.name.ilike(pattern),
            Security.short_name.ilike(pattern),
            Security.security_id.in_(ident_subq),
        )
    )

    if security_type:
        query = query.where(Security.security_type == security_type.upper())
    if asset_class:
        query = query.where(Security.asset_class == asset_class.upper())

    query = query.order_by(Security.name).limit(limit)
    result = await session.execute(query)
    securities = result.scalars().all()

    results = [
        SecurityFinderResult(
            security_id=s.security_id,
            name=s.name,
            short_name=s.short_name,
            security_type=s.security_type,
            asset_class=getattr(s, "asset_class", None),
            status=s.status,
            relevance_score=_relevance(s.name, s.short_name, q),
        )
        for s in securities
    ]
    results.sort(key=lambda r: -r.relevance_score)

    return SecurityFinderResponse(
        query=q,
        total_results=len(results),
        results=results,
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
    """Return autocomplete suggestions for security search (name, ticker, ID)."""
    pattern = f"{q}%"
    ident_subq = select(SecurityIdentifier.security_id).where(
        SecurityIdentifier.identifier_value.ilike(pattern)
    )
    query = (
        select(Security)
        .where(
            or_(
                Security.name.ilike(pattern),
                Security.short_name.ilike(pattern),
                Security.security_id.in_(ident_subq),
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
