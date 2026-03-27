"""API tests for Governance Intelligence endpoints (Pillar 3 Phase 1)."""

from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


# ── Tests ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_proxy(client: AsyncClient, session: AsyncSession):
    """GET /v3/filings/{entity_id}/proxy returns 200 or 404."""
    resp = await client.get(f"/v3/filings/{uuid4()}/proxy")
    assert resp.status_code in (200, 404)


@pytest.mark.asyncio
async def test_get_proxy_compensation(client: AsyncClient, session: AsyncSession):
    """GET /v3/filings/{entity_id}/proxy/compensation returns 200 or 404."""
    resp = await client.get(f"/v3/filings/{uuid4()}/proxy/compensation")
    assert resp.status_code in (200, 404)


@pytest.mark.asyncio
async def test_get_proxy_governance(client: AsyncClient, session: AsyncSession):
    """GET /v3/filings/{entity_id}/proxy/governance returns 200 or 404."""
    resp = await client.get(f"/v3/filings/{uuid4()}/proxy/governance")
    assert resp.status_code in (200, 404)


@pytest.mark.asyncio
async def test_get_proxy_red_flags(client: AsyncClient, session: AsyncSession):
    """GET /v3/filings/{entity_id}/proxy/red-flags returns 200 or 404."""
    resp = await client.get(f"/v3/filings/{uuid4()}/proxy/red-flags")
    assert resp.status_code in (200, 404)


@pytest.mark.asyncio
async def test_get_proxy_proposals(client: AsyncClient, session: AsyncSession):
    """GET /v3/filings/{entity_id}/proxy/proposals returns 200 or 404."""
    resp = await client.get(f"/v3/filings/{uuid4()}/proxy/proposals")
    assert resp.status_code in (200, 404)


@pytest.mark.asyncio
async def test_get_proxy_board(client: AsyncClient, session: AsyncSession):
    """GET /v3/filings/{entity_id}/proxy/board returns 200 or 404."""
    resp = await client.get(f"/v3/filings/{uuid4()}/proxy/board")
    assert resp.status_code in (200, 404)
