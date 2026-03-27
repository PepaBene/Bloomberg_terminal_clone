"""API tests for Earnings Intelligence P2 endpoints (Pillar 3 Phase 2)."""

import uuid
from datetime import date
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.entity import Entity
from src.models.earnings_transcript import EarningsCallTranscript
from src.models.earnings_intelligence import EarningsSurprise, GuidanceTracking


# ── Helpers ──────────────────────────────────────────────────────────


async def _seed_entity(session: AsyncSession, entity_id: uuid.UUID) -> Entity:
    entity = Entity(
        entity_id=entity_id,
        entity_type="CORPORATION",
        legal_name="Earnings P2 Test Corp",
        short_name="EARNP2",
        status="ACTIVE",
        source="TEST",
        confidence_score=0.99,
    )
    session.add(entity)
    await session.commit()
    return entity


# ── Static route tests ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_surprises_today(client: AsyncClient, session: AsyncSession):
    """GET /v3/earnings/surprises/today returns 200."""
    resp = await client.get("/v3/earnings/surprises/today")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_get_earnings_calendar(client: AsyncClient, session: AsyncSession):
    """GET /v3/earnings/calendar returns 200."""
    resp = await client.get("/v3/earnings/calendar")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_get_upcoming_earnings(client: AsyncClient, session: AsyncSession):
    """GET /v3/earnings/calendar/upcoming returns 200."""
    resp = await client.get("/v3/earnings/calendar/upcoming")
    assert resp.status_code == 200


# ── Transcript tests ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_transcripts_empty(client: AsyncClient, session: AsyncSession):
    """GET /v3/earnings/{entity_id}/calls returns 200 or 404."""
    resp = await client.get(f"/v3/earnings/{uuid4()}/calls")
    assert resp.status_code in (200, 404)


@pytest.mark.asyncio
async def test_get_latest_transcript(client: AsyncClient, session: AsyncSession):
    """GET /v3/earnings/{entity_id}/calls/latest returns 200 or 404."""
    resp = await client.get(f"/v3/earnings/{uuid4()}/calls/latest")
    assert resp.status_code in (200, 404)


@pytest.mark.asyncio
async def test_get_latest_transcript_summary(client: AsyncClient, session: AsyncSession):
    """GET /v3/earnings/{entity_id}/calls/latest/summary returns 200 or 404."""
    resp = await client.get(f"/v3/earnings/{uuid4()}/calls/latest/summary")
    assert resp.status_code in (200, 404)


@pytest.mark.asyncio
async def test_get_latest_transcript_sentiment(client: AsyncClient, session: AsyncSession):
    """GET /v3/earnings/{entity_id}/calls/latest/sentiment returns 200 or 404."""
    resp = await client.get(f"/v3/earnings/{uuid4()}/calls/latest/sentiment")
    assert resp.status_code in (200, 404)


@pytest.mark.asyncio
async def test_get_latest_transcript_topics(client: AsyncClient, session: AsyncSession):
    """GET /v3/earnings/{entity_id}/calls/latest/topics returns 200 or 404."""
    resp = await client.get(f"/v3/earnings/{uuid4()}/calls/latest/topics")
    assert resp.status_code in (200, 404)


@pytest.mark.asyncio
async def test_get_sentiment_history(client: AsyncClient, session: AsyncSession):
    """GET /v3/earnings/{entity_id}/calls/sentiment/history returns 200 or 404."""
    resp = await client.get(f"/v3/earnings/{uuid4()}/calls/sentiment/history")
    assert resp.status_code in (200, 404)


# ── Surprise tests ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_surprise_history(client: AsyncClient, session: AsyncSession):
    """GET /v3/earnings/{entity_id}/surprises returns 200 or 404."""
    resp = await client.get(f"/v3/earnings/{uuid4()}/surprises")
    assert resp.status_code in (200, 404)


@pytest.mark.asyncio
async def test_get_latest_surprise(client: AsyncClient, session: AsyncSession):
    """GET /v3/earnings/{entity_id}/surprises/latest returns 200 or 404."""
    resp = await client.get(f"/v3/earnings/{uuid4()}/surprises/latest")
    assert resp.status_code in (200, 404)


# ── Guidance tests ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_guidance(client: AsyncClient, session: AsyncSession):
    """GET /v3/earnings/{entity_id}/guidance returns 200 or 404."""
    resp = await client.get(f"/v3/earnings/{uuid4()}/guidance")
    assert resp.status_code in (200, 404)


@pytest.mark.asyncio
async def test_get_guidance_history(client: AsyncClient, session: AsyncSession):
    """GET /v3/earnings/{entity_id}/guidance/history returns 200 or 404."""
    resp = await client.get(f"/v3/earnings/{uuid4()}/guidance/history")
    assert resp.status_code in (200, 404)


@pytest.mark.asyncio
async def test_get_guidance_credibility(client: AsyncClient, session: AsyncSession):
    """GET /v3/earnings/{entity_id}/guidance/credibility returns 200 or 404."""
    resp = await client.get(f"/v3/earnings/{uuid4()}/guidance/credibility")
    assert resp.status_code in (200, 404)
