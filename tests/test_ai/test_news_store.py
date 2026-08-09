"""Unit tests for src/ai/news/store.py (compute-on-miss article analysis)."""
from __future__ import annotations

import uuid
from datetime import date

import pytest

from src.ai.news.analyzer import ArticleAnalysisOutput
from src.ai.news.store import get_or_compute_article_analysis
from src.models.news_article import NewsArticle


class FakeStructuredClient:
    def __init__(self, *, enabled: bool = True, response: ArticleAnalysisOutput | None = None, raises: bool = False):
        self.enabled = enabled
        self._response = response
        self._raises = raises
        self.calls = 0

    async def complete_structured(self, *, response_model, user, system, tier, max_tokens, feature):
        self.calls += 1
        if self._raises:
            raise RuntimeError("simulated failure")
        return self._response


def _article(**kwargs) -> NewsArticle:
    defaults = dict(
        id=uuid.uuid4(), source_url=f"https://reuters.com/{uuid.uuid4().hex}",
        title="Some headline", summary="Some summary.", source_name="Reuters",
        publish_date=date(2026, 1, 10), ingest_date=date(2026, 1, 10),
    )
    defaults.update(kwargs)
    return NewsArticle(**defaults)


OUTPUT = ArticleAnalysisOutput(
    summary="A summary.", interpretation="It matters.",
    non_consensus_angle=None, connections=["Tech sector"], confidence=0.75,
)


@pytest.mark.asyncio
async def test_cache_hit_skips_llm_call(session):
    art = _article(ai_analysis={
        "summary": "Cached summary.", "interpretation": "Cached interpretation.",
        "non_consensus_angle": None, "connections": [], "confidence": 0.6,
        "model": "x", "prompt_id": "news_article_summary", "prompt_version": 1,
    })
    session.add(art)
    await session.flush()
    client = FakeStructuredClient(response=OUTPUT)

    result = await get_or_compute_article_analysis(session, client, art)

    assert result.summary == "Cached summary."
    assert client.calls == 0


@pytest.mark.asyncio
async def test_cache_miss_computes_and_persists(session):
    art = _article()
    session.add(art)
    await session.flush()
    client = FakeStructuredClient(response=OUTPUT)

    result = await get_or_compute_article_analysis(session, client, art)

    assert result == OUTPUT
    assert client.calls == 1
    assert art.ai_analysis is not None
    assert art.ai_analysis["summary"] == "A summary."
    assert art.ai_analysis["prompt_id"] == "news_article_summary"


@pytest.mark.asyncio
async def test_cache_miss_disabled_client_returns_none(session):
    art = _article()
    session.add(art)
    await session.flush()
    client = FakeStructuredClient(enabled=False)

    result = await get_or_compute_article_analysis(session, client, art)

    assert result is None
    assert art.ai_analysis is None


@pytest.mark.asyncio
async def test_cache_miss_client_failure_returns_none_and_does_not_persist(session):
    art = _article()
    session.add(art)
    await session.flush()
    client = FakeStructuredClient(raises=True)

    result = await get_or_compute_article_analysis(session, client, art)

    assert result is None
    assert art.ai_analysis is None


@pytest.mark.asyncio
async def test_force_refresh_bypasses_cache(session):
    art = _article(ai_analysis={
        "summary": "Stale summary.", "interpretation": "Stale.",
        "non_consensus_angle": None, "connections": [], "confidence": 0.5,
        "model": "x", "prompt_id": "news_article_summary", "prompt_version": 1,
    })
    session.add(art)
    await session.flush()
    client = FakeStructuredClient(response=OUTPUT)

    result = await get_or_compute_article_analysis(session, client, art, force_refresh=True)

    assert result == OUTPUT
    assert client.calls == 1
    assert art.ai_analysis["summary"] == "A summary."


@pytest.mark.asyncio
async def test_disabled_client_with_force_refresh_still_returns_none(session):
    art = _article(ai_analysis={
        "summary": "Stale.", "interpretation": "Stale.", "non_consensus_angle": None,
        "connections": [], "confidence": 0.5, "model": "x",
        "prompt_id": "news_article_summary", "prompt_version": 1,
    })
    session.add(art)
    await session.flush()
    client = FakeStructuredClient(enabled=False)

    result = await get_or_compute_article_analysis(session, client, art, force_refresh=True)
    assert result is None
