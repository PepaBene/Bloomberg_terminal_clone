"""Tests for ownership API endpoints."""

import uuid

import pytest


@pytest.mark.asyncio
async def test_list_institutions_empty(client):
    """Test listing institutions when DB is empty."""
    response = await client.get("/v1/institutions")
    assert response.status_code == 200
    data = response.json()
    assert data["data"] == []
    assert data["meta"]["total_count"] == 0


@pytest.mark.asyncio
async def test_institutional_holdings_empty(client):
    """Test institutional holdings for a non-existent security returns 404."""
    fake_id = str(uuid.uuid4())
    response = await client.get(f"/v1/securities/{fake_id}/ownership/institutional")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_insider_holdings_empty(client):
    """Test insider holdings for a non-existent security returns 404."""
    fake_id = str(uuid.uuid4())
    response = await client.get(f"/v1/securities/{fake_id}/ownership/insider")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_short_interest_404(client):
    """Test short interest for a non-existent security returns 404."""
    fake_id = str(uuid.uuid4())
    response = await client.get(f"/v1/securities/{fake_id}/short-interest")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_ownership_summary_404(client):
    """Test ownership summary for a non-existent security returns 404."""
    fake_id = str(uuid.uuid4())
    response = await client.get(f"/v1/securities/{fake_id}/ownership/summary")
    assert response.status_code == 404
