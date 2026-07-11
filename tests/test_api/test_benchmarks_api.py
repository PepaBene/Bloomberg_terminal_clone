"""API tests for benchmarks endpoints (Pillar 2 Frontend Bugs 93-95).

Covers both benchmark kinds unified behind ``/v1/benchmarks``: standard
ETF-proxy-tracked indices (``Benchmark`` model, lazily seeded) and
user-created custom indices (delegated to the pre-existing
``CustomIndex``/``IndexConstituent`` system).
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

    session.add(SecurityIdentifier(
        security_id=sec.security_id,
        identifier_type="TICKER",
        identifier_value=ticker,
        source="TEST",
    ))
    await session.flush()
    return sec.security_id


async def _seed_price(
    session: AsyncSession, security_id: uuid.UUID, price_date: date, close: float,
) -> None:
    session.add(EODPrice(
        security_id=security_id,
        price_date=price_date,
        open=close, high=close, low=close, close=close, close_adjusted=close,
        volume=1000,
        source="TEST",
    ))
    await session.flush()


@pytest.mark.asyncio
async def test_list_benchmarks_seeds_standard_indices(client: AsyncClient):
    resp = await client.get("/v1/benchmarks")
    assert resp.status_code == 200
    data = resp.json()
    codes = {b["code"] for b in data}
    assert {"SP500", "NASDAQ100", "RUSSELL1000", "RUSSELL2000", "DOW"} <= codes
    sp500 = next(b for b in data if b["code"] == "SP500")
    assert sp500["benchmark_type"] == "INDEX"
    assert sp500["ticker"] == "SPY"


@pytest.mark.asyncio
async def test_create_benchmark_rejects_bad_weights(client: AsyncClient):
    resp = await client.post(
        "/v1/benchmarks",
        json={"name": "Bad Basket", "constituents": [{"ticker": "AAPL", "weight": 0.5}]},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_benchmark_rejects_unknown_ticker(client: AsyncClient, session: AsyncSession):
    await _seed_security(session, "Apple Inc.", "AAPL")
    resp = await client.post(
        "/v1/benchmarks",
        json={
            "name": "Unknown Ticker Basket",
            "constituents": [
                {"ticker": "AAPL", "weight": 0.5},
                {"ticker": "ZZZZNOPE", "weight": 0.5},
            ],
        },
    )
    assert resp.status_code == 422
    assert "ZZZZNOPE" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_create_benchmark_persists_via_custom_index(client: AsyncClient, session: AsyncSession):
    """POST /v1/benchmarks creates a real CustomIndex + IndexConstituent rows."""
    sec_a = await _seed_security(session, "Apple Inc.", "AAPL")
    sec_b = await _seed_security(session, "Microsoft Corp.", "MSFT")

    resp = await client.post(
        "/v1/benchmarks",
        json={
            "name": "My Tech Basket",
            "constituents": [
                {"ticker": "AAPL", "weight": 0.5},
                {"ticker": "MSFT", "weight": 0.5},
            ],
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "My Tech Basket"
    assert data["benchmark_type"] == "CUSTOM"
    assert data["constituent_count"] == 2
    benchmark_id = data["benchmark_id"]

    # Verify it's a real row in the pre-existing CustomIndex system, not a
    # second parallel storage mechanism.
    from src.models.custom_index import CustomIndex, IndexConstituent
    from sqlalchemy import select

    index_row = (
        await session.execute(select(CustomIndex).where(CustomIndex.index_id == uuid.UUID(benchmark_id)))
    ).scalar_one_or_none()
    assert index_row is not None
    assert index_row.name == "My Tech Basket"

    constituents = (
        await session.execute(
            select(IndexConstituent).where(IndexConstituent.index_id == uuid.UUID(benchmark_id))
        )
    ).scalars().all()
    assert {c.security_id for c in constituents} == {sec_a, sec_b}

    # And it shows up in the unified list.
    list_resp = await client.get("/v1/benchmarks")
    listed = [b for b in list_resp.json() if b["benchmark_id"] == benchmark_id]
    assert len(listed) == 1
    assert listed[0]["benchmark_type"] == "CUSTOM"


@pytest.mark.asyncio
async def test_get_custom_benchmark_detail(client: AsyncClient, session: AsyncSession):
    await _seed_security(session, "Solo Corp", "SOLOC")
    create_resp = await client.post(
        "/v1/benchmarks",
        json={"name": "Solo Basket", "constituents": [{"ticker": "SOLOC", "weight": 1.0}]},
    )
    benchmark_id = create_resp.json()["benchmark_id"]

    resp = await client.get(f"/v1/benchmarks/{benchmark_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["constituents"]) == 1
    assert data["constituents"][0]["ticker"] == "SOLOC"
    assert data["constituents"][0]["weight"] == 1.0


@pytest.mark.asyncio
async def test_get_benchmark_not_found(client: AsyncClient):
    resp = await client.get(f"/v1/benchmarks/{uuid.uuid4()}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_standard_index_returns_computed_from_eod_price(client: AsyncClient, session: AsyncSession):
    sec = await _seed_security(session, "SPDR S&P 500 ETF", "SPY")
    await _seed_price(session, sec, PRIOR_DATE, 100.0)
    await _seed_price(session, sec, LATEST_DATE, 110.0)

    list_resp = await client.get("/v1/benchmarks")
    sp500_id = next(b["benchmark_id"] for b in list_resp.json() if b["code"] == "SP500")

    resp = await client.get(
        f"/v1/benchmarks/{sp500_id}/returns",
        params={"start_date": PRIOR_DATE.isoformat(), "end_date": LATEST_DATE.isoformat()},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["trading_days"] == 2
    assert round(data["total_return"], 4) == 0.10


@pytest.mark.asyncio
async def test_custom_benchmark_returns_weight_averaged(client: AsyncClient, session: AsyncSession):
    sec_a = await _seed_security(session, "Stock A", "STKA")
    sec_b = await _seed_security(session, "Stock B", "STKB")
    await _seed_price(session, sec_a, PRIOR_DATE, 100.0)
    await _seed_price(session, sec_a, LATEST_DATE, 120.0)  # +20%
    await _seed_price(session, sec_b, PRIOR_DATE, 100.0)
    await _seed_price(session, sec_b, LATEST_DATE, 100.0)  # +0%

    create_resp = await client.post(
        "/v1/benchmarks",
        json={
            "name": "Half and Half",
            "constituents": [
                {"ticker": "STKA", "weight": 0.5},
                {"ticker": "STKB", "weight": 0.5},
            ],
        },
    )
    benchmark_id = create_resp.json()["benchmark_id"]

    resp = await client.get(
        f"/v1/benchmarks/{benchmark_id}/returns",
        params={"start_date": PRIOR_DATE.isoformat(), "end_date": LATEST_DATE.isoformat()},
    )
    assert resp.status_code == 200
    data = resp.json()
    # 0.5 * 20% + 0.5 * 0% = 10%
    assert round(data["total_return"], 4) == 0.10
    assert data["unresolved_tickers"] == []


@pytest.mark.asyncio
async def test_custom_benchmark_returns_reports_unresolved_constituent(
    client: AsyncClient, session: AsyncSession,
):
    sec_a = await _seed_security(session, "Stock C", "STKC")
    await _seed_security(session, "Stock D (no prices)", "STKD")
    await _seed_price(session, sec_a, PRIOR_DATE, 100.0)
    await _seed_price(session, sec_a, LATEST_DATE, 110.0)
    # STKD deliberately has no EOD price history at all.

    create_resp = await client.post(
        "/v1/benchmarks",
        json={
            "name": "Partial Data Basket",
            "constituents": [
                {"ticker": "STKC", "weight": 0.5},
                {"ticker": "STKD", "weight": 0.5},
            ],
        },
    )
    benchmark_id = create_resp.json()["benchmark_id"]

    resp = await client.get(
        f"/v1/benchmarks/{benchmark_id}/returns",
        params={"start_date": PRIOR_DATE.isoformat(), "end_date": LATEST_DATE.isoformat()},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["unresolved_tickers"] == ["STKD"]
