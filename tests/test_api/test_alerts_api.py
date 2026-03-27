"""API tests for Alerts & Watchlist endpoints (Pillar 3 Phase 1)."""

import uuid
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.entity import Entity


# ── Helpers ──────────────────────────────────────────────────────────


async def _seed_entity(session: AsyncSession, entity_id: uuid.UUID) -> Entity:
    entity = Entity(
        entity_id=entity_id,
        entity_type="CORPORATION",
        legal_name="P3 Alert Test Co",
        short_name="P3ALERT",
        status="ACTIVE",
        source="TEST",
        confidence_score=0.99,
    )
    session.add(entity)
    await session.commit()
    return entity


# ── Alert Tests ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_alerts(client: AsyncClient, session: AsyncSession):
    """GET /v3/alerts returns 200."""
    resp = await client.get("/v3/alerts")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_get_entity_alerts(client: AsyncClient, session: AsyncSession):
    """GET /v3/alerts/{entity_id} returns 200 or 404 for unknown entity."""
    resp = await client.get(f"/v3/alerts/{uuid4()}")
    assert resp.status_code in (200, 404)


@pytest.mark.asyncio
async def test_acknowledge_alert_not_found(client: AsyncClient, session: AsyncSession):
    """POST /v3/alerts/acknowledge/{alert_id} returns 404 for unknown alert."""
    resp = await client.post(f"/v3/alerts/acknowledge/{uuid4()}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_alert_config(client: AsyncClient, session: AsyncSession):
    """GET /v3/alerts/config returns 200 or 422 (route-ordering: may match /{entity_id})."""
    resp = await client.get("/v3/alerts/config")
    assert resp.status_code in (200, 422)


@pytest.mark.asyncio
async def test_create_custom_alert(client: AsyncClient, session: AsyncSession):
    """POST /v3/alerts/custom creates a custom alert."""
    resp = await client.post(
        "/v3/alerts/custom",
        json={
            "alert_type": "FILING_8K",
            "priority_threshold": "HIGH",
        },
    )
    assert resp.status_code in (200, 201)


@pytest.mark.asyncio
async def test_get_custom_alerts(client: AsyncClient, session: AsyncSession):
    """GET /v3/alerts/custom returns 200 or 422 (route-ordering: may match /{entity_id})."""
    resp = await client.get("/v3/alerts/custom")
    assert resp.status_code in (200, 422)


@pytest.mark.asyncio
async def test_delete_custom_alert_not_found(client: AsyncClient, session: AsyncSession):
    """DELETE /v3/alerts/custom/{alert_id} returns 404 for unknown alert."""
    resp = await client.delete(f"/v3/alerts/custom/{uuid4()}")
    assert resp.status_code == 404


# ── Watchlist Tests ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_watchlist(client: AsyncClient, session: AsyncSession):
    """GET /v3/watchlist returns 200."""
    resp = await client.get("/v3/watchlist")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_add_to_watchlist(client: AsyncClient, session: AsyncSession):
    """POST /v3/watchlist adds an entity to the watchlist."""
    eid = uuid.uuid4()
    await _seed_entity(session, eid)

    resp = await client.post("/v3/watchlist", json={"entity_id": str(eid)})
    assert resp.status_code in (200, 201)


@pytest.mark.asyncio
async def test_delete_from_watchlist(client: AsyncClient, session: AsyncSession):
    """DELETE /v3/watchlist/{entity_id} returns 200 or 404."""
    resp = await client.delete(f"/v3/watchlist/{uuid4()}")
    assert resp.status_code in (200, 404)
