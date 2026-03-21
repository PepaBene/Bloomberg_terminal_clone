"""Tests for ESG Temperature Scoring API endpoints."""

import uuid
from datetime import date

import pytest

from src.models.entity import Entity
from src.models.esg_temperature import ESGTemperatureScore


@pytest.mark.asyncio
async def test_list_esg_temperature_empty(client):
    """Test listing ESG temperature for a non-existent entity."""
    fake_id = "00000000-0000-0000-0000-000000000000"
    response = await client.get(f"/v1/entities/{fake_id}/esg-temperature")
    assert response.status_code == 200
    assert response.json()["data"] == []


@pytest.mark.asyncio
async def test_list_esg_temperature(client, session):
    """Test listing ESG temperature scores."""
    entity_id = uuid.uuid4()
    session.add(Entity(
        entity_id=entity_id, entity_type="PUBLIC_COMPANY",
        legal_name="Temp Corp", status="ACTIVE", source="SEC_EDGAR",
    ))
    await session.flush()

    for year in [2024, 2025, 2026]:
        session.add(ESGTemperatureScore(
            id=uuid.uuid4(), entity_id=entity_id,
            as_of_date=date(year, 1, 1),
            implied_temperature=2.0, alignment="BETWEEN_1_5_AND_2C",
        ))
    await session.flush()

    response = await client.get(f"/v1/entities/{entity_id}/esg-temperature")
    assert response.status_code == 200
    data = response.json()
    assert data["meta"]["total_count"] == 3


@pytest.mark.asyncio
async def test_list_esg_temperature_filter_alignment(client, session):
    """Test filtering ESG temperature by alignment bucket."""
    entity_id = uuid.uuid4()
    session.add(Entity(
        entity_id=entity_id, entity_type="PUBLIC_COMPANY",
        legal_name="Filter Temp Corp", status="ACTIVE", source="SEC_EDGAR",
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

    response = await client.get(
        f"/v1/entities/{entity_id}/esg-temperature",
        params={"alignment": "BELOW_1_5C"},
    )
    assert response.status_code == 200
    assert response.json()["meta"]["total_count"] == 1


@pytest.mark.asyncio
async def test_esg_temperature_response_fields(client, session):
    """Test that response includes all expected fields."""
    entity_id = uuid.uuid4()
    session.add(Entity(
        entity_id=entity_id, entity_type="PUBLIC_COMPANY",
        legal_name="Field Corp", status="ACTIVE", source="SEC_EDGAR",
    ))
    await session.flush()

    session.add(ESGTemperatureScore(
        id=uuid.uuid4(), entity_id=entity_id,
        as_of_date=date(2026, 1, 1),
        implied_temperature=1.80,
        alignment="BETWEEN_1_5_AND_2C",
        scope1_emissions=50000.00,
        scope2_emissions=20000.00,
        emissions_trend_pct=-3.5,
        data_quality_flag="PARTIAL",
    ))
    await session.flush()

    response = await client.get(f"/v1/entities/{entity_id}/esg-temperature")
    assert response.status_code == 200
    item = response.json()["data"][0]
    assert "implied_temperature" in item
    assert "alignment" in item
    assert "data_quality_flag" in item
