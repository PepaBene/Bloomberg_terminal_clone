"""Tests for M&A Deals API endpoints."""

import uuid
from datetime import date

import pytest

from src.models.entity import Entity
from src.models.ma_deals import MandADeal


@pytest.mark.asyncio
async def test_list_deals_empty(client):
    """Test listing deals when DB is empty."""
    response = await client.get("/v1/deals")
    assert response.status_code == 200
    data = response.json()
    assert data["data"] == []


@pytest.mark.asyncio
async def test_list_deals(client, session):
    """Test listing M&A deals."""
    for i in range(3):
        session.add(MandADeal(
            deal_id=uuid.uuid4(),
            deal_type="ACQUISITION",
            deal_status="COMPLETED",
            total_value=1000000000.00 * (i + 1),
            announcement_date=date(2026, 1 + i, 15),
        ))
    await session.flush()

    response = await client.get("/v1/deals")
    assert response.status_code == 200
    data = response.json()
    assert data["meta"]["total_count"] == 3


@pytest.mark.asyncio
async def test_list_deals_filter_status(client, session):
    """Test filtering deals by status."""
    session.add(MandADeal(
        deal_id=uuid.uuid4(), deal_status="PENDING",
        announcement_date=date(2026, 3, 1),
    ))
    session.add(MandADeal(
        deal_id=uuid.uuid4(), deal_status="COMPLETED",
        announcement_date=date(2026, 2, 1),
    ))
    await session.flush()

    response = await client.get("/v1/deals", params={"status": "PENDING"})
    assert response.status_code == 200
    data = response.json()
    assert data["meta"]["total_count"] == 1
    assert data["data"][0]["deal_status"] == "PENDING"


@pytest.mark.asyncio
async def test_get_deal_not_found(client):
    """Test 404 for non-existent deal."""
    fake_id = "00000000-0000-0000-0000-000000000000"
    response = await client.get(f"/v1/deals/{fake_id}")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_deal(client, session):
    """Test fetching a single deal."""
    deal_id = uuid.uuid4()
    session.add(MandADeal(
        deal_id=deal_id,
        acquirer_name="Big Corp",
        target_name="Small Corp",
        deal_type="ACQUISITION",
        deal_status="PENDING",
        total_value=5000000000.00,
        ev_to_ebitda=15.2,
    ))
    await session.flush()

    response = await client.get(f"/v1/deals/{deal_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["acquirer_name"] == "Big Corp"
    assert data["total_value"] == 5000000000.00


@pytest.mark.asyncio
async def test_deal_statistics_empty(client):
    """Test deal statistics with no data."""
    response = await client.get("/v1/deals/statistics")
    assert response.status_code == 200
    data = response.json()
    assert data["total_deals"] == 0


@pytest.mark.asyncio
async def test_deal_statistics(client, session):
    """Test deal statistics aggregation."""
    session.add(MandADeal(
        deal_id=uuid.uuid4(), total_value=10000000000.00,
        ev_to_ebitda=12.0, premium_to_undisturbed=0.25,
        announcement_date=date(2026, 1, 15),
    ))
    session.add(MandADeal(
        deal_id=uuid.uuid4(), total_value=5000000000.00,
        ev_to_ebitda=10.0, premium_to_undisturbed=0.30,
        announcement_date=date(2026, 2, 15),
    ))
    await session.flush()

    response = await client.get("/v1/deals/statistics")
    assert response.status_code == 200
    data = response.json()
    assert data["total_deals"] == 2
    assert data["total_value"] == 15000000000.00


@pytest.mark.asyncio
async def test_entity_deals(client, session):
    """Test listing deals for a specific entity."""
    entity_id = uuid.uuid4()
    session.add(Entity(
        entity_id=entity_id, entity_type="PUBLIC_COMPANY",
        legal_name="Deal Entity", status="ACTIVE", source="SEC_EDGAR",
    ))
    await session.flush()

    session.add(MandADeal(
        deal_id=uuid.uuid4(), acquirer_entity_id=entity_id,
        deal_status="COMPLETED", announcement_date=date(2026, 1, 1),
    ))
    session.add(MandADeal(
        deal_id=uuid.uuid4(), target_entity_id=entity_id,
        deal_status="PENDING", announcement_date=date(2026, 2, 1),
    ))
    await session.flush()

    response = await client.get(f"/v1/entities/{entity_id}/deals")
    assert response.status_code == 200
    data = response.json()
    assert data["meta"]["total_count"] == 2
