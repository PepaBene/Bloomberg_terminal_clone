"""Tests for entity API endpoints."""

import pytest


@pytest.mark.asyncio
async def test_list_entities_empty(client):
    """Test listing entities when DB is empty."""
    response = await client.get("/v1/entities")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_search_entities_empty(client):
    """Test searching entities when DB is empty."""
    response = await client.get("/v1/entities/search?q=Apple")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_get_entity_not_found(client):
    """Test getting a non-existent entity returns 404."""
    fake_id = "00000000-0000-0000-0000-000000000000"
    response = await client.get(f"/v1/entities/{fake_id}")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_resolve_entity(client):
    """Test entity resolution endpoint."""
    response = await client.post(
        "/v1/entities/resolve",
        json={"legal_name": "Apple Inc", "country": "US"},
    )
    # Should work even with empty DB — returns NEW status
    assert response.status_code == 200
