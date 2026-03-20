"""Tests for macroeconomic data API endpoints."""

import pytest


@pytest.mark.asyncio
async def test_list_indicators_empty(client):
    """Test listing indicators when DB is empty."""
    response = await client.get("/v1/macro/indicators")
    assert response.status_code == 200
    data = response.json()
    assert data["data"] == []
    assert data["meta"]["total_count"] == 0


@pytest.mark.asyncio
async def test_search_indicators_empty(client):
    """Test searching indicators when DB is empty."""
    response = await client.get("/v1/macro/indicators/search?q=GDP")
    assert response.status_code == 200
    data = response.json()
    assert data["results"] == []
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_get_indicator_not_found(client):
    """Test getting a non-existent indicator returns 404."""
    response = await client.get("/v1/macro/indicators/NONEXISTENT")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_indicator_values_not_found(client):
    """Test getting values for non-existent indicator returns 404."""
    response = await client.get("/v1/macro/indicators/NONEXISTENT/values")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_indicator_latest_not_found(client):
    """Test getting latest value for non-existent indicator returns 404."""
    response = await client.get("/v1/macro/indicators/NONEXISTENT/latest")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_list_central_banks_empty(client):
    """Test listing central banks when DB is empty."""
    response = await client.get("/v1/macro/central-banks")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_get_central_bank_rates_not_found(client):
    """Test getting rates for non-existent bank returns 404."""
    response = await client.get("/v1/macro/central-banks/NONEXIST/rates")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_bulk_macro_data(client):
    """Test bulk macro data endpoint with unknown indicators."""
    response = await client.post(
        "/v1/macro/bulk",
        json={"indicator_codes": ["GDP", "UNRATE"]},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert "GDP" in data
    assert data["GDP"]["error"] == "Indicator 'GDP' not found"
