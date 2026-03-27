"""Tests for Pillar 3 Phase 4C: Macro Theme & Scenario models."""

import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from src.models.entity import Entity
from src.models.macro_themes import MacroThemeScore, MacroScenario
from src.models.scenario_impact import ScenarioCompanyImpact


# ── Helpers ──────────────────────────────────────────────────────────


async def _seed_entity(session, entity_id=None):
    eid = entity_id or uuid.uuid4()
    entity = Entity(
        entity_id=eid,
        entity_type="PUBLIC_COMPANY",
        legal_name="Theme Test Corp",
        status="ACTIVE",
        source="SEC_EDGAR",
    )
    session.add(entity)
    await session.flush()
    return entity


async def _seed_scenario(session, name="Base Case", scenario_type="SYSTEM"):
    sid = uuid.uuid4()
    scenario = MacroScenario(
        id=sid,
        scenario_name=name,
        scenario_type=scenario_type,
        description="A test scenario for unit testing.",
        assumptions={"rate_hike_bps": 50, "gdp_growth": 2.1},
        created_by="test_user",
    )
    session.add(scenario)
    await session.flush()
    return scenario


# ── MacroThemeScore Tests ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_theme_score(session):
    """Create a macro theme score with all fields."""
    entity = await _seed_entity(session)
    tid = uuid.uuid4()
    score = MacroThemeScore(
        id=tid,
        entity_id=entity.entity_id,
        theme="INFLATION",
        exposure_score=Decimal("72.50"),
        sensitivity_direction="NEGATIVE",
        evidence={"source": "revenue_breakdown", "pct_exposed": 45},
        quantified_exposure="45% of revenue from inflation-sensitive segments",
        as_of_date=date(2025, 6, 1),
    )
    session.add(score)
    await session.flush()

    result = await session.execute(
        select(MacroThemeScore).where(MacroThemeScore.id == tid)
    )
    fetched = result.scalar_one()
    assert fetched.entity_id == entity.entity_id
    assert fetched.theme == "INFLATION"
    assert fetched.exposure_score == Decimal("72.50")
    assert fetched.sensitivity_direction == "NEGATIVE"
    assert fetched.evidence["pct_exposed"] == 45
    assert fetched.as_of_date == date(2025, 6, 1)


@pytest.mark.asyncio
async def test_theme_score_minimal_fields(session):
    """Create a theme score with only required fields."""
    entity = await _seed_entity(session)
    tid = uuid.uuid4()
    score = MacroThemeScore(
        id=tid,
        entity_id=entity.entity_id,
        theme="AI_DISRUPTION",
        as_of_date=date(2025, 7, 1),
    )
    session.add(score)
    await session.flush()

    result = await session.execute(
        select(MacroThemeScore).where(MacroThemeScore.id == tid)
    )
    fetched = result.scalar_one()
    assert fetched.theme == "AI_DISRUPTION"
    assert fetched.exposure_score is None
    assert fetched.sensitivity_direction is None


@pytest.mark.asyncio
async def test_multiple_themes_per_entity(session):
    """An entity can have multiple theme scores."""
    entity = await _seed_entity(session)
    themes = ["INFLATION", "RATES", "GEOPOLITICAL"]
    ids = []
    for theme in themes:
        tid = uuid.uuid4()
        ids.append(tid)
        session.add(MacroThemeScore(
            id=tid,
            entity_id=entity.entity_id,
            theme=theme,
            exposure_score=Decimal("50.00"),
            as_of_date=date(2025, 6, 1),
        ))
    await session.flush()

    result = await session.execute(
        select(MacroThemeScore).where(MacroThemeScore.entity_id == entity.entity_id)
    )
    rows = result.scalars().all()
    assert len(rows) >= 3
    fetched_themes = {r.theme for r in rows}
    assert fetched_themes >= {"INFLATION", "RATES", "GEOPOLITICAL"}


@pytest.mark.asyncio
async def test_theme_score_evidence_jsonb(session):
    """Round-trip JSONB evidence field."""
    entity = await _seed_entity(session)
    tid = uuid.uuid4()
    evidence = {
        "revenue_segments": [
            {"name": "Cloud", "pct": 60, "sensitivity": "HIGH"},
            {"name": "Hardware", "pct": 40, "sensitivity": "LOW"},
        ],
        "confidence": 0.85,
    }
    session.add(MacroThemeScore(
        id=tid,
        entity_id=entity.entity_id,
        theme="CLOUD_ADOPTION",
        evidence=evidence,
        as_of_date=date(2025, 8, 1),
    ))
    await session.flush()

    result = await session.execute(
        select(MacroThemeScore).where(MacroThemeScore.id == tid)
    )
    fetched = result.scalar_one()
    assert fetched.evidence["confidence"] == 0.85
    assert len(fetched.evidence["revenue_segments"]) == 2


