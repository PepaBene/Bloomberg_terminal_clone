"""Unit tests for src/ai/news/store.py (compute-on-miss article analysis)."""
from __future__ import annotations

import uuid
from datetime import date

import pytest

from src.ai.news.analyzer import ArticleAnalysisOutput
from src.ai.news.cluster_analyzer import ClusterSynthesisOutput
from src.ai.news.store import get_or_compute_article_analysis, get_or_compute_cluster_analysis
from src.models.news_article import NewsArticle


class FakeStructuredClient:
    def __init__(self, *, enabled: bool = True, response=None, raises: bool = False):
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


# ── get_or_compute_cluster_analysis ──────────────────────────────────


CLUSTER_OUTPUT = ClusterSynthesisOutput(
    consensus_summary="The Fed raised rates by 25bps.",
    divergent_views=[],
    materiality_assessment="High materiality.",
    confidence=0.8,
)


@pytest.mark.asyncio
async def test_cluster_cache_hit_skips_llm_call(session):
    rep = _article(cluster_analysis={
        "consensus_summary": "Cached consensus.", "divergent_views": [],
        "materiality_assessment": "Cached materiality.", "confidence": 0.6,
        "model": "x", "prompt_id": "news_cluster_analysis", "prompt_version": 1,
    })
    rep.cluster_id = rep.id
    session.add(rep)
    await session.flush()
    client = FakeStructuredClient(response=CLUSTER_OUTPUT)

    representative, result = await get_or_compute_cluster_analysis(session, client, rep)

    assert representative.id == rep.id
    assert result.consensus_summary == "Cached consensus."
    assert client.calls == 0


@pytest.mark.asyncio
async def test_cluster_cache_miss_computes_and_persists(session):
    rep = _article()
    rep.cluster_id = rep.id
    session.add(rep)
    await session.flush()
    client = FakeStructuredClient(response=CLUSTER_OUTPUT)

    representative, result = await get_or_compute_cluster_analysis(session, client, rep)

    assert result == CLUSTER_OUTPUT
    assert client.calls == 1
    assert rep.cluster_analysis is not None
    assert rep.cluster_analysis["consensus_summary"] == "The Fed raised rates by 25bps."
    assert rep.cluster_analysis["prompt_id"] == "news_cluster_analysis"


@pytest.mark.asyncio
async def test_cluster_analysis_resolves_non_representative_to_representative(session):
    rep = _article(title="Original")
    rep.cluster_id = rep.id
    session.add(rep)
    await session.flush()

    follower = _article(title="Corroborator", cluster_id=rep.id)
    session.add(follower)
    await session.flush()

    client = FakeStructuredClient(response=CLUSTER_OUTPUT)
    representative, result = await get_or_compute_cluster_analysis(session, client, follower)

    assert representative.id == rep.id
    assert result == CLUSTER_OUTPUT
    assert rep.cluster_analysis is not None
    assert follower.cluster_analysis is None


@pytest.mark.asyncio
async def test_cluster_cache_miss_disabled_client_returns_none(session):
    rep = _article()
    rep.cluster_id = rep.id
    session.add(rep)
    await session.flush()
    client = FakeStructuredClient(enabled=False)

    representative, result = await get_or_compute_cluster_analysis(session, client, rep)
    assert result is None
    assert representative.cluster_analysis is None


@pytest.mark.asyncio
async def test_cluster_cache_miss_client_failure_returns_none_and_does_not_persist(session):
    rep = _article()
    rep.cluster_id = rep.id
    session.add(rep)
    await session.flush()
    client = FakeStructuredClient(raises=True)

    representative, result = await get_or_compute_cluster_analysis(session, client, rep)
    assert result is None
    assert representative.cluster_analysis is None


@pytest.mark.asyncio
async def test_cluster_force_refresh_bypasses_cache(session):
    rep = _article(cluster_analysis={
        "consensus_summary": "Stale.", "divergent_views": [],
        "materiality_assessment": "Stale.", "confidence": 0.5,
        "model": "x", "prompt_id": "news_cluster_analysis", "prompt_version": 1,
    })
    rep.cluster_id = rep.id
    session.add(rep)
    await session.flush()
    client = FakeStructuredClient(response=CLUSTER_OUTPUT)

    representative, result = await get_or_compute_cluster_analysis(session, client, rep, force_refresh=True)

    assert result == CLUSTER_OUTPUT
    assert client.calls == 1
    assert representative.cluster_analysis["consensus_summary"] == "The Fed raised rates by 25bps."
