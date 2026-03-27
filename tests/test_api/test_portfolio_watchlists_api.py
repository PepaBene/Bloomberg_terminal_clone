"""API tests for Portfolio Watchlist endpoints (Pillar 4 Phase 1)."""

import uuid
from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.entity import Entity
from src.models.portfolio_watchlist import PortfolioWatchlist, PortfolioWatchlistEntry


# ── Helpers ──────────────────────────────────────────────────────────


async def _seed_entity(session: AsyncSession) -> Entity:
    eid = uuid.uuid4()
    entity = Entity(
        entity_id=eid,
        entity_type="PUBLIC_COMPANY",
        legal_name="Watchlist Test Corp",
        status="ACTIVE",
        source="TEST",
    )
    session.add(entity)
    await session.flush()
    return entity


async def _seed_watchlist(
    session: AsyncSession, name: str = "Test Watchlist"
) -> PortfolioWatchlist:
    wl = PortfolioWatchlist(
        id=uuid.uuid4(),
        user_id="default_user",
        name=name,
        description="Test watchlist description",
    )
    session.add(wl)
    await session.flush()
    return wl


async def _seed_watchlist_entry(
    session: AsyncSession, watchlist_id: uuid.UUID, entity_id: uuid.UUID
) -> PortfolioWatchlistEntry:
    entry = PortfolioWatchlistEntry(
        id=uuid.uuid4(),
        watchlist_id=watchlist_id,
        entity_id=entity_id,
        added_date=date.today(),
    )
    session.add(entry)
    await session.flush()
    return entry


