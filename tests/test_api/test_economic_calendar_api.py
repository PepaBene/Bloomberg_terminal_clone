"""API tests for Economic Calendar endpoints (Pillar 3 Phase 2)."""

import uuid
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


# ── Static route tests ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_economic_calendar(client: AsyncClient, session: AsyncSession):
    """GET /v3/news/calendar/economic returns 200."""
    resp = await client.get("/v3/news/calendar/economic")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_get_economic_calendar_with_params(client: AsyncClient, session: AsyncSession):
    """GET /v3/news/calendar/economic with filters returns 200."""
    resp = await client.get("/v3/news/calendar/economic?days_ahead=14&importance=HIGH")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_get_economic_surprises(client: AsyncClient, session: AsyncSession):
    """GET /v3/news/calendar/economic/surprises returns 200."""
    resp = await client.get("/v3/news/calendar/economic/surprises")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_get_central_bank_events(client: AsyncClient, session: AsyncSession):
    """GET /v3/news/calendar/central-banks returns 200."""
    resp = await client.get("/v3/news/calendar/central-banks")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_get_earnings_calendar_events(client: AsyncClient, session: AsyncSession):
    """GET /v3/news/calendar/earnings returns 200."""
    resp = await client.get("/v3/news/calendar/earnings")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_get_regulatory_calendar(client: AsyncClient, session: AsyncSession):
    """GET /v3/news/calendar/regulatory returns 200."""
    resp = await client.get("/v3/news/calendar/regulatory")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_get_corporate_events(client: AsyncClient, session: AsyncSession):
    """GET /v3/news/calendar/corporate returns 200."""
    resp = await client.get("/v3/news/calendar/corporate")
    assert resp.status_code == 200


# ── Parametric route tests ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_economic_release_detail(client: AsyncClient, session: AsyncSession):
    """GET /v3/news/calendar/economic/{release_id} returns 200 or 404."""
    resp = await client.get(f"/v3/news/calendar/economic/{uuid4()}")
    assert resp.status_code in (200, 404)


@pytest.mark.asyncio
async def test_get_economic_release_detail_not_found(client: AsyncClient, session: AsyncSession):
    """GET /v3/news/calendar/economic/{release_id} returns 404 for unknown release."""
    resp = await client.get(f"/v3/news/calendar/economic/{uuid4()}")
    assert resp.status_code == 404
