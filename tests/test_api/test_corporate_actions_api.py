"""Tests for corporate actions API endpoints."""

import pytest


@pytest.mark.asyncio
async def test_list_corporate_actions_empty(client):
    """Test listing corporate actions for a security when DB is empty."""
    fake_id = "00000000-0000-0000-0000-000000000000"
    response = await client.get(f"/v1/securities/{fake_id}/corporate-actions")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_get_corporate_action_not_found(client):
    """Test getting a non-existent corporate action returns 404."""
    fake_id = "00000000-0000-0000-0000-000000000000"
    response = await client.get(f"/v1/corporate-actions/{fake_id}")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_calendar_empty(client):
    """Test corporate actions calendar when DB is empty."""
    response = await client.get("/v1/corporate-actions/calendar")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_dividends_empty(client):
    """Test listing dividends for a security when DB is empty."""
    fake_id = "00000000-0000-0000-0000-000000000000"
    response = await client.get(f"/v1/securities/{fake_id}/dividends")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_splits_empty(client):
    """Test listing splits for a security when DB is empty."""
    fake_id = "00000000-0000-0000-0000-000000000000"
    response = await client.get(f"/v1/securities/{fake_id}/splits")
    assert response.status_code == 200
