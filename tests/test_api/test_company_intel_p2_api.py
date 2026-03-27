"""API tests for Company Intelligence P2 endpoints (Pillar 3 Phase 2)."""

import uuid
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


# ── Intelligence Report tests ────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_company_intelligence(client: AsyncClient, session: AsyncSession):
    """GET /v3/company/{entity_id}/intelligence returns 200 or 404."""
    resp = await client.get(f"/v3/company/{uuid4()}/intelligence")
    assert resp.status_code in (200, 404)


@pytest.mark.asyncio
async def test_get_company_intelligence_summary(client: AsyncClient, session: AsyncSession):
    """GET /v3/company/{entity_id}/intelligence/summary returns 200 or 404."""
    resp = await client.get(f"/v3/company/{uuid4()}/intelligence/summary")
    assert resp.status_code in (200, 404)


# ── Business Model tests ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_business_model(client: AsyncClient, session: AsyncSession):
    """GET /v3/company/{entity_id}/business-model returns 200 or 404."""
    resp = await client.get(f"/v3/company/{uuid4()}/business-model")
    assert resp.status_code in (200, 404)


@pytest.mark.asyncio
async def test_get_business_segments(client: AsyncClient, session: AsyncSession):
    """GET /v3/company/{entity_id}/business-model/segments returns 200 or 404."""
    resp = await client.get(f"/v3/company/{uuid4()}/business-model/segments")
    assert resp.status_code in (200, 404)


# ── Capital Allocation tests ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_capital_allocation(client: AsyncClient, session: AsyncSession):
    """GET /v3/company/{entity_id}/capital-allocation returns 200 or 404."""
    resp = await client.get(f"/v3/company/{uuid4()}/capital-allocation")
    assert resp.status_code in (200, 404)


@pytest.mark.asyncio
async def test_get_ma_history(client: AsyncClient, session: AsyncSession):
    """GET /v3/company/{entity_id}/capital-allocation/ma-history returns 200 or 404."""
    resp = await client.get(f"/v3/company/{uuid4()}/capital-allocation/ma-history")
    assert resp.status_code in (200, 404)


@pytest.mark.asyncio
async def test_get_buybacks(client: AsyncClient, session: AsyncSession):
    """GET /v3/company/{entity_id}/capital-allocation/buybacks returns 200 or 404."""
    resp = await client.get(f"/v3/company/{uuid4()}/capital-allocation/buybacks")
    assert resp.status_code in (200, 404)


# ── Management & Governance tests ────────────────────────────────────


@pytest.mark.asyncio
async def test_get_management_quality(client: AsyncClient, session: AsyncSession):
    """GET /v3/company/{entity_id}/management returns 200 or 404."""
    resp = await client.get(f"/v3/company/{uuid4()}/management")
    assert resp.status_code in (200, 404)


@pytest.mark.asyncio
async def test_get_governance(client: AsyncClient, session: AsyncSession):
    """GET /v3/company/{entity_id}/governance returns 200 or 404."""
    resp = await client.get(f"/v3/company/{uuid4()}/governance")
    assert resp.status_code in (200, 404)


@pytest.mark.asyncio
async def test_get_governance_red_flags(client: AsyncClient, session: AsyncSession):
    """GET /v3/company/{entity_id}/governance/red-flags returns 200 or 404."""
    resp = await client.get(f"/v3/company/{uuid4()}/governance/red-flags")
    assert resp.status_code in (200, 404)


# ── Balance Sheet Risk tests ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_balance_sheet_risk(client: AsyncClient, session: AsyncSession):
    """GET /v3/company/{entity_id}/balance-sheet-risk returns 200 or 404."""
    resp = await client.get(f"/v3/company/{uuid4()}/balance-sheet-risk")
    assert resp.status_code in (200, 404)


@pytest.mark.asyncio
async def test_get_debt_maturity(client: AsyncClient, session: AsyncSession):
    """GET /v3/company/{entity_id}/debt-maturity returns 200 or 404."""
    resp = await client.get(f"/v3/company/{uuid4()}/debt-maturity")
    assert resp.status_code in (200, 404)


@pytest.mark.asyncio
async def test_get_refinancing_risk(client: AsyncClient, session: AsyncSession):
    """GET /v3/company/{entity_id}/refinancing-risk returns 200 or 404."""
    resp = await client.get(f"/v3/company/{uuid4()}/refinancing-risk")
    assert resp.status_code in (200, 404)


# ── FI Profile tests ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_fi_profile(client: AsyncClient, session: AsyncSession):
    """GET /v3/company/{entity_id}/fi-profile returns 200 or 404."""
    resp = await client.get(f"/v3/company/{uuid4()}/fi-profile")
    assert resp.status_code in (200, 404)


@pytest.mark.asyncio
async def test_get_fi_bonds(client: AsyncClient, session: AsyncSession):
    """GET /v3/company/{entity_id}/fi-profile/bonds returns 200 or 404."""
    resp = await client.get(f"/v3/company/{uuid4()}/fi-profile/bonds")
    assert resp.status_code in (200, 404)


@pytest.mark.asyncio
async def test_get_fi_ratings(client: AsyncClient, session: AsyncSession):
    """GET /v3/company/{entity_id}/fi-profile/ratings returns 200 or 404."""
    resp = await client.get(f"/v3/company/{uuid4()}/fi-profile/ratings")
    assert resp.status_code in (200, 404)


@pytest.mark.asyncio
async def test_get_fi_maturity_wall(client: AsyncClient, session: AsyncSession):
    """GET /v3/company/{entity_id}/fi-profile/maturity-wall returns 200 or 404."""
    resp = await client.get(f"/v3/company/{uuid4()}/fi-profile/maturity-wall")
    assert resp.status_code in (200, 404)


@pytest.mark.asyncio
async def test_get_fi_market_cost_debt(client: AsyncClient, session: AsyncSession):
    """GET /v3/company/{entity_id}/fi-profile/market-cost-debt returns 200 or 404."""
    resp = await client.get(f"/v3/company/{uuid4()}/fi-profile/market-cost-debt")
    assert resp.status_code in (200, 404)
