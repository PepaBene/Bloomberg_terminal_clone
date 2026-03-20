"""Tests for business relationships API endpoints."""

import uuid

import pytest


@pytest.mark.asyncio
async def test_list_relationships_empty(client):
    """Test listing relationships for an entity with no data."""
    entity_id = uuid.uuid4()
    response = await client.get(f"/v1/entities/{entity_id}/business-relationships")
    assert response.status_code == 200
    data = response.json()
    assert data["data"] == []
    assert data["meta"]["total_count"] == 0


@pytest.mark.asyncio
async def test_list_customers_empty(client):
    """Test listing customer relationships when empty."""
    entity_id = uuid.uuid4()
    response = await client.get(f"/v1/entities/{entity_id}/business-relationships/customers")
    assert response.status_code == 200
    data = response.json()
    assert data["data"] == []


@pytest.mark.asyncio
async def test_list_suppliers_empty(client):
    """Test listing supplier relationships when empty."""
    entity_id = uuid.uuid4()
    response = await client.get(f"/v1/entities/{entity_id}/business-relationships/suppliers")
    assert response.status_code == 200
    data = response.json()
    assert data["data"] == []


@pytest.mark.asyncio
async def test_list_competitors_empty(client):
    """Test listing competitor relationships when empty."""
    entity_id = uuid.uuid4()
    response = await client.get(f"/v1/entities/{entity_id}/business-relationships/competitors")
    assert response.status_code == 200
    data = response.json()
    assert data["data"] == []


@pytest.mark.asyncio
async def test_get_relationship_not_found(client):
    """Test getting a non-existent relationship returns 404."""
    fake_id = uuid.uuid4()
    response = await client.get(f"/v1/business-relationships/{fake_id}")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_relationship_history_not_found(client):
    """Test getting history for a non-existent relationship returns 404."""
    fake_id = uuid.uuid4()
    response = await client.get(f"/v1/business-relationships/{fake_id}/history")
    assert response.status_code == 404
