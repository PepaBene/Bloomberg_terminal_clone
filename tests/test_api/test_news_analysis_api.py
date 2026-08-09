"""API tests for the Layer 2 news-analysis endpoint
(src/api/routers/news_analysis.py).

No live ANTHROPIC_API_KEY in the test env, so these exercise the
not-yet-cached (AI disabled -> 503) and already-cached (seeded
ai_analysis -> served without needing AI) paths -- the AI computation
path itself is covered by tests/test_ai/test_news_store.py's
FakeStructuredClient tests.
"""
from __future__ import annotations

import uuid
from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.news_article import NewsArticle


async def _seed_article(session: AsyncSession, **kwargs) -> uuid.UUID:
    article_id = uuid.uuid4()
    defaults = dict(
        id=article_id, source_url=f"https://reuters.com/{uuid.uuid4().hex}",
        title="Some headline", summary="Some summary.", source_name="Reuters",
        publish_date=date(2026, 1, 10), ingest_date=date(2026, 1, 10),
    )
    defaults.update(kwargs)
    session.add(NewsArticle(**defaults))
    await session.commit()
    return article_id


@pytest.mark.asyncio
async def test_article_analysis_404_for_unknown_article(client: AsyncClient):
    resp = await client.get(f"/v5/news/articles/{uuid.uuid4()}/analysis")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_article_analysis_503_when_not_cached_and_ai_disabled(client: AsyncClient, session: AsyncSession):
    article_id = await _seed_article(session)
    resp = await client.get(f"/v5/news/articles/{article_id}/analysis")
    assert resp.status_code == 503


@pytest.mark.asyncio
async def test_article_analysis_serves_fresh_cached_result_without_ai(client: AsyncClient, session: AsyncSession):
    article_id = await _seed_article(session, ai_analysis={
        "summary": "Cached summary.", "interpretation": "Cached interpretation.",
        "non_consensus_angle": "A contrarian read.", "connections": ["Energy sector"],
        "confidence": 0.7, "model": "x", "prompt_id": "news_article_summary", "prompt_version": 1,
    })

    resp = await client.get(f"/v5/news/articles/{article_id}/analysis")
    assert resp.status_code == 200
    body = resp.json()
    assert body["summary"] == "Cached summary."
    assert body["non_consensus_angle"] == "A contrarian read."
    assert body["connections"] == ["Energy sector"]
    assert body["confidence"] == 0.7


@pytest.mark.asyncio
async def test_article_analysis_refresh_with_ai_disabled_still_503(client: AsyncClient, session: AsyncSession):
    """?refresh=true bypasses the cache read, but with no live AI client
    there's still nothing to serve -- 503, not a stale/wrong 200."""
    article_id = await _seed_article(session, ai_analysis={
        "summary": "Cached.", "interpretation": "Cached.", "non_consensus_angle": None,
        "connections": [], "confidence": 0.5, "model": "x",
        "prompt_id": "news_article_summary", "prompt_version": 1,
    })

    resp = await client.get(f"/v5/news/articles/{article_id}/analysis", params={"refresh": "true"})
    assert resp.status_code == 503
