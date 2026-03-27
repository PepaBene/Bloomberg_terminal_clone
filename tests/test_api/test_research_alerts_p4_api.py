"""API tests for Intelligent Alerts endpoints (Pillar 3 Phase 4C)."""

import uuid
from datetime import date, datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.entity import Entity
from src.models.intelligent_alerts import ConsolidatedAlert


# ── Helpers ──────────────────────────────────────────────────────────


async def _seed_entity(session, entity_id=None):
    eid = entity_id or uuid.uuid4()
    entity = Entity(
        entity_id=eid,
        entity_type="PUBLIC_COMPANY",
        legal_name="Alert API Test Corp",
        status="ACTIVE",
        source="SEC_EDGAR",
    )
    session.add(entity)
    await session.flush()
    return entity


async def _seed_alert(session, entity_id, priority=2, headline="Test alert",
                      primary_type="NEWS_ALERT", acknowledged=False):
    aid = uuid.uuid4()
    alert = ConsolidatedAlert(
        id=aid,
        entity_id=entity_id,
        alert_priority=priority,
        alert_categories={"categories": ["NEWS"]},
        primary_headline=headline,
        primary_type=primary_type,
        ai_synthesis="AI-generated synthesis for testing.",
        recommended_action="MONITOR",
        is_acknowledged=acknowledged,
    )
    session.add(alert)
    await session.flush()
    return alert


# ── GET /research/alerts/feed ───────────────────────────────────────


@pytest.mark.asyncio
async def test_alert_feed_empty(client: AsyncClient, session: AsyncSession):
    """GET /v4/research/alerts/feed returns empty feed."""
    resp = await client.get("/v4/research/alerts/feed")
    assert resp.status_code == 200
    data = resp.json()
    assert "alerts" in data
    assert "total_count" in data
    assert "critical_count" in data
    assert isinstance(data["alerts"], list)


@pytest.mark.asyncio
async def test_alert_feed_with_data(client: AsyncClient, session: AsyncSession):
    """GET /v4/research/alerts/feed returns populated feed."""
    entity = await _seed_entity(session)
    await _seed_alert(session, entity.entity_id, priority=1, headline="Critical alert")
    await _seed_alert(session, entity.entity_id, priority=2, headline="Normal alert")
    resp = await client.get("/v4/research/alerts/feed")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_count"] >= 2
    assert data["critical_count"] >= 1
    assert len(data["alerts"]) >= 2


@pytest.mark.asyncio
async def test_alert_feed_limit(client: AsyncClient, session: AsyncSession):
    """GET /v4/research/alerts/feed respects limit parameter."""
    entity = await _seed_entity(session)
    await _seed_alert(session, entity.entity_id, headline="A1")
    await _seed_alert(session, entity.entity_id, headline="A2")
    resp = await client.get("/v4/research/alerts/feed", params={"limit": 1})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["alerts"]) == 1


# ── GET /research/alerts/critical ───────────────────────────────────


@pytest.mark.asyncio
async def test_critical_alerts_empty(client: AsyncClient, session: AsyncSession):
    """GET /v4/research/alerts/critical returns empty list."""
    resp = await client.get("/v4/research/alerts/critical")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_critical_alerts_with_data(client: AsyncClient, session: AsyncSession):
    """GET /v4/research/alerts/critical returns only priority=1 alerts."""
    entity = await _seed_entity(session)
    await _seed_alert(session, entity.entity_id, priority=1, headline="Critical one")
    await _seed_alert(session, entity.entity_id, priority=3, headline="Low priority")
    resp = await client.get("/v4/research/alerts/critical")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    for alert in data:
        assert alert["alert_priority"] == 1


# ── GET /research/alerts/today ──────────────────────────────────────


@pytest.mark.asyncio
async def test_today_alerts(client: AsyncClient, session: AsyncSession):
    """GET /v4/research/alerts/today returns today's alerts."""
    resp = await client.get("/v4/research/alerts/today")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


# ── GET /research/alerts/statistics ─────────────────────────────────


@pytest.mark.asyncio
async def test_alert_statistics_empty(client: AsyncClient, session: AsyncSession):
    """GET /v4/research/alerts/statistics returns stats structure."""
    resp = await client.get("/v4/research/alerts/statistics")
    assert resp.status_code == 200
    data = resp.json()
    assert "total_alerts" in data
    assert "acknowledged_count" in data
    assert "unacknowledged_count" in data
    assert "critical_count" in data
    assert "type_counts" in data


