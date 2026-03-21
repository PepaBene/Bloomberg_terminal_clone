"""Tests for Fund Holdings API endpoints."""

import uuid
from datetime import date

import pytest

from src.models.fund_holdings import Fund, FundHolding


@pytest.mark.asyncio
async def test_list_funds_empty(client):
    """Test listing funds when DB is empty."""
    response = await client.get("/v1/funds")
    assert response.status_code == 200
    data = response.json()
    assert data["data"] == []


@pytest.mark.asyncio
async def test_list_funds(client, session):
    """Test listing funds."""
    for i, (name, ftype) in enumerate([
        ("SPY ETF", "ETF"), ("Fidelity Growth", "MUTUAL_FUND"), ("QQQ ETF", "ETF"),
    ]):
        session.add(Fund(fund_id=uuid.uuid4(), fund_name=name, fund_type=ftype))
    await session.flush()

    response = await client.get("/v1/funds")
    assert response.status_code == 200
    data = response.json()
    assert data["meta"]["total_count"] == 3


@pytest.mark.asyncio
async def test_list_funds_filter_type(client, session):
    """Test filtering funds by type."""
    session.add(Fund(fund_id=uuid.uuid4(), fund_name="ETF 1", fund_type="ETF"))
    session.add(Fund(fund_id=uuid.uuid4(), fund_name="MF 1", fund_type="MUTUAL_FUND"))
    await session.flush()

    response = await client.get("/v1/funds", params={"fund_type": "ETF"})
    assert response.status_code == 200
    data = response.json()
    assert data["meta"]["total_count"] == 1


@pytest.mark.asyncio
async def test_get_fund_not_found(client):
    """Test 404 for non-existent fund."""
    fake_id = "00000000-0000-0000-0000-000000000000"
    response = await client.get(f"/v1/funds/{fake_id}")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_fund(client, session):
    """Test fetching a single fund."""
    fund_id = uuid.uuid4()
    session.add(Fund(
        fund_id=fund_id, fund_name="Test ETF",
        fund_ticker="TEST", fund_type="ETF",
        total_net_assets=1000000000.00,
    ))
    await session.flush()

    response = await client.get(f"/v1/funds/{fund_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["fund_name"] == "Test ETF"


@pytest.mark.asyncio
async def test_list_fund_holdings_empty(client):
    """Test listing holdings for a non-existent fund."""
    fake_id = "00000000-0000-0000-0000-000000000000"
    response = await client.get(f"/v1/funds/{fake_id}/holdings")
    assert response.status_code == 200
    data = response.json()
    assert data["data"] == []


@pytest.mark.asyncio
async def test_list_fund_holdings(client, session):
    """Test listing fund holdings."""
    fund_id = uuid.uuid4()
    session.add(Fund(fund_id=fund_id, fund_name="Holdings ETF", fund_type="ETF"))
    await session.flush()

    for name in ["Apple Inc.", "Microsoft Corp."]:
        session.add(FundHolding(
            holding_id=uuid.uuid4(), fund_id=fund_id,
            report_date=date(2025, 12, 31),
            security_name=name, pct_of_nav=0.05,
            asset_type="EQUITY",
        ))
    await session.flush()

    response = await client.get(f"/v1/funds/{fund_id}/holdings")
    assert response.status_code == 200
    data = response.json()
    assert data["meta"]["total_count"] == 2


@pytest.mark.asyncio
async def test_fund_holders_empty(client):
    """Test fund holders for a non-existent security."""
    fake_id = "00000000-0000-0000-0000-000000000000"
    response = await client.get(f"/v1/securities/{fake_id}/fund-holders")
    assert response.status_code == 200
    data = response.json()
    assert data["data"] == []
