"""API tests for Investment Thesis endpoints (Pillar 3 Phase 4B).

M-005: analyst_id is now derived from the authenticated caller
(Depends(get_current_active_user)) rather than a caller-supplied string,
so every test authenticates as a real seeded User via the shared
`test_user`/`auth_headers` fixtures (tests/test_api/conftest.py).
"""

import uuid
from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.entity import Entity
from src.models.investment_thesis import InvestmentThesis


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


async def _seed_thesis(session, entity_id, analyst_id, version=1,
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
        # Real shape (_build_slide_outline() in research_thesis.py) is
        # list[dict], one entry per slide -- NOT {"slides": [...]}. The old
        # dict-shaped fixture here was masking a genuine schema bug (see
        # ThesisResponse.slide_outline) where every real response 422'd.
        slide_outline=[
            {"slide_number": 1, "title": "Overview", "bullet_points": ["Conviction: HIGH"]},
            {"slide_number": 2, "title": "Thesis", "bullet_points": ["growth"]},
        ],
        ai_enabled=False,
    )
    session.add(thesis)
    await session.flush()
    return thesis


# ── Auth enforcement ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_thesis_endpoints_require_auth(client: AsyncClient, session: AsyncSession):
    """No Bearer token -> 401, not a silent anonymous read."""
    resp = await client.get("/v4/research/thesis/recent")
    assert resp.status_code == 401


# ── GET /research/thesis/recent ──────────────────────────────────────


