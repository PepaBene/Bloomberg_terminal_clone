"""API tests for Investment Thesis endpoints (Pillar 3 Phase 4B)."""

import uuid
from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.entity import Entity
from src.models.investment_thesis import InvestmentThesis, ThesisVersion


# ── Helpers ──────────────────────────────────────────────────────────


async def _seed_entity(session, entity_id=None):
    eid = entity_id or uuid.uuid4()
    entity = Entity(
        entity_id=eid,
        entity_type="PUBLIC_COMPANY",
        legal_name="Thesis API Test Corp",
        status="ACTIVE",
        source="SEC_EDGAR",
    )
    session.add(entity)
    await session.flush()
    return entity


async def _seed_thesis(session, entity_id, version=1, analyst_id="analyst_001",
                       conviction_level="HIGH", investment_horizon="12M"):
    tid = uuid.uuid4()
    thesis = InvestmentThesis(
        id=tid,
        entity_id=entity_id,
        analyst_id=analyst_id,
        version=version,
        thesis_title=f"Thesis v{version}",
        investment_horizon=investment_horizon,
        conviction_level=conviction_level,
        executive_summary=f"Summary for version {version}.",
        key_drivers={"drivers": ["growth"]},
        primary_risks={"risks": ["competition"]},
        valuation_scenarios={"bull": 200, "base": 170, "bear": 130},
        catalysts={"events": ["earnings"]},
        quality_metrics={"score": 0.85},
        elevator_pitch=f"Elevator pitch v{version}.",
        slide_outline={"slides": ["Overview", "Thesis"]},
        ai_enabled=False,
    )
    session.add(thesis)
    await session.flush()
    return thesis


# ── GET /research/thesis/recent ──────────────────────────────────────


@pytest.mark.asyncio
async def test_recent_theses_empty(client: AsyncClient, session: AsyncSession):
    """GET /v4/research/thesis/recent returns empty list when no data."""
    resp = await client.get("/v4/research/thesis/recent")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_recent_theses_with_data(client: AsyncClient, session: AsyncSession):
    """GET /v4/research/thesis/recent returns theses."""
    entity = await _seed_entity(session)
    await _seed_thesis(session, entity.entity_id, version=1)
    await _seed_thesis(session, entity.entity_id, version=2)
    resp = await client.get("/v4/research/thesis/recent")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 2


@pytest.mark.asyncio
async def test_recent_theses_limit(client: AsyncClient, session: AsyncSession):
    """GET /v4/research/thesis/recent respects limit parameter."""
    entity = await _seed_entity(session)
    await _seed_thesis(session, entity.entity_id, version=1)
    await _seed_thesis(session, entity.entity_id, version=2)
    resp = await client.get("/v4/research/thesis/recent", params={"limit": 1})
    assert resp.status_code == 200
    assert len(resp.json()) == 1


# ── GET /research/thesis/quality-report ──────────────────────────────


@pytest.mark.asyncio
async def test_quality_report_empty(client: AsyncClient, session: AsyncSession):
    """GET /v4/research/thesis/quality-report returns zero counts when empty."""
    resp = await client.get("/v4/research/thesis/quality-report")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_theses"] >= 0
    assert isinstance(data["by_conviction"], dict)


@pytest.mark.asyncio
async def test_quality_report_with_data(client: AsyncClient, session: AsyncSession):
    """GET /v4/research/thesis/quality-report reflects existing theses."""
    entity = await _seed_entity(session)
    await _seed_thesis(session, entity.entity_id, version=1, conviction_level="HIGH")
    await _seed_thesis(session, entity.entity_id, version=2, conviction_level="MEDIUM")
    resp = await client.get("/v4/research/thesis/quality-report")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_theses"] >= 2


# ── GET /research/thesis/by-conviction/{level} ──────────────────────


@pytest.mark.asyncio
async def test_by_conviction_empty(client: AsyncClient, session: AsyncSession):
    """GET /v4/research/thesis/by-conviction/LOW returns empty if none."""
    resp = await client.get("/v4/research/thesis/by-conviction/LOW")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_by_conviction_with_data(client: AsyncClient, session: AsyncSession):
    """GET /v4/research/thesis/by-conviction/HIGH returns matching theses."""
    entity = await _seed_entity(session)
    await _seed_thesis(session, entity.entity_id, version=1, conviction_level="HIGH")
    await _seed_thesis(session, entity.entity_id, version=2, conviction_level="HIGH")
    resp = await client.get("/v4/research/thesis/by-conviction/HIGH")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 2
    for t in data:
        assert t["conviction_level"] == "HIGH"


