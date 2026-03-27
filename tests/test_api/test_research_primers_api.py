"""API tests for Research Primers endpoints (Pillar 3 Phase 4A)."""

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.entity import Entity
from src.models.company_primer_model import CompanyPrimer, PrimerRefreshLog


# ── Helpers ──────────────────────────────────────────────────────────


async def _seed_entity(session, entity_id=None):
    eid = entity_id or uuid.uuid4()
    entity = Entity(
        entity_id=eid,
        entity_type="PUBLIC_COMPANY",
        legal_name="Primer Test Corp",
        status="ACTIVE",
        source="SEC_EDGAR",
    )
    session.add(entity)
    await session.flush()
    return entity


async def _seed_primer(session, entity_id, version=1):
    pid = uuid.uuid4()
    primer = CompanyPrimer(
        id=pid,
        primer_id=uuid.uuid4(),
        generated_date=date(2025, 10, 15 + version),
        entity_id=entity_id,
        primer_version=version,
        executive_summary=f"Primer version {version} summary.",
        business_model={"type": "SaaS"},
        competitive_landscape={"moat": "HIGH"},
        financial_health={"debt_to_equity": 0.3},
        strategic_initiatives={"focus": ["AI"]},
        risk_factors={"regulatory": "MEDIUM"},
        analyst_consensus={"rating": "BUY"},
        recent_catalysts={"events": ["earnings beat"]},
        data_completeness_score=Decimal("85.00"),
        last_filing_date=date(2025, 10, 15),
        last_earnings_call_date=date(2025, 10, 20),
        ai_enabled=True,
        prompt_template_used="v2_standard",
    )
    session.add(primer)
    await session.flush()
    return primer


# ── GET /research/primers/recent ─────────────────────────────────────


@pytest.mark.asyncio
async def test_recent_primers_empty(client: AsyncClient, session: AsyncSession):
    """GET /v4/research/primers/recent returns empty list when no data."""
    resp = await client.get("/v4/research/primers/recent")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_recent_primers_with_data(client: AsyncClient, session: AsyncSession):
    """GET /v4/research/primers/recent returns primers."""
    entity = await _seed_entity(session)
    await _seed_primer(session, entity.entity_id, version=1)
    await _seed_primer(session, entity.entity_id, version=2)
    resp = await client.get("/v4/research/primers/recent")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 2


@pytest.mark.asyncio
async def test_recent_primers_limit(client: AsyncClient, session: AsyncSession):
    """GET /v4/research/primers/recent respects limit parameter."""
    entity = await _seed_entity(session)
    await _seed_primer(session, entity.entity_id, version=1)
    await _seed_primer(session, entity.entity_id, version=2)
    resp = await client.get("/v4/research/primers/recent", params={"limit": 1})
    assert resp.status_code == 200
    assert len(resp.json()) == 1


# ── GET /research/primers/{entity_id} ────────────────────────────────


