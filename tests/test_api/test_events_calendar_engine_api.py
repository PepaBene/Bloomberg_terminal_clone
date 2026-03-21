"""API tests for events calendar engine endpoints (Pillar 2 Supplement – Part 5)."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_get_events(client: AsyncClient):
    resp = await client.get("/v1/analytics/events")
    assert resp.status_code == 200
    data = resp.json()
    assert "events" in data
    assert "total_events" in data


@pytest.mark.asyncio
async def test_get_events_with_dates(client: AsyncClient):
    resp = await client.get(
        "/v1/analytics/events",
        params={"start": "2024-07-01", "end": "2024-07-31"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["start_date"] == "2024-07-01"
    assert data["end_date"] == "2024-07-31"


@pytest.mark.asyncio
async def test_get_events_summary(client: AsyncClient):
    resp = await client.get("/v1/analytics/events/summary", params={"days": 14})
    assert resp.status_code == 200
    data = resp.json()
    assert data["date_range"] == "next 14 days"