@pytest.mark.asyncio
async def test_recent_theses_empty(client: AsyncClient, session: AsyncSession, auth_headers):
    """GET /v4/research/thesis/recent returns empty list when no data."""
    resp = await client.get("/v4/research/thesis/recent", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_recent_theses_with_data(client: AsyncClient, session: AsyncSession, test_user, auth_headers):
    """GET /v4/research/thesis/recent returns theses."""
    entity = await _seed_entity(session)
    await _seed_thesis(session, entity.entity_id, test_user.user_id, version=1)
    await _seed_thesis(session, entity.entity_id, test_user.user_id, version=2)
    resp = await client.get("/v4/research/thesis/recent", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 2


@pytest.mark.asyncio
async def test_recent_theses_limit(client: AsyncClient, session: AsyncSession, test_user, auth_headers):
    """GET /v4/research/thesis/recent respects limit parameter."""
    entity = await _seed_entity(session)
    await _seed_thesis(session, entity.entity_id, test_user.user_id, version=1)
    await _seed_thesis(session, entity.entity_id, test_user.user_id, version=2)
    resp = await client.get("/v4/research/thesis/recent", params={"limit": 1}, headers=auth_headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 1


# ── GET /research/thesis/quality-report ──────────────────────────────


@pytest.mark.asyncio
async def test_quality_report_empty(client: AsyncClient, session: AsyncSession, auth_headers):
    """GET /v4/research/thesis/quality-report returns zero counts when empty."""
    resp = await client.get("/v4/research/thesis/quality-report", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_theses"] >= 0
    assert isinstance(data["by_conviction"], dict)


@pytest.mark.asyncio
async def test_quality_report_with_data(client: AsyncClient, session: AsyncSession, test_user, auth_headers):
    """GET /v4/research/thesis/quality-report reflects existing theses."""
    entity = await _seed_entity(session)
    await _seed_thesis(session, entity.entity_id, test_user.user_id, version=1, conviction_level="HIGH")
    await _seed_thesis(session, entity.entity_id, test_user.user_id, version=2, conviction_level="MEDIUM")
    resp = await client.get("/v4/research/thesis/quality-report", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_theses"] >= 2


# ── GET /research/thesis/by-conviction/{level} ──────────────────────


@pytest.mark.asyncio
async def test_by_conviction_empty(client: AsyncClient, session: AsyncSession, auth_headers):
    """GET /v4/research/thesis/by-conviction/LOW returns empty if none."""
    resp = await client.get("/v4/research/thesis/by-conviction/LOW", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_by_conviction_with_data(client: AsyncClient, session: AsyncSession, test_user, auth_headers):
    """GET /v4/research/thesis/by-conviction/HIGH returns matching theses."""
    entity = await _seed_entity(session)
    await _seed_thesis(session, entity.entity_id, test_user.user_id, version=1, conviction_level="HIGH")
    await _seed_thesis(session, entity.entity_id, test_user.user_id, version=2, conviction_level="HIGH")
    resp = await client.get("/v4/research/thesis/by-conviction/HIGH", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 2
    for t in data:
        assert t["conviction_level"] == "HIGH"


# ── GET /research/thesis/by-analyst/{analyst_id} ────────────────────


@pytest.mark.asyncio
async def test_by_analyst_empty(client: AsyncClient, session: AsyncSession, auth_headers):
    """GET /v4/research/thesis/by-analyst/{uuid} returns empty list for an unused id."""
    resp = await client.get(f"/v4/research/thesis/by-analyst/{uuid.uuid4()}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_by_analyst_with_data(client: AsyncClient, session: AsyncSession, test_user, auth_headers):
    """GET /v4/research/thesis/by-analyst/{analyst_id} returns that analyst's theses."""
    entity = await _seed_entity(session)
    await _seed_thesis(session, entity.entity_id, test_user.user_id, version=1)
    resp = await client.get(f"/v4/research/thesis/by-analyst/{test_user.user_id}", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert data[0]["analyst_id"] == str(test_user.user_id)


# ── POST /research/thesis/{entity_id} ───────────────────────────────


@pytest.mark.asyncio
async def test_generate_thesis_not_found(client: AsyncClient, session: AsyncSession, auth_headers):
    """POST /v4/research/thesis/{entity_id} returns 404 for unknown entity."""
    resp = await client.post(
        f"/v4/research/thesis/{uuid.uuid4()}",
        json={"thesis_title": "New Thesis"},
        headers=auth_headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_generate_thesis_success(client: AsyncClient, session: AsyncSession, test_user, auth_headers):
    """POST /v4/research/thesis/{entity_id} creates a new thesis attributed to the caller."""
    entity = await _seed_entity(session)
    resp = await client.post(f"/v4/research/thesis/{entity.entity_id}", json={
        "thesis_title": "Bullish on Cloud",
        "conviction_level": "HIGH",
        "investment_horizon": "12M",
    }, headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["analyst_id"] == str(test_user.user_id)
    assert data["version"] == 1
    assert data["thesis_title"] == "Bullish on Cloud"
    assert data["conviction_level"] == "HIGH"


# ── GET /research/thesis/{entity_id}/latest ──────────────────────────


@pytest.mark.asyncio
async def test_latest_thesis_not_found(client: AsyncClient, session: AsyncSession, auth_headers):
    """GET /v4/research/thesis/{entity_id}/latest returns 404 for unknown entity."""
    resp = await client.get(f"/v4/research/thesis/{uuid.uuid4()}/latest", headers=auth_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_latest_thesis_with_data(client: AsyncClient, session: AsyncSession, test_user, auth_headers):
    """GET /v4/research/thesis/{entity_id}/latest returns the latest version."""
    entity = await _seed_entity(session)
    await _seed_thesis(session, entity.entity_id, test_user.user_id, version=1)
    await _seed_thesis(session, entity.entity_id, test_user.user_id, version=2)
    resp = await client.get(f"/v4/research/thesis/{entity.entity_id}/latest", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["version"] == 2


# ── GET /research/thesis/{entity_id}/versions ────────────────────────


@pytest.mark.asyncio
async def test_versions_not_found(client: AsyncClient, session: AsyncSession, auth_headers):
    """GET /v4/research/thesis/{entity_id}/versions returns 404 for unknown entity."""
    resp = await client.get(f"/v4/research/thesis/{uuid.uuid4()}/versions", headers=auth_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_versions_with_data(client: AsyncClient, session: AsyncSession, test_user, auth_headers):
    """GET /v4/research/thesis/{entity_id}/versions returns version history."""
    entity = await _seed_entity(session)
    await _seed_thesis(session, entity.entity_id, test_user.user_id, version=1)
    await _seed_thesis(session, entity.entity_id, test_user.user_id, version=2)
    resp = await client.get(f"/v4/research/thesis/{entity.entity_id}/versions", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    assert data[0]["version"] == 2
    assert data[1]["version"] == 1


# ── GET /research/thesis/{thesis_id}/detail ──────────────────────────


@pytest.mark.asyncio
async def test_detail_not_found(client: AsyncClient, session: AsyncSession, auth_headers):
    """GET /v4/research/thesis/{thesis_id}/detail returns 404 for unknown thesis."""
    resp = await client.get(f"/v4/research/thesis/{uuid.uuid4()}/detail", headers=auth_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_detail_with_data(client: AsyncClient, session: AsyncSession, test_user, auth_headers):
    """GET /v4/research/thesis/{thesis_id}/detail returns thesis details."""
    entity = await _seed_entity(session)
    thesis = await _seed_thesis(session, entity.entity_id, test_user.user_id, version=1)
    resp = await client.get(f"/v4/research/thesis/{thesis.id}/detail", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["version"] == 1
    assert data["thesis_title"] == "Thesis v1"


# ── PUT /research/thesis/{thesis_id}/update ──────────────────────────


@pytest.mark.asyncio
async def test_update_thesis_not_found(client: AsyncClient, session: AsyncSession, auth_headers):
    """PUT /v4/research/thesis/{thesis_id}/update returns 404 for unknown thesis."""
    resp = await client.put(f"/v4/research/thesis/{uuid.uuid4()}/update", json={
        "conviction_level": "LOW",
    }, headers=auth_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_thesis_success(client: AsyncClient, session: AsyncSession, test_user, auth_headers):
    """PUT /v4/research/thesis/{thesis_id}/update updates thesis fields."""
    entity = await _seed_entity(session)
    thesis = await _seed_thesis(session, entity.entity_id, test_user.user_id, version=1)
    resp = await client.put(f"/v4/research/thesis/{thesis.id}/update", json={
        "conviction_level": "LOW",
        "analyst_note": "Downgraded on weak guidance.",
    }, headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["conviction_level"] == "LOW"
    assert data["version"] == 2


# ── GET /research/thesis/{thesis_id}/diff ────────────────────────────


@pytest.mark.asyncio
async def test_diff_not_found(client: AsyncClient, session: AsyncSession, auth_headers):
    """GET /v4/research/thesis/{thesis_id}/diff returns 404 for unknown thesis."""
    resp = await client.get(f"/v4/research/thesis/{uuid.uuid4()}/diff", headers=auth_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_diff_no_versions(client: AsyncClient, session: AsyncSession, test_user, auth_headers):
    """GET /v4/research/thesis/{thesis_id}/diff returns null previous when no versions."""
    entity = await _seed_entity(session)
    thesis = await _seed_thesis(session, entity.entity_id, test_user.user_id, version=1)
    resp = await client.get(f"/v4/research/thesis/{thesis.id}/diff", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["current_version"] == 1
    assert data["previous_version"] is None


# ── GET /research/thesis/{thesis_id}/slides ──────────────────────────


@pytest.mark.asyncio
async def test_slides_not_found(client: AsyncClient, session: AsyncSession, auth_headers):
    """GET /v4/research/thesis/{thesis_id}/slides returns 404 for unknown thesis."""
    resp = await client.get(f"/v4/research/thesis/{uuid.uuid4()}/slides", headers=auth_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_slides_with_data(client: AsyncClient, session: AsyncSession, test_user, auth_headers):
    """GET /v4/research/thesis/{thesis_id}/slides returns slide outline."""
    entity = await _seed_entity(session)
    thesis = await _seed_thesis(session, entity.entity_id, test_user.user_id, version=1)
    resp = await client.get(f"/v4/research/thesis/{thesis.id}/slides", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["slide_outline"] == [
        {"slide_number": 1, "title": "Overview", "bullet_points": ["Conviction: HIGH"]},
        {"slide_number": 2, "title": "Thesis", "bullet_points": ["growth"]},
    ]


# ── GET /research/thesis/{thesis_id}/elevator ────────────────────────


@pytest.mark.asyncio
async def test_elevator_not_found(client: AsyncClient, session: AsyncSession, auth_headers):
    """GET /v4/research/thesis/{thesis_id}/elevator returns 404 for unknown thesis."""
    resp = await client.get(f"/v4/research/thesis/{uuid.uuid4()}/elevator", headers=auth_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_elevator_with_data(client: AsyncClient, session: AsyncSession, test_user, auth_headers):
    """GET /v4/research/thesis/{thesis_id}/elevator returns elevator pitch."""
    entity = await _seed_entity(session)
    thesis = await _seed_thesis(session, entity.entity_id, test_user.user_id, version=1)
    resp = await client.get(f"/v4/research/thesis/{thesis.id}/elevator", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["elevator_pitch"] == "Elevator pitch v1."


# ── POST /research/thesis/{thesis_id}/validate (previously missing) ──


@pytest.mark.asyncio
async def test_validate_requires_auth(client: AsyncClient, session: AsyncSession):
    resp = await client.post(f"/v4/research/thesis/{uuid.uuid4()}/validate")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_validate_not_found(client: AsyncClient, session: AsyncSession, auth_headers):
    resp = await client.post(f"/v4/research/thesis/{uuid.uuid4()}/validate", headers=auth_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_validate_incomplete_thesis(client: AsyncClient, session: AsyncSession, test_user, auth_headers):
    """A thesis whose key_drivers/primary_risks/catalysts don't use the
    real {"items": [...]} convention has driver/risk/catalyst counts of 0
    and is correctly flagged incomplete, even though the fields themselves
    are non-empty dicts."""
    entity = await _seed_entity(session)
    # _seed_thesis's fixture shapes ({"drivers": [...]}) don't match the
    # real {"items": [...]} convention -- exactly the gap this endpoint
    # should catch, not silently count as populated.
    thesis = await _seed_thesis(session, entity.entity_id, test_user.user_id, version=1)

    resp = await client.post(f"/v4/research/thesis/{thesis.id}/validate", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["driver_count"] == 0
    assert data["risk_count"] == 0
    assert data["catalyst_count"] == 0
    assert data["has_valuation_scenarios"] is False  # missing bull/base/bear sub-keys
    assert data["data_coverage"] == 1.0  # all 6 top-level fields ARE non-empty
    assert data["missing_fields"] == []
    assert "driver(s)" in data["summary"]


@pytest.mark.asyncio
async def test_validate_complete_thesis(client: AsyncClient, session: AsyncSession, test_user, auth_headers):
    """A thesis with real {"items": [...]}-shaped drivers/risks/catalysts
    and a complete valuation is correctly flagged complete."""
    entity = await _seed_entity(session)
    thesis = InvestmentThesis(
        id=uuid.uuid4(),
        entity_id=entity.entity_id,
        analyst_id=test_user.user_id,
        version=1,
        thesis_title="Complete Thesis",
        investment_horizon="12M",
        conviction_level="HIGH",
        executive_summary="A real summary.",
        key_drivers={"items": [{"driver": "Cloud growth", "current_impact": "HIGH"}]},
        primary_risks={"items": [{"risk": "Competition", "severity": "MODERATE"}]},
        valuation_scenarios={
            "current_price": 100.0,
            "bull": {"target_price": 140.0, "implied_return": 40.0},
            "base": {"target_price": 120.0, "implied_return": 20.0},
            "bear": {"target_price": 80.0, "implied_return": -20.0},
        },
        catalysts={"items": [{"description": "Q3 earnings"}]},
        ai_enabled=False,
    )
    session.add(thesis)
    await session.flush()

    resp = await client.post(f"/v4/research/thesis/{thesis.id}/validate", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_complete"] is True
    assert data["data_coverage"] == 1.0
    assert data["missing_fields"] == []
    assert data["driver_count"] == 1
    assert data["risk_count"] == 1
    assert data["catalyst_count"] == 1
    assert data["has_valuation_scenarios"] is True
    assert data["staleness_days"] == 0


@pytest.mark.asyncio
async def test_validate_missing_fields_reported(client: AsyncClient, session: AsyncSession, test_user, auth_headers):
    """A thesis missing required top-level fields reports them by name and
    is flagged incomplete."""
    entity = await _seed_entity(session)
    thesis = InvestmentThesis(
        id=uuid.uuid4(),
        entity_id=entity.entity_id,
        analyst_id=test_user.user_id,
        version=1,
        thesis_title="Sparse Thesis",
        ai_enabled=False,
    )
    session.add(thesis)
    await session.flush()

    resp = await client.post(f"/v4/research/thesis/{thesis.id}/validate", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_complete"] is False
    assert "executive_summary" in data["missing_fields"]
    assert "key_drivers" in data["missing_fields"]
    assert data["data_coverage"] < 1.0