# ── GET /research/thesis/by-analyst/{analyst_id} ────────────────────


@pytest.mark.asyncio
async def test_by_analyst_empty(client: AsyncClient, session: AsyncSession):
    """GET /v4/research/thesis/by-analyst/nonexistent returns empty list."""
    resp = await client.get("/v4/research/thesis/by-analyst/nonexistent_analyst")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_by_analyst_with_data(client: AsyncClient, session: AsyncSession):
    """GET /v4/research/thesis/by-analyst/{analyst_id} returns matching theses."""
    entity = await _seed_entity(session)
    await _seed_thesis(session, entity.entity_id, version=1, analyst_id="analyst_test_99")
    resp = await client.get("/v4/research/thesis/by-analyst/analyst_test_99")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert data[0]["analyst_id"] == "analyst_test_99"


# ── POST /research/thesis/{entity_id} ───────────────────────────────


@pytest.mark.asyncio
async def test_generate_thesis_not_found(client: AsyncClient, session: AsyncSession):
    """POST /v4/research/thesis/{entity_id} returns 404 for unknown entity."""
    resp = await client.post(f"/v4/research/thesis/{uuid.uuid4()}", json={
        "analyst_id": "analyst_001",
        "thesis_title": "New Thesis",
    })
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_generate_thesis_success(client: AsyncClient, session: AsyncSession):
    """POST /v4/research/thesis/{entity_id} creates a new thesis."""
    entity = await _seed_entity(session)
    resp = await client.post(f"/v4/research/thesis/{entity.entity_id}", json={
        "analyst_id": "analyst_001",
        "thesis_title": "Bullish on Cloud",
        "conviction_level": "HIGH",
        "investment_horizon": "12M",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["analyst_id"] == "analyst_001"
    assert data["version"] == 1
    assert data["thesis_title"] == "Bullish on Cloud"
    assert data["conviction_level"] == "HIGH"


# ── GET /research/thesis/{entity_id}/latest ──────────────────────────


@pytest.mark.asyncio
async def test_latest_thesis_not_found(client: AsyncClient, session: AsyncSession):
    """GET /v4/research/thesis/{entity_id}/latest returns 404 for unknown entity."""
    resp = await client.get(f"/v4/research/thesis/{uuid.uuid4()}/latest")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_latest_thesis_with_data(client: AsyncClient, session: AsyncSession):
    """GET /v4/research/thesis/{entity_id}/latest returns the latest version."""
    entity = await _seed_entity(session)
    await _seed_thesis(session, entity.entity_id, version=1)
    await _seed_thesis(session, entity.entity_id, version=2)
    resp = await client.get(f"/v4/research/thesis/{entity.entity_id}/latest")
    assert resp.status_code == 200
    data = resp.json()
    assert data["version"] == 2


# ── GET /research/thesis/{entity_id}/versions ────────────────────────


@pytest.mark.asyncio
async def test_versions_not_found(client: AsyncClient, session: AsyncSession):
    """GET /v4/research/thesis/{entity_id}/versions returns 404 for unknown entity."""
    resp = await client.get(f"/v4/research/thesis/{uuid.uuid4()}/versions")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_versions_with_data(client: AsyncClient, session: AsyncSession):
    """GET /v4/research/thesis/{entity_id}/versions returns version history."""
    entity = await _seed_entity(session)
    await _seed_thesis(session, entity.entity_id, version=1)
    await _seed_thesis(session, entity.entity_id, version=2)
    resp = await client.get(f"/v4/research/thesis/{entity.entity_id}/versions")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    assert data[0]["version"] == 2
    assert data[1]["version"] == 1


# ── GET /research/thesis/{thesis_id}/detail ──────────────────────────


@pytest.mark.asyncio
async def test_detail_not_found(client: AsyncClient, session: AsyncSession):
    """GET /v4/research/thesis/{thesis_id}/detail returns 404 for unknown thesis."""
    resp = await client.get(f"/v4/research/thesis/{uuid.uuid4()}/detail")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_detail_with_data(client: AsyncClient, session: AsyncSession):
    """GET /v4/research/thesis/{thesis_id}/detail returns thesis details."""
    entity = await _seed_entity(session)
    thesis = await _seed_thesis(session, entity.entity_id, version=1)
    resp = await client.get(f"/v4/research/thesis/{thesis.id}/detail")
    assert resp.status_code == 200
    data = resp.json()
    assert data["version"] == 1
    assert data["thesis_title"] == "Thesis v1"


# ── PUT /research/thesis/{thesis_id}/update ──────────────────────────


@pytest.mark.asyncio
async def test_update_thesis_not_found(client: AsyncClient, session: AsyncSession):
    """PUT /v4/research/thesis/{thesis_id}/update returns 404 for unknown thesis."""
    resp = await client.put(f"/v4/research/thesis/{uuid.uuid4()}/update", json={
        "conviction_level": "LOW",
    })
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_thesis_success(client: AsyncClient, session: AsyncSession):
    """PUT /v4/research/thesis/{thesis_id}/update updates thesis fields."""
    entity = await _seed_entity(session)
    thesis = await _seed_thesis(session, entity.entity_id, version=1)
    resp = await client.put(f"/v4/research/thesis/{thesis.id}/update", json={
        "conviction_level": "LOW",
        "analyst_note": "Downgraded on weak guidance.",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["conviction_level"] == "LOW"
    assert data["version"] == 2


# ── GET /research/thesis/{thesis_id}/diff ────────────────────────────


@pytest.mark.asyncio
async def test_diff_not_found(client: AsyncClient, session: AsyncSession):
    """GET /v4/research/thesis/{thesis_id}/diff returns 404 for unknown thesis."""
    resp = await client.get(f"/v4/research/thesis/{uuid.uuid4()}/diff")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_diff_no_versions(client: AsyncClient, session: AsyncSession):
    """GET /v4/research/thesis/{thesis_id}/diff returns null previous when no versions."""
    entity = await _seed_entity(session)
    thesis = await _seed_thesis(session, entity.entity_id, version=1)
    resp = await client.get(f"/v4/research/thesis/{thesis.id}/diff")
    assert resp.status_code == 200
    data = resp.json()
    assert data["current_version"] == 1
    assert data["previous_version"] is None


# ── GET /research/thesis/{thesis_id}/slides ──────────────────────────


@pytest.mark.asyncio
async def test_slides_not_found(client: AsyncClient, session: AsyncSession):
    """GET /v4/research/thesis/{thesis_id}/slides returns 404 for unknown thesis."""
    resp = await client.get(f"/v4/research/thesis/{uuid.uuid4()}/slides")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_slides_with_data(client: AsyncClient, session: AsyncSession):
    """GET /v4/research/thesis/{thesis_id}/slides returns slide outline."""
    entity = await _seed_entity(session)
    thesis = await _seed_thesis(session, entity.entity_id, version=1)
    resp = await client.get(f"/v4/research/thesis/{thesis.id}/slides")
    assert resp.status_code == 200
    data = resp.json()
    assert data["slide_outline"] == {"slides": ["Overview", "Thesis"]}


# ── GET /research/thesis/{thesis_id}/elevator ────────────────────────


@pytest.mark.asyncio
async def test_elevator_not_found(client: AsyncClient, session: AsyncSession):
    """GET /v4/research/thesis/{thesis_id}/elevator returns 404 for unknown thesis."""
    resp = await client.get(f"/v4/research/thesis/{uuid.uuid4()}/elevator")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_elevator_with_data(client: AsyncClient, session: AsyncSession):
    """GET /v4/research/thesis/{thesis_id}/elevator returns elevator pitch."""
    entity = await _seed_entity(session)
    thesis = await _seed_thesis(session, entity.entity_id, version=1)
    resp = await client.get(f"/v4/research/thesis/{thesis.id}/elevator")
    assert resp.status_code == 200
    data = resp.json()
    assert data["elevator_pitch"] == "Elevator pitch v1."
