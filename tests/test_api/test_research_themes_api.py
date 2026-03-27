"""API tests for Macro Themes & Scenarios endpoints (Pillar 3 Phase 4C)."""

import uuid
from datetime import date
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.entity import Entity
from src.models.macro_themes import MacroThemeScore, MacroScenario
from src.models.scenario_impact import ScenarioCompanyImpact


# ── Helpers ──────────────────────────────────────────────────────────


async def _seed_entity(session, entity_id=None):
    eid = entity_id or uuid.uuid4()
    entity = Entity(
        entity_id=eid,
        entity_type="PUBLIC_COMPANY",
        legal_name="Theme API Test Corp",
        status="ACTIVE",
        source="SEC_EDGAR",
    )
    session.add(entity)
    await session.flush()
    return entity


async def _seed_theme_score(session, entity_id, theme="INFLATION",
                            exposure=Decimal("65.00"), as_of=None):
    tid = uuid.uuid4()
    score = MacroThemeScore(
        id=tid,
        entity_id=entity_id,
        theme=theme,
        exposure_score=exposure,
        sensitivity_direction="NEGATIVE",
        evidence={"source": "model"},
        quantified_exposure="65% exposure to inflation-sensitive revenue",
        as_of_date=as_of or date(2025, 6, 1),
    )
    session.add(score)
    await session.flush()
    return score


async def _seed_scenario(session, name="Test Scenario", scenario_type="SYSTEM"):
    sid = uuid.uuid4()
    scenario = MacroScenario(
        id=sid,
        scenario_name=name,
        scenario_type=scenario_type,
        description="Test scenario for API tests.",
        assumptions={"rate_change_bps": 100},
        created_by="test_user",
    )
    session.add(scenario)
    await session.flush()
    return scenario


async def _seed_impact(session, scenario_id, entity_id):
    iid = uuid.uuid4()
    impact = ScenarioCompanyImpact(
        id=iid,
        scenario_id=scenario_id,
        entity_id=entity_id,
        base_eps=Decimal("5.00"),
        scenario_eps=Decimal("4.00"),
        eps_change_pct=Decimal("-20.00"),
        margin_impact_bps=Decimal("-100.00"),
        rating_implication="HOLD",
        price_target_scenario=Decimal("130.00"),
        narrative="Moderate impact from rate changes.",
    )
    session.add(impact)
    await session.flush()
    return impact


# ── GET /research/themes/dashboard ──────────────────────────────────


@pytest.mark.asyncio
async def test_themes_dashboard_empty(client: AsyncClient, session: AsyncSession):
    """GET /v4/research/themes/dashboard returns empty list when no data."""
    resp = await client.get("/v4/research/themes/dashboard")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_themes_dashboard_with_data(client: AsyncClient, session: AsyncSession):
    """GET /v4/research/themes/dashboard returns theme scores."""
    entity = await _seed_entity(session)
    await _seed_theme_score(session, entity.entity_id, theme="INFLATION")
    await _seed_theme_score(session, entity.entity_id, theme="RATES")
    resp = await client.get("/v4/research/themes/dashboard")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 2


@pytest.mark.asyncio
async def test_themes_dashboard_limit(client: AsyncClient, session: AsyncSession):
    """GET /v4/research/themes/dashboard respects limit parameter."""
    entity = await _seed_entity(session)
    await _seed_theme_score(session, entity.entity_id, theme="T1")
    await _seed_theme_score(session, entity.entity_id, theme="T2")
    resp = await client.get("/v4/research/themes/dashboard", params={"limit": 1})
    assert resp.status_code == 200
    assert len(resp.json()) == 1


# ── GET /research/themes/{entity_id} ───────────────────────────────


