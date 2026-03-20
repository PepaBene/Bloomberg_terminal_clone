"""Tests for Scenario & Sensitivity models (E8)."""

import uuid
from datetime import date, datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.entity import Entity
from src.models.scenario import ScenarioResult
from src.models.security import Security


@pytest.fixture
def _entity_security():
    """Return (entity, security) pair for test seeding."""
    now = datetime.now(timezone.utc)
    entity = Entity(
        entity_id=uuid.uuid4(),
        entity_type="PUBLIC_COMPANY",
        legal_name="Scenario Model Corp",
        status="ACTIVE",
        source="TEST",
        created_at=now,
        updated_at=now,
    )
    security = Security(
        security_id=uuid.uuid4(),
        name="Scenario Model Corp Stock",
        short_name="SCNM",
        security_type="COMMON_STOCK",
        asset_class="EQUITY",
        status="ACTIVE",
        issuer_entity_id=entity.entity_id,
        created_at=now,
        updated_at=now,
    )
    return entity, security


@pytest.mark.asyncio
async def test_scenario_result_crud(session: AsyncSession, _entity_security):
    """Create and read back a ScenarioResult."""
    entity, security = _entity_security
    session.add(entity)
    await session.flush()
    session.add(security)
    await session.flush()

    row = ScenarioResult(
        security_id=security.security_id,
        entity_id=entity.entity_id,
        calculation_date=date.today(),
        scenario_type="SENSITIVITY_2D",
        scenario_name="WACC vs Growth",
        input_params={"row_variable": "discount_rate", "col_variable": "terminal_growth"},
        output_data={"grid": [[1.0, 2.0], [3.0, 4.0]]},
        base_case_value=42.0,
        min_value=30.0,
        max_value=55.0,
        data_quality="COMPLETE",
    )
    session.add(row)
    await session.flush()

    result = await session.execute(
        select(ScenarioResult).where(ScenarioResult.scenario_id == row.scenario_id)
    )
    fetched = result.scalar_one()
    assert fetched.scenario_type == "SENSITIVITY_2D"
    assert fetched.scenario_name == "WACC vs Growth"
    assert float(fetched.base_case_value) == pytest.approx(42.0)
    assert fetched.output_data["grid"] == [[1.0, 2.0], [3.0, 4.0]]


@pytest.mark.asyncio
async def test_scenario_result_jsonb_roundtrip(session: AsyncSession, _entity_security):
    """JSONB fields round-trip correctly."""
    entity, security = _entity_security
    session.add(entity)
    await session.flush()
    session.add(security)
    await session.flush()

    complex_input = {
        "variables": ["discount_rate", "ebit_margin"],
        "ranges": {"discount_rate": [0.08, 0.12], "ebit_margin": [0.10, 0.20]},
        "steps": 7,
    }
    complex_output = {
        "bars": [
            {"variable": "discount_rate", "impact": 15.0},
            {"variable": "ebit_margin", "impact": 8.5},
        ]
    }

    row = ScenarioResult(
        security_id=security.security_id,
        calculation_date=date.today(),
        scenario_type="TORNADO",
        input_params=complex_input,
        output_data=complex_output,
        data_quality="COMPLETE",
    )
    session.add(row)
    await session.flush()

    result = await session.execute(
        select(ScenarioResult).where(ScenarioResult.scenario_id == row.scenario_id)
    )
    fetched = result.scalar_one()
    assert fetched.input_params == complex_input
    assert fetched.output_data == complex_output


@pytest.mark.asyncio
async def test_scenario_result_defaults(session: AsyncSession, _entity_security):
    """Default data_quality is COMPLETE, nullable fields are None."""
    entity, security = _entity_security
    session.add(entity)
    await session.flush()
    session.add(security)
    await session.flush()

    row = ScenarioResult(
        security_id=security.security_id,
        calculation_date=date.today(),
        scenario_type="SHOCK",
        input_params={"shock": {}},
        output_data={"result": 0},
    )
    session.add(row)
    await session.flush()

    result = await session.execute(
        select(ScenarioResult).where(ScenarioResult.scenario_id == row.scenario_id)
    )
    fetched = result.scalar_one()
    assert fetched.data_quality == "COMPLETE"
    assert fetched.entity_id is None
    assert fetched.base_case_value is None
    assert fetched.scenario_name is None
