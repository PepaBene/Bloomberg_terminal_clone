"""API tests for market movers endpoints (Pillar 2 Supplement – Part 5)."""

import uuid
from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.market_movers import MarketMoversSnapshot


async def _seed_snapshot(
    session: AsyncSession,
    snapshot_date: date,
    category: str,
    rankings: list[dict],
    sector: str | None = None,
):
    snap = MarketMoversSnapshot(
        id=uuid.uuid4(),
        snapshot_date=snapshot_date,
        category=category,
        sector=sector,
        rankings=rankings,
    )
    session.add(snap)
    await session.commit()


SAMPLE_RANKINGS = [
    {"security_id": str(uuid.uuid4()), "name": "Stock A", "ticker": "A", "price": 110.0, "change_pct": 10.0, "volume": 5000},
    {"security_id": str(uuid.uuid4()), "name": "Stock B", "ticker": "B", "price": 95.0, "change_pct": -5.0, "volume": 3000},
]


@pytest.mark.asyncio
async def test_get_movers_empty(client: AsyncClient):
    resp = await client.get("/v1/analytics/movers", params={"category": "TOP_GAINERS"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["category"] == "TOP_GAINERS"
    assert data["movers"] == []


@pytest.mark.asyncio
async def test_get_movers_with_data(client: AsyncClient, session: AsyncSession):
    await _seed_snapshot(session, date(2024, 8, 1), "TOP_GAINERS", SAMPLE_RANKINGS)
    resp = await client.get(
        "/v1/analytics/movers",
        params={"category": "TOP_GAINERS", "snapshot_date": "2024-08-01"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["category"] == "TOP_GAINERS"
    assert len(data["movers"]) == 2
    assert data["movers"][0]["rank"] == 1
    assert data["movers"][0]["ticker"] == "A"


@pytest.mark.asyncio
async def test_get_movers_latest(client: AsyncClient, session: AsyncSession):
    await _seed_snapshot(session, date(2024, 8, 2), "TOP_LOSERS", SAMPLE_RANKINGS[:1])
    resp = await client.get("/v1/analytics/movers", params={"category": "TOP_LOSERS"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["category"] == "TOP_LOSERS"
    assert len(data["movers"]) >= 1


@pytest.mark.asyncio
async def test_get_movers_summary_empty(client: AsyncClient):
    # Use a specific date that has no data to avoid module-scoped DB pollution
    resp = await client.get(
        "/v1/analytics/movers/summary", params={"snapshot_date": "1999-01-01"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["gainers_count"] == 0
    assert data["losers_count"] == 0
    assert data["most_active_count"] == 0


@pytest.mark.asyncio
async def test_get_movers_summary_with_data(client: AsyncClient, session: AsyncSession):
    d = date(2024, 8, 3)
    await _seed_snapshot(session, d, "TOP_GAINERS", SAMPLE_RANKINGS)
    await _seed_snapshot(session, d, "TOP_LOSERS", SAMPLE_RANKINGS[:1])
    await _seed_snapshot(session, d, "MOST_ACTIVE", SAMPLE_RANKINGS)
    resp = await client.get(
        "/v1/analytics/movers/summary", params={"snapshot_date": "2024-08-03"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["gainers_count"] == 2
    assert data["losers_count"] == 1
    assert data["most_active_count"] == 2