@pytest.mark.asyncio
async def test_alert_statistics_with_data(client: AsyncClient, session: AsyncSession):
    """GET /v4/research/alerts/statistics returns correct counts."""
    entity = await _seed_entity(session)
    await _seed_alert(session, entity.entity_id, priority=1, acknowledged=False)
    await _seed_alert(session, entity.entity_id, priority=2, acknowledged=True)
    resp = await client.get("/v4/research/alerts/statistics")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_alerts"] >= 2


# ── GET /research/alerts/by-category/{category} ────────────────────


@pytest.mark.asyncio
async def test_alerts_by_category_empty(client: AsyncClient, session: AsyncSession):
    """GET /v4/research/alerts/by-category/{category} returns empty for no match."""
    resp = await client.get("/v4/research/alerts/by-category/NONEXISTENT")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_alerts_by_category_with_data(client: AsyncClient, session: AsyncSession):
    """GET /v4/research/alerts/by-category/{category} returns matching alerts."""
    entity = await _seed_entity(session)
    await _seed_alert(session, entity.entity_id, primary_type="EARNINGS_ALERT")
    await _seed_alert(session, entity.entity_id, primary_type="FILING_ALERT")
    resp = await client.get("/v4/research/alerts/by-category/EARNINGS_ALERT")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    for alert in data:
        assert alert["primary_type"] == "EARNINGS_ALERT"


# ── GET /research/alerts/{entity_id} ───────────────────────────────


@pytest.mark.asyncio
async def test_entity_alerts_empty(client: AsyncClient, session: AsyncSession):
    """GET /v4/research/alerts/{entity_id} returns empty for entity with no alerts."""
    resp = await client.get(f"/v4/research/alerts/{uuid.uuid4()}")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_entity_alerts_with_data(client: AsyncClient, session: AsyncSession):
    """GET /v4/research/alerts/{entity_id} returns entity-specific alerts."""
    entity = await _seed_entity(session)
    await _seed_alert(session, entity.entity_id, priority=1, headline="Entity alert 1")
    await _seed_alert(session, entity.entity_id, priority=2, headline="Entity alert 2")
    resp = await client.get(f"/v4/research/alerts/{entity.entity_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 2
    for alert in data:
        assert alert["entity_id"] == str(entity.entity_id)


@pytest.mark.asyncio
async def test_entity_alerts_limit(client: AsyncClient, session: AsyncSession):
    """GET /v4/research/alerts/{entity_id} respects limit parameter."""
    entity = await _seed_entity(session)
    await _seed_alert(session, entity.entity_id, headline="E1")
    await _seed_alert(session, entity.entity_id, headline="E2")
    resp = await client.get(f"/v4/research/alerts/{entity.entity_id}", params={"limit": 1})
    assert resp.status_code == 200
    assert len(resp.json()) == 1


# ── POST /research/alerts/{alert_id}/acknowledge ───────────────────


@pytest.mark.asyncio
async def test_acknowledge_alert_not_found(client: AsyncClient, session: AsyncSession):
    """POST /v4/research/alerts/{alert_id}/acknowledge returns 404."""
    resp = await client.post(f"/v4/research/alerts/{uuid.uuid4()}/acknowledge")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_acknowledge_alert_success(client: AsyncClient, session: AsyncSession):
    """POST /v4/research/alerts/{alert_id}/acknowledge acknowledges an alert."""
    entity = await _seed_entity(session)
    alert = await _seed_alert(session, entity.entity_id, headline="To acknowledge")
    resp = await client.post(
        f"/v4/research/alerts/{alert.id}/acknowledge",
        params={"acknowledged_by": "analyst_001"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_acknowledged"] is True
    assert data["acknowledged_by"] == "analyst_001"
    assert data["acknowledged_at"] is not None


@pytest.mark.asyncio
async def test_acknowledge_alert_default_user(client: AsyncClient, session: AsyncSession):
    """POST /v4/research/alerts/{alert_id}/acknowledge uses default user."""
    entity = await _seed_entity(session)
    alert = await _seed_alert(session, entity.entity_id)
    resp = await client.post(f"/v4/research/alerts/{alert.id}/acknowledge")
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_acknowledged"] is True
    assert data["acknowledged_by"] == "system"


@pytest.mark.asyncio
async def test_alert_response_fields(client: AsyncClient, session: AsyncSession):
    """Verify all expected fields are present in alert response."""
    entity = await _seed_entity(session)
    alert = await _seed_alert(session, entity.entity_id, priority=1,
                              headline="Full fields test")
    resp = await client.get(f"/v4/research/alerts/{entity.entity_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    item = data[0]
    assert "id" in item
    assert "entity_id" in item
    assert "alert_priority" in item
    assert "primary_headline" in item
    assert "primary_type" in item
    assert "ai_synthesis" in item
    assert "recommended_action" in item
    assert "is_acknowledged" in item
