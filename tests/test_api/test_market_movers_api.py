"""API tests for market movers endpoints (Pillar 2 Supplement – Part 5).

The router computes gainers/losers/most-active LIVE from ``EODPrice`` rows
(no more dependency on the abandoned ``MarketMoversSnapshot`` table), so
these tests seed ``Entity`` + ``Security`` + ``EODPrice`` data directly
instead of a pre-built snapshot, and assert the current 404-on-no-data
contract (rather than the old fake 200/empty-list behavior).
"""

import uuid
from datetime import date, datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.entity import Entity
from src.models.security import EODPrice, Security, SecurityIdentifier

PRIOR_DATE = date(2024, 8, 1)
LATEST_DATE = date(2024, 8, 2)


async def _seed_security(session: AsyncSession, name: str, ticker: str) -> uuid.UUID:
    """Create an Entity + Security (+ TICKER identifier) and return the security_id."""
    now = datetime.now(timezone.utc)
    entity = Entity(
        entity_id=uuid.uuid4(),
        entity_type="PUBLIC_COMPANY",
        legal_name=name,
        status="ACTIVE",
        source="TEST",
        created_at=now,
        updated_at=now,
    )
    session.add(entity)
    await session.flush()

    sec = Security(
        security_id=uuid.uuid4(),
        name=name,
        short_name=ticker,
        security_type="COMMON_STOCK",
        asset_class="EQUITY",
        status="ACTIVE",
        issuer_entity_id=entity.entity_id,
        created_at=now,
        updated_at=now,
    )
    session.add(sec)
    await session.flush()

    session.add(
        SecurityIdentifier(
            security_id=sec.security_id,
            identifier_type="TICKER",
            identifier_value=ticker,
            source="TEST",
        )
    )
    await session.flush()
    return sec.security_id


async def _seed_price(
    session: AsyncSession,
    security_id: uuid.UUID,
    price_date: date,
    close: float,
    volume: int = 5000,
) -> None:
    session.add(
        EODPrice(
            security_id=security_id,
            price_date=price_date,
            open=close,
            high=close,
            low=close,
            close=close,
            close_adjusted=close,
            volume=volume,
            source="TEST",
        )
    )
    await session.flush()


@pytest.mark.asyncio
async def test_get_movers_empty(client: AsyncClient):
    """No EOD price data at all -> 404, matching the "no fake data" contract."""
    resp = await client.get("/v1/analytics/movers", params={"category": "TOP_GAINERS"})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_movers_with_data(client: AsyncClient, session: AsyncSession):
    sec_a = await _seed_security(session, "Stock A", "A")
    sec_b = await _seed_security(session, "Stock B", "B")

    # Stock A: 100 -> 110 (+10%), Stock B: 100 -> 95 (-5%)
    await _seed_price(session, sec_a, PRIOR_DATE, 100.0, volume=5000)
    await _seed_price(session, sec_a, LATEST_DATE, 110.0, volume=5000)
    await _seed_price(session, sec_b, PRIOR_DATE, 100.0, volume=3000)
    await _seed_price(session, sec_b, LATEST_DATE, 95.0, volume=3000)

    resp = await client.get(
        "/v1/analytics/movers",
        params={"category": "TOP_GAINERS", "snapshot_date": LATEST_DATE.isoformat()},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["category"] == "TOP_GAINERS"
    assert data["snapshot_date"] == LATEST_DATE.isoformat()
    assert len(data["movers"]) == 2
    assert data["movers"][0]["rank"] == 1
    assert data["movers"][0]["ticker"] == "A"


@pytest.mark.asyncio
async def test_get_movers_latest(client: AsyncClient, session: AsyncSession):
    """Omitting snapshot_date resolves to the latest available trading date."""
    sec = await _seed_security(session, "Stock C", "C")
    await _seed_price(session, sec, PRIOR_DATE, 100.0, volume=2000)
    await _seed_price(session, sec, LATEST_DATE, 90.0, volume=2000)

    resp = await client.get("/v1/analytics/movers", params={"category": "TOP_LOSERS"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["category"] == "TOP_LOSERS"
    assert len(data["movers"]) >= 1


@pytest.mark.asyncio
async def test_get_movers_summary_empty(client: AsyncClient):
    """No EOD data for the requested date -> 404 (was silently faked with
    snapshot_date=date.today() and all-zero counts before)."""
    resp = await client.get(
        "/v1/analytics/movers/summary", params={"snapshot_date": "1999-01-01"}
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_movers_summary_with_data(client: AsyncClient, session: AsyncSession):
    sec_a = await _seed_security(session, "Stock D", "D")
    sec_b = await _seed_security(session, "Stock E", "E")

    # Stock D: 100 -> 120 (+20%), Stock E: 100 -> 80 (-20%)
    await _seed_price(session, sec_a, PRIOR_DATE, 100.0, volume=5000)
    await _seed_price(session, sec_a, LATEST_DATE, 120.0, volume=5000)
    await _seed_price(session, sec_b, PRIOR_DATE, 100.0, volume=3000)
    await _seed_price(session, sec_b, LATEST_DATE, 80.0, volume=3000)

    resp = await client.get(
        "/v1/analytics/movers/summary",
        params={"snapshot_date": LATEST_DATE.isoformat()},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["snapshot_date"] == LATEST_DATE.isoformat()
    assert data["gainers_count"] == 2
    assert data["losers_count"] == 2
    assert data["most_active_count"] == 2
