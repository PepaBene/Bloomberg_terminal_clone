"""Tests for IPO Monitor API endpoints."""

import uuid
from datetime import date

import pytest

from src.models.ipo import IPOEvent


@pytest.mark.asyncio
async def test_list_ipos_empty(client):
    """Test listing IPOs when DB is empty."""
    response = await client.get("/v1/ipos")
    assert response.status_code == 200
    data = response.json()
    assert data["data"] == []


@pytest.mark.asyncio
async def test_list_ipos(client, session):
    """Test listing IPO events."""
    for i in range(3):
        session.add(IPOEvent(
            ipo_id=uuid.uuid4(),
            status="TRADING",
            pricing_date=date(2026, 1 + i, 15),
            offer_price=20.00 + i * 5,
        ))
    await session.flush()

    response = await client.get("/v1/ipos")
    assert response.status_code == 200
    data = response.json()
    assert data["meta"]["total_count"] == 3


@pytest.mark.asyncio
async def test_list_ipos_filter_status(client, session):
    """Test filtering IPOs by status."""
    session.add(IPOEvent(ipo_id=uuid.uuid4(), status="FILED"))
    session.add(IPOEvent(ipo_id=uuid.uuid4(), status="TRADING"))
    await session.flush()

    response = await client.get("/v1/ipos", params={"status": "FILED"})
    assert response.status_code == 200
    data = response.json()
    assert data["meta"]["total_count"] == 1


@pytest.mark.asyncio
async def test_ipo_pipeline(client, session):
    """Test IPO pipeline endpoint."""
    session.add(IPOEvent(ipo_id=uuid.uuid4(), status="FILED", s1_filing_date=date(2026, 3, 1)))
    session.add(IPOEvent(ipo_id=uuid.uuid4(), status="AMENDED", s1_filing_date=date(2026, 3, 5)))
    session.add(IPOEvent(ipo_id=uuid.uuid4(), status="TRADING"))
    await session.flush()

    response = await client.get("/v1/ipos/pipeline")
    assert response.status_code == 200
    data = response.json()
    assert data["meta"]["total_count"] == 2


@pytest.mark.asyncio
async def test_get_ipo_not_found(client):
    """Test 404 for non-existent IPO."""
    fake_id = "00000000-0000-0000-0000-000000000000"
    response = await client.get(f"/v1/ipos/{fake_id}")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_ipo(client, session):
    """Test fetching a single IPO."""
    ipo_id = uuid.uuid4()
    session.add(IPOEvent(
        ipo_id=ipo_id,
        offer_price=25.00,
        first_day_close=32.50,
        first_day_return_pct=0.30,
        status="TRADING",
    ))
    await session.flush()

    response = await client.get(f"/v1/ipos/{ipo_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["offer_price"] == 25.00
    assert data["status"] == "TRADING"
