"""API tests for company intelligence endpoints (Pillar 2 Supplement – Part 7)."""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.entity import Entity


async def _seed_entity(session: AsyncSession) -> uuid.UUID:
    """Seed a test entity and return its ID."""
    eid = uuid.uuid4()
    session.add(Entity(
        entity_id=eid,
        entity_type="PUBLIC_COMPANY",
        legal_name="Intelligence Test Corp",
        status="ACTIVE",
        source="TEST",
        confidence_score=0.99,
    ))
    await session.commit()
    return eid


@pytest.mark.asyncio
async def test_get_briefing(client: AsyncClient, session: AsyncSession):
    eid = await _seed_entity(session)
    resp = await client.get(f"/v1/analytics/intelligence/{eid}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["entity_id"] == str(eid)
    assert data["briefing_type"] == "DAILY"
    assert data["status"] == "COMPLETED"
    assert data["ai_enabled"] is False


@pytest.mark.asyncio
async def test_get_briefing_entity_not_found(client: AsyncClient):
    fake_id = uuid.uuid4()
    resp = await client.get(f"/v1/analytics/intelligence/{fake_id}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_signals(client: AsyncClient, session: AsyncSession):
    eid = await _seed_entity(session)
    resp = await client.get(f"/v1/analytics/intelligence/{eid}/signals")
    assert resp.status_code == 200
    data = resp.json()
    assert data["entity_id"] == str(eid)
    assert "signals" in data


@pytest.mark.asyncio
async def test_refresh_briefing(client: AsyncClient, session: AsyncSession):
    eid = await _seed_entity(session)
    resp = await client.post(f"/v1/analytics/intelligence/{eid}/refresh")
    assert resp.status_code == 200
    data = resp.json()
    assert data["entity_id"] == str(eid)
    assert data["status"] == "COMPLETED"


@pytest.mark.asyncio
async def test_briefing_ai_disabled(client: AsyncClient, session: AsyncSession):
    eid = await _seed_entity(session)
    resp = await client.get(f"/v1/analytics/intelligence/{eid}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ai_enabled"] is False
    assert data["summary_text"] is None
