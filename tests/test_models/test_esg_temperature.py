"""Tests for ESG temperature score models."""

import uuid
from datetime import date

import pytest
from sqlalchemy import select

from src.models.entity import Entity
from src.models.esg_temperature import ESGTemperatureScore


@pytest.mark.asyncio
async def test_create_esg_temperature_score(session):
    """Test creating an ESG temperature score."""
    entity_id = uuid.uuid4()
    session.add(Entity(
        entity_id=entity_id, entity_type="PUBLIC_COMPANY",
        legal_name="Green Corp", status="ACTIVE", source="SEC_EDGAR",
    ))
    await session.flush()

    sid = uuid.uuid4()
    session.add(ESGTemperatureScore(
        id=sid, entity_id=entity_id,
        as_of_date=date(2026, 1, 1),
        implied_temperature=1.80,
        alignment="BETWEEN_1_5_AND_2C",
        scope1_emissions=50000.00,
        scope2_emissions=20000.00,
        scope3_emissions=150000.00,
        emissions_trend_pct=-3.5,
        data_quality_flag="FULL",
    ))
    await session.flush()

    result = await session.execute(
        select(ESGTemperatureScore).where(ESGTemperatureScore.id == sid)
    )
    fetched = result.scalar_one()
    assert float(fetched.implied_temperature) == pytest.approx(1.80, abs=0.01)
    assert fetched.alignment == "BETWEEN_1_5_AND_2C"
    assert fetched.data_quality_flag == "FULL"


@pytest.mark.asyncio
async def test_list_scores_by_entity(session):
    """Test querying temperature scores by entity."""
    entity_id = uuid.uuid4()
    session.add(Entity(
        entity_id=entity_id, entity_type="PUBLIC_COMPANY",
        legal_name="Multi-Year Corp", status="ACTIVE", source="SEC_EDGAR",
    ))
    await session.flush()

    for year in [2024, 2025, 2026]:
        session.add(ESGTemperatureScore(
            id=uuid.uuid4(), entity_id=entity_id,
            as_of_date=date(year, 1, 1),
            implied_temperature=2.0, alignment="BETWEEN_1_5_AND_2C",
        ))
    await session.flush()

    result = await session.execute(
        select(ESGTemperatureScore).where(ESGTemperatureScore.entity_id == entity_id)
    )
    scores = result.scalars().all()
    assert len(scores) == 3


@pytest.mark.asyncio
async def test_filter_by_alignment(session):
    """Test filtering scores by alignment bucket."""
    entity_id = uuid.uuid4()
    session.add(Entity(
        entity_id=entity_id, entity_type="PUBLIC_COMPANY",
        legal_name="Mix Corp", status="ACTIVE", source="SEC_EDGAR",
    ))
    await session.flush()

    session.add(ESGTemperatureScore(
        id=uuid.uuid4(), entity_id=entity_id,
        as_of_date=date(2025, 1, 1),
        implied_temperature=1.3, alignment="BELOW_1_5C",
    ))
    session.add(ESGTemperatureScore(
        id=uuid.uuid4(), entity_id=entity_id,
        as_of_date=date(2026, 1, 1),
        implied_temperature=2.5, alignment="BETWEEN_2_AND_3C",
    ))
    await session.flush()

    result = await session.execute(
        select(ESGTemperatureScore)
        .where(ESGTemperatureScore.entity_id == entity_id)
        .where(ESGTemperatureScore.alignment == "BELOW_1_5C")
    )
    scores = result.scalars().all()
    assert len(scores) == 1
    assert float(scores[0].implied_temperature) == pytest.approx(1.3, abs=0.01)
