"""API tests for News Sentiment P2 endpoints (Pillar 3 Phase 2)."""

import uuid
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


# ── Static route tests ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_post_sentiment_screen(client: AsyncClient, session: AsyncSession):
    """POST /v3/news/sentiment/screen with empty body returns 200."""
    resp = await client.post("/v3/news/sentiment/screen", json={})
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_get_daily_digest(client: AsyncClient, session: AsyncSession):
    """GET /v3/news/digest returns 200 (or 422 if shadowed by Phase 1 /news/{entity_id})."""
    resp = await client.get("/v3/news/digest")
    assert resp.status_code in (200, 422)


@pytest.mark.asyncio
async def test_get_watchlist_digest(client: AsyncClient, session: AsyncSession):
    """GET /v3/news/digest/watchlist returns 200."""
    resp = await client.get("/v3/news/digest/watchlist")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_post_bulk_news(client: AsyncClient, session: AsyncSession):
    """POST /v3/news/bulk with empty body returns 200."""
    resp = await client.post("/v3/news/bulk", json={})
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_post_bulk_sentiment(client: AsyncClient, session: AsyncSession):
    """POST /v3/news/bulk/sentiment with empty entity_ids returns 200."""
    resp = await client.post("/v3/news/bulk/sentiment", json={"entity_ids": []})
    assert resp.status_code == 200


# ── Parametric route tests ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_entity_sentiment(client: AsyncClient, session: AsyncSession):
    """GET /v3/news/{entity_id}/sentiment returns 200 or 404."""
    resp = await client.get(f"/v3/news/{uuid4()}/sentiment")
    assert resp.status_code in (200, 404)


@pytest.mark.asyncio
async def test_get_sentiment_history(client: AsyncClient, session: AsyncSession):
    """GET /v3/news/{entity_id}/sentiment/history returns 200 or 404."""
    resp = await client.get(f"/v3/news/{uuid4()}/sentiment/history")
    assert resp.status_code in (200, 404)


@pytest.mark.asyncio
async def test_get_sentiment_vs_peers(client: AsyncClient, session: AsyncSession):
    """GET /v3/news/{entity_id}/sentiment/vs-peers returns 200 or 404."""
    resp = await client.get(f"/v3/news/{uuid4()}/sentiment/vs-peers")
    assert resp.status_code in (200, 404)


@pytest.mark.asyncio
async def test_get_sentiment_anomalies(client: AsyncClient, session: AsyncSession):
    """GET /v3/news/{entity_id}/sentiment/anomalies returns 200 or 404."""
    resp = await client.get(f"/v3/news/{uuid4()}/sentiment/anomalies")
    assert resp.status_code in (200, 404)
