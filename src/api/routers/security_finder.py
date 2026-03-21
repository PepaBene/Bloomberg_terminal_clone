"""Security Finder API endpoints (Pillar 2 Supplement – Part 5)."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_session
from src.engines.security_finder import search_securities, suggest_securities
from src.models.security import Security
from src.schemas.security_finder import (
    SecurityFinderResponse,
    SecurityFinderResult,
    SecuritySuggestion,
)

router = APIRouter(tags=["Security Finder"])


async def _load_securities(session: AsyncSession, limit: int = 500) -> list[dict]:
    """Load securities from DB for in-memory search."""
    result = await session.execute(select(Security).limit(limit))
    rows = result.scalars().all()
    return [
        {
            "security_id": str(r.security_id),
            "name": r.name,
            "short_name": r.short_name,
            "security_type": r.security_type,
            "asset_class": getattr(r, "asset_class", None),
            "status": r.status,
        }
        for r in rows
    ]


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
    securities = await _load_securities(session)
    results = search_securities(
        q, securities, max_results=limit,
        security_type=security_type, asset_class=asset_class,
    )

    return SecurityFinderResponse(
        query=q,
        total_results=len(results),
        results=[
            SecurityFinderResult(
                security_id=r.security_id,
                name=r.name,
                short_name=r.short_name,
                security_type=r.security_type,
                asset_class=r.asset_class,
                status=r.status,
                relevance_score=r.relevance_score,
            )
            for r in results
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
    securities = await _load_securities(session)
    suggestions = suggest_securities(q, securities, max_suggestions=limit)
    return [SecuritySuggestion(**s) for s in suggestions]