# ══════════════════════════════════════════════════════════════════════
# Watchlist CRUD
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_create_watchlist(client: AsyncClient, session: AsyncSession):
    """POST /v4/portfolios/watchlists creates a watchlist."""
    resp = await client.post("/v4/portfolios/watchlists", json={
        "name": "My Tech Watchlist",
        "description": "Tracking tech stocks",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "My Tech Watchlist"
    assert data["entities"] == []


@pytest.mark.asyncio
async def test_list_watchlists_empty(client: AsyncClient, session: AsyncSession):
    """GET /v4/portfolios/watchlists returns empty list."""
    resp = await client.get("/v4/portfolios/watchlists")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_list_watchlists_with_data(client: AsyncClient, session: AsyncSession):
    """GET /v4/portfolios/watchlists returns seeded watchlists."""
    await _seed_watchlist(session, name="WL Alpha")
    await _seed_watchlist(session, name="WL Beta")
    resp = await client.get("/v4/portfolios/watchlists")
    assert resp.status_code == 200
    data = resp.json()
    names = [wl["name"] for wl in data]
    assert "WL Alpha" in names
    assert "WL Beta" in names


@pytest.mark.asyncio
async def test_get_watchlist_by_id(client: AsyncClient, session: AsyncSession):
    """GET /v4/portfolios/watchlists/{id} returns watchlist."""
    wl = await _seed_watchlist(session, name="Get By ID")
    resp = await client.get(f"/v4/portfolios/watchlists/{wl.id}")
    assert resp.status_code == 200
    assert resp.json()["name"] == "Get By ID"


@pytest.mark.asyncio
async def test_get_watchlist_not_found(client: AsyncClient, session: AsyncSession):
    """GET /v4/portfolios/watchlists/{id} returns 404."""
    resp = await client.get(f"/v4/portfolios/watchlists/{uuid.uuid4()}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_add_entity_to_watchlist(client: AsyncClient, session: AsyncSession):
    """POST /v4/portfolios/watchlists/{wl_id}/add/{entity_id} adds entity."""
    wl = await _seed_watchlist(session, name="Add Entity WL")
    entity = await _seed_entity(session)
    resp = await client.post(
        f"/v4/portfolios/watchlists/{wl.id}/add/{entity.entity_id}"
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["entities"]) == 1
    assert data["entities"][0]["entity_id"] == str(entity.entity_id)


@pytest.mark.asyncio
async def test_add_entity_duplicate_409(client: AsyncClient, session: AsyncSession):
    """POST /v4/portfolios/watchlists/{wl_id}/add/{entity_id} duplicate returns 409."""
    wl = await _seed_watchlist(session, name="Dup Entity WL")
    entity = await _seed_entity(session)
    await _seed_watchlist_entry(session, wl.id, entity.entity_id)
    resp = await client.post(
        f"/v4/portfolios/watchlists/{wl.id}/add/{entity.entity_id}"
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_add_entity_not_found_404(client: AsyncClient, session: AsyncSession):
    """POST /v4/portfolios/watchlists/{wl_id}/add/{entity_id} entity not found 404."""
    wl = await _seed_watchlist(session, name="Entity NF WL")
    resp = await client.post(
        f"/v4/portfolios/watchlists/{wl.id}/add/{uuid.uuid4()}"
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_remove_entity_from_watchlist(client: AsyncClient, session: AsyncSession):
    """DELETE /v4/portfolios/watchlists/{wl_id}/remove/{entity_id} removes entity."""
    wl = await _seed_watchlist(session, name="Remove Entity WL")
    entity = await _seed_entity(session)
    await _seed_watchlist_entry(session, wl.id, entity.entity_id)
    resp = await client.delete(
        f"/v4/portfolios/watchlists/{wl.id}/remove/{entity.entity_id}"
    )
    assert resp.status_code == 200
    assert len(resp.json()["entities"]) == 0


@pytest.mark.asyncio
async def test_remove_entity_not_in_watchlist_404(client: AsyncClient, session: AsyncSession):
    """DELETE /v4/portfolios/watchlists/{wl_id}/remove/{entity_id} not in list 404."""
    wl = await _seed_watchlist(session, name="Not In WL")
    entity = await _seed_entity(session)
    resp = await client.delete(
        f"/v4/portfolios/watchlists/{wl.id}/remove/{entity.entity_id}"
    )
    assert resp.status_code == 404


# ══════════════════════════════════════════════════════════════════════
# Watchlist Monitoring
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_get_alerts_empty(client: AsyncClient, session: AsyncSession):
    """GET /v4/portfolios/watchlists/{wl_id}/alerts returns empty."""
    wl = await _seed_watchlist(session, name="Alerts Empty")
    resp = await client.get(f"/v4/portfolios/watchlists/{wl.id}/alerts")
    assert resp.status_code == 200
    assert resp.json()["alerts"] == []


@pytest.mark.asyncio
async def test_get_alert_digest(client: AsyncClient, session: AsyncSession):
    """GET /v4/portfolios/watchlists/{wl_id}/alerts/digest returns digest."""
    wl = await _seed_watchlist(session, name="Digest WL")
    resp = await client.get(f"/v4/portfolios/watchlists/{wl.id}/alerts/digest")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_alerts"] == 0


@pytest.mark.asyncio
async def test_configure_alerts(client: AsyncClient, session: AsyncSession):
    """POST /v4/portfolios/watchlists/{wl_id}/alerts/configure sets config."""
    wl = await _seed_watchlist(session, name="Config Alerts")
    resp = await client.post(
        f"/v4/portfolios/watchlists/{wl.id}/alerts/configure",
        json={"muted_types": ["PRICE_MOVE"], "min_severity": "HIGH"},
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_get_earnings_calendar(client: AsyncClient, session: AsyncSession):
    """GET /v4/portfolios/watchlists/{wl_id}/earnings-calendar returns entries."""
    wl = await _seed_watchlist(session, name="Earnings Cal")
    resp = await client.get(f"/v4/portfolios/watchlists/{wl.id}/earnings-calendar")
    assert resp.status_code == 200
    assert resp.json()["entries"] == []


@pytest.mark.asyncio
async def test_get_dashboard(client: AsyncClient, session: AsyncSession):
    """GET /v4/portfolios/watchlists/{wl_id}/dashboard returns entities."""
    wl = await _seed_watchlist(session, name="Dashboard WL")
    entity = await _seed_entity(session)
    await _seed_watchlist_entry(session, wl.id, entity.entity_id)
    resp = await client.get(f"/v4/portfolios/watchlists/{wl.id}/dashboard")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["entities"]) == 1
    assert data["entities"][0]["entity_id"] == str(entity.entity_id)


@pytest.mark.asyncio
async def test_get_dashboard_empty(client: AsyncClient, session: AsyncSession):
    """GET /v4/portfolios/watchlists/{wl_id}/dashboard empty returns empty list."""
    wl = await _seed_watchlist(session, name="Dashboard Empty")
    resp = await client.get(f"/v4/portfolios/watchlists/{wl.id}/dashboard")
    assert resp.status_code == 200
    assert resp.json()["entities"] == []


@pytest.mark.asyncio
async def test_watchlist_not_found_alerts(client: AsyncClient, session: AsyncSession):
    """GET /v4/portfolios/watchlists/{wl_id}/alerts returns 404 for bad id."""
    resp = await client.get(f"/v4/portfolios/watchlists/{uuid.uuid4()}/alerts")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_watchlist_not_found_dashboard(client: AsyncClient, session: AsyncSession):
    """GET /v4/portfolios/watchlists/{wl_id}/dashboard returns 404 for bad id."""
    resp = await client.get(f"/v4/portfolios/watchlists/{uuid.uuid4()}/dashboard")
    assert resp.status_code == 404