# ── MacroScenario Tests ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_scenario(session):
    """Create a macro scenario with all fields."""
    sid = uuid.uuid4()
    scenario = MacroScenario(
        id=sid,
        scenario_name="Rate Hike Shock",
        scenario_type="STRESS_TEST",
        description="Simulate impact of 200bps Fed rate hike.",
        assumptions={"fed_funds_rate_change_bps": 200, "timeline_months": 12},
        created_by="analyst_001",
    )
    session.add(scenario)
    await session.flush()

    result = await session.execute(
        select(MacroScenario).where(MacroScenario.id == sid)
    )
    fetched = result.scalar_one()
    assert fetched.scenario_name == "Rate Hike Shock"
    assert fetched.scenario_type == "STRESS_TEST"
    assert fetched.assumptions["fed_funds_rate_change_bps"] == 200
    assert fetched.created_by == "analyst_001"


@pytest.mark.asyncio
async def test_scenario_default_active(session):
    """Scenario defaults to is_active=True."""
    scenario = await _seed_scenario(session)
    result = await session.execute(
        select(MacroScenario).where(MacroScenario.id == scenario.id)
    )
    fetched = result.scalar_one()
    assert fetched.is_active is True


@pytest.mark.asyncio
async def test_scenario_custom_type(session):
    """Custom scenario type is persisted."""
    scenario = await _seed_scenario(session, name="Custom Recession", scenario_type="CUSTOM")
    result = await session.execute(
        select(MacroScenario).where(MacroScenario.id == scenario.id)
    )
    fetched = result.scalar_one()
    assert fetched.scenario_type == "CUSTOM"
    assert fetched.scenario_name == "Custom Recession"


# ── ScenarioCompanyImpact Tests ─────────────────────────────────────


@pytest.mark.asyncio
async def test_create_scenario_impact(session):
    """Create a scenario company impact with all fields."""
    entity = await _seed_entity(session)
    scenario = await _seed_scenario(session)
    iid = uuid.uuid4()
    impact = ScenarioCompanyImpact(
        id=iid,
        scenario_id=scenario.id,
        entity_id=entity.entity_id,
        base_eps=Decimal("5.20"),
        scenario_eps=Decimal("3.80"),
        eps_change_pct=Decimal("-26.92"),
        margin_impact_bps=Decimal("-150.00"),
        rating_implication="DOWNGRADE",
        price_target_scenario=Decimal("120.00"),
        narrative="Material impact from rate sensitivity in variable-rate debt portfolio.",
    )
    session.add(impact)
    await session.flush()

    result = await session.execute(
        select(ScenarioCompanyImpact).where(ScenarioCompanyImpact.id == iid)
    )
    fetched = result.scalar_one()
    assert fetched.scenario_id == scenario.id
    assert fetched.entity_id == entity.entity_id
    assert fetched.base_eps == Decimal("5.20")
    assert fetched.scenario_eps == Decimal("3.80")
    assert fetched.eps_change_pct == Decimal("-26.92")
    assert fetched.margin_impact_bps == Decimal("-150.00")
    assert fetched.rating_implication == "DOWNGRADE"
    assert fetched.price_target_scenario == Decimal("120.00")


@pytest.mark.asyncio
async def test_multiple_impacts_per_scenario(session):
    """A scenario can have impacts for multiple entities."""
    entity1 = await _seed_entity(session)
    entity2 = await _seed_entity(session)
    scenario = await _seed_scenario(session, name="Multi Impact")
    ids = []
    for eid in [entity1.entity_id, entity2.entity_id]:
        iid = uuid.uuid4()
        ids.append(iid)
        session.add(ScenarioCompanyImpact(
            id=iid,
            scenario_id=scenario.id,
            entity_id=eid,
            base_eps=Decimal("4.00"),
            scenario_eps=Decimal("3.50"),
        ))
    await session.flush()

    result = await session.execute(
        select(ScenarioCompanyImpact)
        .where(ScenarioCompanyImpact.scenario_id == scenario.id)
    )
    rows = result.scalars().all()
    assert len(rows) >= 2


@pytest.mark.asyncio
async def test_scenario_impact_minimal_fields(session):
    """Create scenario impact with only required fields."""
    entity = await _seed_entity(session)
    scenario = await _seed_scenario(session, name="Minimal")
    iid = uuid.uuid4()
    impact = ScenarioCompanyImpact(
        id=iid,
        scenario_id=scenario.id,
        entity_id=entity.entity_id,
    )
    session.add(impact)
    await session.flush()

    result = await session.execute(
        select(ScenarioCompanyImpact).where(ScenarioCompanyImpact.id == iid)
    )
    fetched = result.scalar_one()
    assert fetched.base_eps is None
    assert fetched.scenario_eps is None
    assert fetched.narrative is None
