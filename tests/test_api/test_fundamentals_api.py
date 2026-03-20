"""Tests for company fundamentals API endpoints."""

import pytest


@pytest.mark.asyncio
async def test_list_filings_empty(client):
    """Test listing filings for a non-existent entity."""
    fake_id = "00000000-0000-0000-0000-000000000000"
    response = await client.get(f"/v1/entities/{fake_id}/filings")
    assert response.status_code == 200
    data = response.json()
    assert data["data"] == []


@pytest.mark.asyncio
async def test_get_filing_not_found(client):
    """Test getting a non-existent filing returns 404."""
    fake_id = "00000000-0000-0000-0000-000000000000"
    response = await client.get(f"/v1/filings/{fake_id}")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_fundamentals_empty(client):
    """Test getting fundamentals for a non-existent entity."""
    fake_id = "00000000-0000-0000-0000-000000000000"
    response = await client.get(f"/v1/entities/{fake_id}/fundamentals")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_get_income_statements_empty(client):
    """Test getting income statements when empty."""
    fake_id = "00000000-0000-0000-0000-000000000000"
    response = await client.get(f"/v1/entities/{fake_id}/fundamentals/income-statement")
    assert response.status_code == 200
    data = response.json()
    assert data["data"] == []


@pytest.mark.asyncio
async def test_get_balance_sheets_empty(client):
    """Test getting balance sheets when empty."""
    fake_id = "00000000-0000-0000-0000-000000000000"
    response = await client.get(f"/v1/entities/{fake_id}/fundamentals/balance-sheet")
    assert response.status_code == 200
    data = response.json()
    assert data["data"] == []


@pytest.mark.asyncio
async def test_get_cash_flows_empty(client):
    """Test getting cash flow statements when empty."""
    fake_id = "00000000-0000-0000-0000-000000000000"
    response = await client.get(f"/v1/entities/{fake_id}/fundamentals/cash-flow")
    assert response.status_code == 200
    data = response.json()
    assert data["data"] == []


@pytest.mark.asyncio
async def test_get_segments_empty(client):
    """Test getting segments when empty."""
    fake_id = "00000000-0000-0000-0000-000000000000"
    response = await client.get(f"/v1/entities/{fake_id}/segments")
    assert response.status_code == 200
    data = response.json()
    assert data["data"] == []