@pytest.mark.asyncio
async def test_get_latest_primer_not_found(client: AsyncClient, session: AsyncSession):
    """GET /v4/research/primers/{entity_id} returns 404 for unknown entity."""
    resp = await client.get(f"/v4/research/primers/{uuid.uuid4()}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_latest_primer_no_primer(client: AsyncClient, session: AsyncSession):
    """GET /v4/research/primers/{entity_id} returns 404 when entity exists but no primer."""
    entity = await _seed_entity(session)
    resp = await client.get(f"/v4/research/primers/{entity.entity_id}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_latest_primer_with_data(client: AsyncClient, session: AsyncSession):
    """GET /v4/research/primers/{entity_id} returns latest version."""
    entity = await _seed_entity(session)
    await _seed_primer(session, entity.entity_id, version=1)
    await _seed_primer(session, entity.entity_id, version=2)
    resp = await client.get(f"/v4/research/primers/{entity.entity_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["primer_version"] == 2


# ── GET /research/primers/{entity_id}/history ────────────────────────


@pytest.mark.asyncio
async def test_primer_history_not_found(client: AsyncClient, session: AsyncSession):
    """GET /v4/research/primers/{entity_id}/history returns 404 for unknown entity."""
    resp = await client.get(f"/v4/research/primers/{uuid.uuid4()}/history")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_primer_history_with_data(client: AsyncClient, session: AsyncSession):
    """GET /v4/research/primers/{entity_id}/history returns all versions."""
    entity = await _seed_entity(session)
    await _seed_primer(session, entity.entity_id, version=1)
    await _seed_primer(session, entity.entity_id, version=2)
    resp = await client.get(f"/v4/research/primers/{entity.entity_id}/history")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    # Should be ordered by version desc
    assert data[0]["primer_version"] == 2
    assert data[1]["primer_version"] == 1


# ── POST /research/primers/{entity_id}/refresh ───────────────────────


@pytest.mark.asyncio
async def test_refresh_primer_not_found(client: AsyncClient, session: AsyncSession):
    """POST /v4/research/primers/{entity_id}/refresh returns 404 for unknown entity."""
    resp = await client.post(f"/v4/research/primers/{uuid.uuid4()}/refresh")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_refresh_primer_success(client: AsyncClient, session: AsyncSession):
    """POST /v4/research/primers/{entity_id}/refresh creates refresh log."""
    entity = await _seed_entity(session)
    resp = await client.post(f"/v4/research/primers/{entity.entity_id}/refresh")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "PENDING"
    assert data["refresh_type"] == "MANUAL"
    assert data["trigger_event"] == "API_REQUEST"


# ── GET /research/primers/{entity_id}/completeness ───────────────────


@pytest.mark.asyncio
async def test_completeness_not_found(client: AsyncClient, session: AsyncSession):
    """GET /v4/research/primers/{entity_id}/completeness returns 404 for unknown entity."""
    resp = await client.get(f"/v4/research/primers/{uuid.uuid4()}/completeness")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_completeness_with_data(client: AsyncClient, session: AsyncSession):
    """GET /v4/research/primers/{entity_id}/completeness returns score."""
    entity = await _seed_entity(session)
    await _seed_primer(session, entity.entity_id)
    resp = await client.get(f"/v4/research/primers/{entity.entity_id}/completeness")
    assert resp.status_code == 200
    data = resp.json()
    assert data["data_completeness_score"] == 85.0
    assert data["ai_enabled"] is True


# ── GET /research/primers/{entity_id}/risks ──────────────────────────


@pytest.mark.asyncio
async def test_risks_not_found(client: AsyncClient, session: AsyncSession):
    """GET /v4/research/primers/{entity_id}/risks returns 404 for unknown entity."""
    resp = await client.get(f"/v4/research/primers/{uuid.uuid4()}/risks")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_risks_with_data(client: AsyncClient, session: AsyncSession):
    """GET /v4/research/primers/{entity_id}/risks returns risk factors."""
    entity = await _seed_entity(session)
    await _seed_primer(session, entity.entity_id)
    resp = await client.get(f"/v4/research/primers/{entity.entity_id}/risks")
    assert resp.status_code == 200
    data = resp.json()
    assert data["risk_factors"] == {"regulatory": "MEDIUM"}


# ── GET /research/primers/{entity_id}/catalysts ──────────────────────


@pytest.mark.asyncio
async def test_catalysts_with_data(client: AsyncClient, session: AsyncSession):
    """GET /v4/research/primers/{entity_id}/catalysts returns catalysts."""
    entity = await _seed_entity(session)
    await _seed_primer(session, entity.entity_id)
    resp = await client.get(f"/v4/research/primers/{entity.entity_id}/catalysts")
    assert resp.status_code == 200
    data = resp.json()
    assert data["recent_catalysts"] == {"events": ["earnings beat"]}


# ── GET /research/primers/{entity_id}/financials ─────────────────────


@pytest.mark.asyncio
async def test_financials_with_data(client: AsyncClient, session: AsyncSession):
    """GET /v4/research/primers/{entity_id}/financials returns financial health."""
    entity = await _seed_entity(session)
    await _seed_primer(session, entity.entity_id)
    resp = await client.get(f"/v4/research/primers/{entity.entity_id}/financials")
    assert resp.status_code == 200
    data = resp.json()
    assert data["financial_health"] == {"debt_to_equity": 0.3}


# ── GET /research/primers/{entity_id}/competitive ────────────────────


@pytest.mark.asyncio
async def test_competitive_with_data(client: AsyncClient, session: AsyncSession):
    """GET /v4/research/primers/{entity_id}/competitive returns landscape."""
    entity = await _seed_entity(session)
    await _seed_primer(session, entity.entity_id)
    resp = await client.get(f"/v4/research/primers/{entity.entity_id}/competitive")
    assert resp.status_code == 200
    data = resp.json()
    assert data["competitive_landscape"] == {"moat": "HIGH"}


# ── GET /research/primers/{entity_id}/strategic ──────────────────────


@pytest.mark.asyncio
async def test_strategic_with_data(client: AsyncClient, session: AsyncSession):
    """GET /v4/research/primers/{entity_id}/strategic returns initiatives."""
    entity = await _seed_entity(session)
    await _seed_primer(session, entity.entity_id)
    resp = await client.get(f"/v4/research/primers/{entity.entity_id}/strategic")
    assert resp.status_code == 200
    data = resp.json()
    assert data["strategic_initiatives"] == {"focus": ["AI"]}
