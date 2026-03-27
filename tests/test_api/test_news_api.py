"""API tests for News endpoints (Pillar 3 Phase 1)."""

from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


# ── Tests ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_entity_news(client: AsyncClient, session: AsyncSession):
    """GET /v3/news/{entity_id} returns 200 or 404 for unknown entity."""
    resp = await client.get(f"/v3/news/{uuid4()}")
    assert resp.status_code in (200, 404)


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