@pytest.mark.asyncio
async def test_entity_theme_exposures_empty(client: AsyncClient, session: AsyncSession):
    """GET /v4/research/themes/{entity_id} returns empty for entity with no themes."""
    resp = await client.get(f"/v4/research/themes/{uuid.uuid4()}")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_entity_theme_exposures_with_data(client: AsyncClient, session: AsyncSession):
    """GET /v4/research/themes/{entity_id} returns entity theme scores."""
    entity = await _seed_entity(session)
    await _seed_theme_score(session, entity.entity_id, theme="INFLATION")
    resp = await client.get(f"/v4/research/themes/{entity.entity_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert data[0]["theme"] == "INFLATION"
    assert data[0]["entity_id"] == str(entity.entity_id)


# ── GET /research/themes/{entity_id}/history ────────────────────────


@pytest.mark.asyncio
async def test_theme_history_empty(client: AsyncClient, session: AsyncSession):
    """GET /v4/research/themes/{entity_id}/history returns empty list."""
    resp = await client.get(f"/v4/research/themes/{uuid.uuid4()}/history")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_theme_history_with_data(client: AsyncClient, session: AsyncSession):
    """GET /v4/research/themes/{entity_id}/history returns historical scores."""
    entity = await _seed_entity(session)
    await _seed_theme_score(session, entity.entity_id, theme="RATES", as_of=date(2025, 1, 1))
    await _seed_theme_score(session, entity.entity_id, theme="RATES", as_of=date(2025, 6, 1))
    resp = await client.get(f"/v4/research/themes/{entity.entity_id}/history",
                           params={"theme": "RATES"})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 2


@pytest.mark.asyncio
async def test_theme_history_limit(client: AsyncClient, session: AsyncSession):
    """GET /v4/research/themes/{entity_id}/history respects limit."""
    entity = await _seed_entity(session)
    await _seed_theme_score(session, entity.entity_id, theme="AI", as_of=date(2025, 1, 1))
    await _seed_theme_score(session, entity.entity_id, theme="AI", as_of=date(2025, 2, 1))
    resp = await client.get(f"/v4/research/themes/{entity.entity_id}/history",
                           params={"limit": 1})
    assert resp.status_code == 200
    assert len(resp.json()) == 1


# ── POST /research/themes/screen ────────────────────────────────────


@pytest.mark.asyncio
async def test_theme_screen_empty(client: AsyncClient, session: AsyncSession):
    """POST /v4/research/themes/screen returns empty for non-matching theme."""
    resp = await client.post("/v4/research/themes/screen", json={
        "theme": "NONEXISTENT_THEME",
    })
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_theme_screen_with_data(client: AsyncClient, session: AsyncSession):
    """POST /v4/research/themes/screen returns matching entities."""
    entity = await _seed_entity(session)
    await _seed_theme_score(session, entity.entity_id, theme="INFLATION",
                           exposure=Decimal("80.00"))
    resp = await client.post("/v4/research/themes/screen", json={
        "theme": "INFLATION",
        "min_exposure": 50.0,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert data[0]["theme"] == "INFLATION"


@pytest.mark.asyncio
async def test_theme_screen_with_direction_filter(client: AsyncClient, session: AsyncSession):
    """POST /v4/research/themes/screen filters by sensitivity_direction."""
    entity = await _seed_entity(session)
    await _seed_theme_score(session, entity.entity_id, theme="INFLATION")
    resp = await client.post("/v4/research/themes/screen", json={
        "theme": "INFLATION",
        "sensitivity_direction": "NEGATIVE",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1


# ── GET /research/scenarios ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_scenarios_empty(client: AsyncClient, session: AsyncSession):
    """GET /v4/research/scenarios returns empty list when no data."""
    resp = await client.get("/v4/research/scenarios")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_list_scenarios_with_data(client: AsyncClient, session: AsyncSession):
    """GET /v4/research/scenarios returns active scenarios."""
    await _seed_scenario(session, name="Scenario A")
    resp = await client.get("/v4/research/scenarios")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1


# ── POST /research/scenarios/custom ─────────────────────────────────


@pytest.mark.asyncio
async def test_create_custom_scenario(client: AsyncClient, session: AsyncSession):
    """POST /v4/research/scenarios/custom creates a new scenario."""
    resp = await client.post("/v4/research/scenarios/custom", json={
        "scenario_name": "Custom Recession",
        "scenario_type": "CUSTOM",
        "description": "Simulating a mild recession scenario.",
        "assumptions": {"gdp_growth": -1.0, "unemployment": 6.0},
        "created_by": "analyst_001",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["scenario_name"] == "Custom Recession"
    assert data["scenario_type"] == "CUSTOM"
    assert data["assumptions"]["gdp_growth"] == -1.0


@pytest.mark.asyncio
async def test_create_custom_scenario_minimal(client: AsyncClient, session: AsyncSession):
    """POST /v4/research/scenarios/custom works with minimal fields."""
    resp = await client.post("/v4/research/scenarios/custom", json={
        "scenario_name": "Minimal Scenario",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["scenario_name"] == "Minimal Scenario"
    assert data["scenario_type"] == "CUSTOM"


# ── GET /research/scenarios/compare ─────────────────────────────────


@pytest.mark.asyncio
async def test_compare_scenarios_empty(client: AsyncClient, session: AsyncSession):
    """GET /v4/research/scenarios/compare returns empty for no matching impacts."""
    sid = uuid.uuid4()
    eid = uuid.uuid4()
    resp = await client.get("/v4/research/scenarios/compare",
                           params={"scenario_ids": str(sid), "entity_id": str(eid)})
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_compare_scenarios_with_data(client: AsyncClient, session: AsyncSession):
    """GET /v4/research/scenarios/compare returns impacts for matching scenarios."""
    entity = await _seed_entity(session)
    sc1 = await _seed_scenario(session, name="Scenario 1")
    sc2 = await _seed_scenario(session, name="Scenario 2")
    await _seed_impact(session, sc1.id, entity.entity_id)
    await _seed_impact(session, sc2.id, entity.entity_id)

    ids_str = f"{sc1.id},{sc2.id}"
    resp = await client.get("/v4/research/scenarios/compare",
                           params={"scenario_ids": ids_str,
                                   "entity_id": str(entity.entity_id)})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 2


# ── GET /research/scenarios/{scenario_id} ───────────────────────────


@pytest.mark.asyncio
async def test_get_scenario_detail_not_found(client: AsyncClient, session: AsyncSession):
    """GET /v4/research/scenarios/{scenario_id} returns 404 for unknown scenario."""
    resp = await client.get(f"/v4/research/scenarios/{uuid.uuid4()}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_scenario_detail(client: AsyncClient, session: AsyncSession):
    """GET /v4/research/scenarios/{scenario_id} returns scenario details."""
    sc = await _seed_scenario(session, name="Detail Test")
    resp = await client.get(f"/v4/research/scenarios/{sc.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["scenario_name"] == "Detail Test"


# ── POST /research/scenarios/{scenario_id}/run ──────────────────────


@pytest.mark.asyncio
async def test_run_scenario_not_found(client: AsyncClient, session: AsyncSession):
    """POST /v4/research/scenarios/{scenario_id}/run returns 404 for unknown scenario."""
    resp = await client.post(f"/v4/research/scenarios/{uuid.uuid4()}/run")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_run_scenario_with_data(client: AsyncClient, session: AsyncSession):
    """POST /v4/research/scenarios/{scenario_id}/run returns cached impacts."""
    entity = await _seed_entity(session)
    sc = await _seed_scenario(session, name="Run Test")
    await _seed_impact(session, sc.id, entity.entity_id)

    resp = await client.post(f"/v4/research/scenarios/{sc.id}/run")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert data[0]["scenario_id"] == str(sc.id)


# ── GET /research/scenarios/{scenario_id}/results ───────────────────


@pytest.mark.asyncio
async def test_scenario_results_empty(client: AsyncClient, session: AsyncSession):
    """GET /v4/research/scenarios/{scenario_id}/results returns empty for no impacts."""
    resp = await client.get(f"/v4/research/scenarios/{uuid.uuid4()}/results")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_scenario_results_with_data(client: AsyncClient, session: AsyncSession):
    """GET /v4/research/scenarios/{scenario_id}/results returns cached results."""
    entity = await _seed_entity(session)
    sc = await _seed_scenario(session, name="Results Test")
    await _seed_impact(session, sc.id, entity.entity_id)

    resp = await client.get(f"/v4/research/scenarios/{sc.id}/results")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert data[0]["base_eps"] == 5.0
    assert data[0]["scenario_eps"] == 4.0
