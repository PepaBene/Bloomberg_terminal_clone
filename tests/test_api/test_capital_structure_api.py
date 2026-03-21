"""Tests for Capital Structure API endpoints."""

import uuid
from datetime import date

import pytest

from src.models.capital_structure import CapitalStructure, DebtTranche
from src.models.entity import Entity


@pytest.mark.asyncio
async def test_get_capital_structure_not_found(client):
    """Test 404 when no capital structure exists for entity."""
    fake_id = "00000000-0000-0000-0000-000000000000"
    response = await client.get(f"/v1/entities/{fake_id}/capital-structure")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_capital_structure(client, session):
    """Test fetching the latest capital structure with tranches."""
    entity_id = uuid.uuid4()
    entity = Entity(
        entity_id=entity_id,
        entity_type="PUBLIC_COMPANY",
        legal_name="API Test Corp",
        status="ACTIVE",
        source="SEC_EDGAR",
    )
    session.add(entity)
    await session.flush()

    cs_id = uuid.uuid4()
    cs = CapitalStructure(
        capital_structure_id=cs_id,
        entity_id=entity_id,
        as_of_date=date(2025, 12, 31),
        total_debt=5000000000.00,
        net_debt=3500000000.00,
        source="SEC_10K",
    )
    session.add(cs)
    await session.flush()

    tranche = DebtTranche(
        tranche_id=uuid.uuid4(),
        entity_id=entity_id,
        capital_structure_id=cs_id,
        instrument_name="4.5% Senior Notes due 2030",
        instrument_type="SENIOR_UNSECURED_NOTES",
        principal_amount=1000000000.00,
        coupon_rate=0.045,
        seniority_rank=1,
    )
    session.add(tranche)
    await session.flush()

    response = await client.get(f"/v1/entities/{entity_id}/capital-structure")
    assert response.status_code == 200
    data = response.json()
    assert data["entity_id"] == str(entity_id)
    assert data["total_debt"] == 5000000000.00
    assert len(data["tranches"]) == 1
    assert data["tranches"][0]["instrument_name"] == "4.5% Senior Notes due 2030"


@pytest.mark.asyncio
async def test_list_tranches_empty(client):
    """Test listing tranches for entity with no data."""
    fake_id = "00000000-0000-0000-0000-000000000000"
    response = await client.get(f"/v1/entities/{fake_id}/capital-structure/tranches")
    assert response.status_code == 200
    data = response.json()
    assert data["data"] == []
    assert data["meta"]["total_count"] == 0


@pytest.mark.asyncio
async def test_list_tranches(client, session):
    """Test listing debt tranches for an entity."""
    entity_id = uuid.uuid4()
    entity = Entity(
        entity_id=entity_id,
        entity_type="PUBLIC_COMPANY",
        legal_name="Tranche API Corp",
        status="ACTIVE",
        source="SEC_EDGAR",
    )
    session.add(entity)
    await session.flush()

    cs_id = uuid.uuid4()
    cs = CapitalStructure(
        capital_structure_id=cs_id,
        entity_id=entity_id,
        as_of_date=date(2025, 12, 31),
    )
    session.add(cs)
    await session.flush()

    for i in range(3):
        session.add(DebtTranche(
            tranche_id=uuid.uuid4(),
            entity_id=entity_id,
            capital_structure_id=cs_id,
            instrument_name=f"Note {i}",
            seniority_rank=i + 1,
        ))
    await session.flush()

    response = await client.get(f"/v1/entities/{entity_id}/capital-structure/tranches")
    assert response.status_code == 200
    data = response.json()
    assert data["meta"]["total_count"] == 3
    assert len(data["data"]) == 3


@pytest.mark.asyncio
async def test_capital_structure_history_empty(client):
    """Test capital structure history when empty."""
    fake_id = "00000000-0000-0000-0000-000000000000"
    response = await client.get(f"/v1/entities/{fake_id}/capital-structure/history")
    assert response.status_code == 200
    data = response.json()
    assert data["data"] == []


@pytest.mark.asyncio
async def test_capital_structure_history(client, session):
    """Test fetching capital structure history with date filters."""
    entity_id = uuid.uuid4()
    entity = Entity(
        entity_id=entity_id,
        entity_type="PUBLIC_COMPANY",
        legal_name="History Corp",
        status="ACTIVE",
        source="SEC_EDGAR",
    )
    session.add(entity)
    await session.flush()

    for quarter_end in [date(2025, 3, 31), date(2025, 6, 30), date(2025, 9, 30), date(2025, 12, 31)]:
        session.add(CapitalStructure(
            capital_structure_id=uuid.uuid4(),
            entity_id=entity_id,
            as_of_date=quarter_end,
            total_debt=4000000000.00,
        ))
    await session.flush()

    response = await client.get(
        f"/v1/entities/{entity_id}/capital-structure/history",
        params={"start": "2025-06-01", "end": "2025-12-31"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["meta"]["total_count"] == 3  # Q2, Q3, Q4


@pytest.mark.asyncio
async def test_capital_structure_summary_not_found(client):
    """Test 404 for summary when no data exists."""
    fake_id = "00000000-0000-0000-0000-000000000000"
    response = await client.get(f"/v1/entities/{fake_id}/capital-structure/summary")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_capital_structure_summary(client, session):
    """Test fetching capital structure summary (no tranches)."""
    entity_id = uuid.uuid4()
    entity = Entity(
        entity_id=entity_id,
        entity_type="PUBLIC_COMPANY",
        legal_name="Summary Corp",
        status="ACTIVE",
        source="SEC_EDGAR",
    )
    session.add(entity)
    await session.flush()

    session.add(CapitalStructure(
        capital_structure_id=uuid.uuid4(),
        entity_id=entity_id,
        as_of_date=date(2025, 12, 31),
        total_debt=5000000000.00,
        net_debt=3500000000.00,
        total_capitalization=12000000000.00,
        debt_to_capitalization=0.4167,
    ))
    await session.flush()

    response = await client.get(f"/v1/entities/{entity_id}/capital-structure/summary")
    assert response.status_code == 200
    data = response.json()
    assert data["entity_id"] == str(entity_id)
    assert data["total_debt"] == 5000000000.00
    assert "tranches" not in data
