"""Tests for security API endpoints."""

import pytest


@pytest.mark.asyncio
async def test_list_securities_empty(client):
    """Test listing securities when DB is empty."""
    response = await client.get("/v1/securities")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_search_securities_empty(client):
    """Test searching securities when DB is empty."""
    response = await client.get("/v1/securities/search?q=AAPL")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_get_security_not_found(client):
    """Test getting a non-existent security returns 404."""
    fake_id = "00000000-0000-0000-0000-000000000000"
    response = await client.get(f"/v1/securities/{fake_id}")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_translate_endpoint(client):
    """Test the identifier translation endpoint — 404 expected with empty DB."""
    response = await client.post(
        "/v1/securities/translate",
        json={
            "source_type": "TICKER",
            "source_value": "AAPL",
            "target_types": ["ISIN", "FIGI"],
        },
    )
    # No data seeded, so identifier not found → 404
    assert response.status_code == 404
