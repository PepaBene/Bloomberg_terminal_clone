"""API tests for News endpoints (Pillar 3 Phase 1)."""

import uuid
from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.entity import Entity
from src.models.news_article import ArticleEntityLink, NewsArticle


# ── Tests ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_entity_news(client: AsyncClient, session: AsyncSession):
    """GET /v3/news/{entity_id} returns 200 or 404 for unknown entity."""
    resp = await client.get(f"/v3/news/{uuid4()}")
    assert resp.status_code in (200, 404)


async def _seed_entity_with_ranked_articles(session: AsyncSession) -> uuid.UUID:
    """One entity with two articles: an older HIGH-credibility WIRE story
    and a newer, uncredited (never-enriched) story -- lets rank_by=date
    vs rank_by=credibility disagree on ordering, which is the whole point
    of the no-AI trust-ranked mode (§4.5)."""
    entity_id = uuid.uuid4()
    session.add(Entity(
        entity_id=entity_id, entity_type="PUBLIC_COMPANY",
        legal_name="Ranked News Test Corp", status="ACTIVE", source="TEST",
    ))
    await session.flush()

    old_credible = NewsArticle(
        id=uuid.uuid4(), source_url="https://reuters.com/ranked-news-test-old",
        title="Older but highly credible story", summary="s",
        source_name="Reuters", publish_date=date.today() - timedelta(days=5),
        ingest_date=date.today() - timedelta(days=5),
        credibility_score=Decimal("1.0000"), source_trust=Decimal("1.00"),
    )
    new_uncredited = NewsArticle(
        id=uuid.uuid4(), source_url="https://reuters.com/ranked-news-test-new",
        title="Newer story never scored for credibility", summary="s",
        source_name="Reuters", publish_date=date.today(),
        ingest_date=date.today(),
    )
    session.add_all([old_credible, new_uncredited])
    await session.flush()
    session.add_all([
        ArticleEntityLink(id=uuid.uuid4(), article_id=old_credible.id, entity_id=entity_id, is_primary=True, mention_count=1),
        ArticleEntityLink(id=uuid.uuid4(), article_id=new_uncredited.id, entity_id=entity_id, is_primary=True, mention_count=1),
    ])
    await session.flush()
    return entity_id


@pytest.mark.asyncio
async def test_get_entity_news_default_rank_by_date(client: AsyncClient, session: AsyncSession):
    entity_id = await _seed_entity_with_ranked_articles(session)
    resp = await client.get(f"/v3/news/{entity_id}")
    assert resp.status_code == 200
    titles = [a["title"] for a in resp.json()]
    assert titles[0] == "Newer story never scored for credibility"


@pytest.mark.asyncio
async def test_get_entity_news_rank_by_credibility(client: AsyncClient, session: AsyncSession):
    entity_id = await _seed_entity_with_ranked_articles(session)
    resp = await client.get(f"/v3/news/{entity_id}", params={"rank_by": "credibility"})
    assert resp.status_code == 200
    articles = resp.json()
    assert articles[0]["title"] == "Older but highly credible story"
    assert articles[0]["credibility_score"] == 1.0
    # Unscored article sorts last, not first (NULLs LAST), still present.
    assert articles[1]["title"] == "Newer story never scored for credibility"
    assert articles[1]["credibility_score"] is None


@pytest.mark.asyncio
async def test_get_news_latest(client: AsyncClient, session: AsyncSession):
    """GET /v3/news/latest returns 200."""
    resp = await client.get("/v3/news/latest")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_get_news_market_moving(client: AsyncClient, session: AsyncSession):
    """GET /v3/news/market-moving returns 200."""
    resp = await client.get("/v3/news/market-moving")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_get_news_most_mentioned(client: AsyncClient, session: AsyncSession):
    """GET /v3/news/most-mentioned returns 200."""
    resp = await client.get("/v3/news/most-mentioned")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_get_news_sector(client: AsyncClient, session: AsyncSession):
    """GET /v3/news/sector/TECHNOLOGY returns 200 or 404 (no entities in sector)."""
    resp = await client.get("/v3/news/sector/TECHNOLOGY")
    assert resp.status_code in (200, 404)


@pytest.mark.asyncio
async def test_post_news_search(client: AsyncClient, session: AsyncSession):
    """POST /v3/news/search with query returns 200."""
    resp = await client.post("/v3/news/search", json={"query": "earnings"})
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_get_news_stats(client: AsyncClient, session: AsyncSession):
    """GET /v3/news/stats returns 200."""
    resp = await client.get("/v3/news/stats")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_get_news_timeline(client: AsyncClient, session: AsyncSession):
    """GET /v3/news/{entity_id}/timeline returns 200 or 404 for unknown entity."""
    resp = await client.get(f"/v3/news/{uuid4()}/timeline")
    assert resp.status_code in (200, 404)
