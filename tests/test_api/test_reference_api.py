"""Tests for reference data API endpoints."""

import pytest


@pytest.mark.asyncio
async def test_health_check(client):
    """Test the health check endpoint."""
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


@pytest.mark.asyncio
async def test_list_countries_empty(client):
    """Test listing countries when DB is empty."""
    response = await client.get("/v1/reference/countries")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_get_country_not_found(client):
    """Test getting a non-existent country returns 404."""
    response = await client.get("/v1/reference/countries/ZZ")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_list_currencies_empty(client):
    """Test listing currencies when DB is empty."""
    response = await client.get("/v1/reference/currencies")
    assert response.status_code == 200
