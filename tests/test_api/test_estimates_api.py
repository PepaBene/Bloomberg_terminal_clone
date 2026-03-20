"""Tests for estimates API endpoints."""

import pytest


@pytest.mark.asyncio
async def test_consensus_estimates_empty(client):
    """Test getting consensus estimates for a non-existent security returns empty."""
    fake_id = "00000000-0000-0000-0000-000000000000"
    response = await client.get(f"/v1/securities/{fake_id}/estimates/consensus")
    assert response.status_code == 200
    data = response.json()
    assert data["data"] == []


@pytest.mark.asyncio
async def test_estimate_surprises_not_found(client):
    """Test getting surprises for a non-existent security returns 404."""
    fake_id = "00000000-0000-0000-0000-000000000000"
    response = await client.get(f"/v1/securities/{fake_id}/estimates/surprises")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_guidance_empty(client):
    """Test getting guidance for a non-existent entity returns empty."""
    fake_id = "00000000-0000-0000-0000-000000000000"
    response = await client.get(f"/v1/entities/{fake_id}/guidance")
    assert response.status_code == 200
    data = response.json()
    assert data["data"] == []


@pytest.mark.asyncio
async def test_consensus_with_metric_filter(client):
    """Test consensus endpoint accepts metric filter parameter."""
    fake_id = "00000000-0000-0000-0000-000000000000"
    response = await client.get(
        f"/v1/securities/{fake_id}/estimates/consensus",
        params={"metric": "EPS"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["data"] == []
    assert data["meta"]["total_count"] == 0
