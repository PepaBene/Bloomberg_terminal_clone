"""Tests for ESG & Sustainability API endpoints."""

import uuid

import pytest


ENTITY_ID = str(uuid.uuid4())


@pytest.mark.asyncio
async def test_esg_overview_empty(client):
    """Test ESG overview for an entity with no data."""
    response = await client.get(f"/v1/entities/{ENTITY_ID}/esg")
    assert response.status_code == 200
    data = response.json()
    assert data["entity_id"] == ENTITY_ID
    assert data["scores"] == []
    assert data["metrics"] == []
    assert data["controversies"] == []


@pytest.mark.asyncio
async def test_esg_scores_empty(client):
    """Test ESG scores for an entity with no data."""
    response = await client.get(f"/v1/entities/{ENTITY_ID}/esg/scores")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_esg_metrics_empty(client):
    """Test ESG metrics for an entity with no data."""
    response = await client.get(f"/v1/entities/{ENTITY_ID}/esg/metrics")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_esg_controversies_empty(client):
    """Test ESG controversies for an entity with no data."""
    response = await client.get(f"/v1/entities/{ENTITY_ID}/esg/controversies")
    assert response.status_code == 200
    assert response.json() == []
