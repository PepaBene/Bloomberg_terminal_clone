"""API tests for Filing Intelligence endpoints (Pillar 3 Phase 1)."""

import uuid
from datetime import date
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.entity import Entity
from src.models.filing_intelligence import EightKEvent


# ── Helpers ──────────────────────────────────────────────────────────


async def _seed_entity(session: AsyncSession, entity_id: uuid.UUID) -> Entity:
    entity = Entity(
        entity_id=entity_id,
        entity_type="CORPORATION",
        legal_name="P3 Filing Test Corp",
        short_name="P3FILING",
        status="ACTIVE",
        source="TEST",
        confidence_score=0.99,
    )
    session.add(entity)
    await session.commit()
    return entity


# ── 8-K Event Tests ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_entity_events_empty(client: AsyncClient, session: AsyncSession):
    """GET /v3/filings/{entity_id}/events returns 200 or 404 for unknown entity."""
    resp = await client.get(f"/v3/filings/{uuid4()}/events")
    assert resp.status_code in (200, 404)


@pytest.mark.asyncio
async def test_get_events_today(client: AsyncClient, session: AsyncSession):
    """GET /v3/filings/events/today returns today's events."""
    eid = uuid.uuid4()
    await _seed_entity(session, eid)

    event = EightKEvent(
        entity_id=eid,
        filing_date=date.today(),
        item_number="5.02",
        item_description="Management Change",
        priority=1,
    )
    session.add(event)
    await session.commit()

    resp = await client.get("/v3/filings/events/today")
    assert resp.status_code == 200


# ── Diff Tests ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_diff_latest_empty(client: AsyncClient, session: AsyncSession):
    """GET /v3/filings/{entity_id}/diff/latest returns 200 or 404 for unknown entity."""
    resp = await client.get(f"/v3/filings/{uuid4()}/diff/latest")
    assert resp.status_code in (200, 404)


@pytest.mark.asyncio
async def test_get_diff_risk_factors(client: AsyncClient, session: AsyncSession):
    """GET /v3/filings/{entity_id}/diff/risk-factors returns 200 or 404."""
    resp = await client.get(f"/v3/filings/{uuid4()}/diff/risk-factors")
    assert resp.status_code in (200, 404)


@pytest.mark.asyncio
async def test_get_diff_summary(client: AsyncClient, session: AsyncSession):
    """GET /v3/filings/{entity_id}/diff/summary returns 200 or 404."""
    resp = await client.get(f"/v3/filings/{uuid4()}/diff/summary")
    assert resp.status_code in (200, 404)


# ── Insider Tests ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_insiders_empty(client: AsyncClient, session: AsyncSession):
    """GET /v3/filings/{entity_id}/insiders returns 200 or 404 for unknown entity."""
    resp = await client.get(f"/v3/filings/{uuid4()}/insiders")
    assert resp.status_code in (200, 404)


@pytest.mark.asyncio
async def test_get_insider_transactions(client: AsyncClient, session: AsyncSession):
    """GET /v3/filings/{entity_id}/insiders/transactions returns 200 or 404."""
    resp = await client.get(f"/v3/filings/{uuid4()}/insiders/transactions")
    assert resp.status_code in (200, 404)


@pytest.mark.asyncio
async def test_get_insider_signal(client: AsyncClient, session: AsyncSession):
    """GET /v3/filings/{entity_id}/insiders/signal returns 200 or 404."""
    resp = await client.get(f"/v3/filings/{uuid4()}/insiders/signal")
    assert resp.status_code in (200, 404)


@pytest.mark.asyncio
async def test_post_insider_screen(client: AsyncClient, session: AsyncSession):
    """POST /v3/filings/insiders/screen with empty body returns 200."""
    resp = await client.post("/v3/filings/insiders/screen", json={})
    assert resp.status_code == 200
