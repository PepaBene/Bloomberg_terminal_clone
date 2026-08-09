"""Layer 2 — News AI analysis API endpoint (AI_THREE_LAYER_REBUILD_PLAN.md §4.4).

Compute-on-miss, same shape as ``src/api/routers/interpret.py``: a GET
either serves the article's persisted ``ai_analysis`` or computes+persists
it inline. ``?refresh=true`` forces recomputation.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.ai.client import get_ai_client
from src.ai.news.store import get_or_compute_article_analysis
from src.api.deps import get_session
from src.models.news_article import NewsArticle
from src.schemas.news_article import ArticleAnalysisResponse

router = APIRouter(tags=["AI - News Analysis"])


@router.get("/news/articles/{article_id}/analysis", response_model=ArticleAnalysisResponse)
async def get_article_analysis(
    article_id: uuid.UUID,
    refresh: bool = Query(False, description="Force recompute, bypassing the cache"),
    session: AsyncSession = Depends(get_session),
):
    """Trust-weighted AI analysis for one news article: summary,
    interpretation, non-consensus angle (when genuinely warranted), and
    entity/sector/market connections grounded in this article's already-
    computed propagation targets.
    """
    article = (
        await session.execute(select(NewsArticle).where(NewsArticle.id == article_id))
    ).scalar_one_or_none()
    if article is None:
        raise HTTPException(status_code=404, detail=f"News article '{article_id}' not found")

    client = get_ai_client()
    output = await get_or_compute_article_analysis(session, client, article, force_refresh=refresh)
    await session.commit()

    if output is None:
        raise HTTPException(
            status_code=503,
            detail="Analysis unavailable (AI disabled and no cached result)",
        )
    return ArticleAnalysisResponse(
        article_id=article_id,
        summary=output.summary,
        interpretation=output.interpretation,
        non_consensus_angle=output.non_consensus_angle,
        connections=output.connections,
        confidence=output.confidence,
    )
