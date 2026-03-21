"""API tests for custom index endpoints (Pillar 2 Supplement – Part 4)."""

import uuid
from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.custom_index import CustomIndex, IndexConstituent, IndexPerformance
from src.models.security import Security


async def _seed_index(session: AsyncSession, index_id: uuid.UUID) -> CustomIndex:
    idx = CustomIndex(
        index_id=index_id,
        name="Test Value Index",
        description="A test index",
        status="ACTIVE",
        weighting_method="EQUAL",
        rebalance_frequency="QUARTERLY",
        inception_date=date(2023, 1, 1),
    )
    session.add(idx)
    await session.commit()
    return idx


@pytest.mark.asyncio
async def test_create_index(client: AsyncClient):
    resp = await client.post(
        "/v1/analytics/indices",
        json={
            "name": "My Growth Index",
            "weighting_method": "MARKET_CAP",
            "rebalance_frequency": "MONTHLY",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "My Growth Index"
    assert data["status"] == "ACTIVE"


@pytest.mark.asyncio
async def test_list_indices(client: AsyncClient, session: AsyncSession):
    await _seed_index(session, uuid.uuid4())
    resp = await client.get("/v1/analytics/indices")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1


@pytest.mark.asyncio
async def test_get_index(client: AsyncClient, session: AsyncSession):
    iid = uuid.uuid4()
    await _seed_index(session, iid)
    resp = await client.get(f"/v1/analytics/indices/{iid}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["index_id"] == str(iid)
    assert data["name"] == "Test Value Index"


@pytest.mark.asyncio
async def test_get_index_404(client: AsyncClient):
    resp = await client.get(f"/v1/analytics/indices/{uuid.uuid4()}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_index_constituents(client: AsyncClient, session: AsyncSession):
    iid = uuid.uuid4()
    await _seed_index(session, iid)
    sid = uuid.uuid4()
    sec = Security(
        security_id=sid, name="Test Stock", security_type="COMMON_STOCK",
        asset_class="EQUITY", status="ACTIVE",
    )
    session.add(sec)
    await session.flush()
    constituent = IndexConstituent(
        constituent_id=uuid.uuid4(),
        index_id=iid, security_id=sid,
        weight=0.5, added_date=date(2023, 1, 1), is_active=True,
    )
    session.add(constituent)
    await session.commit()

    resp = await client.get(f"/v1/analytics/indices/{iid}/constituents")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["security_id"] == str(sid)


@pytest.mark.asyncio
async def test_get_index_performance(client: AsyncClient, session: AsyncSession):
    iid = uuid.uuid4()
    await _seed_index(session, iid)
    perf = IndexPerformance(
        id=uuid.uuid4(), index_id=iid, perf_date=date(2023, 1, 2),
        index_level=1010.0, daily_return=0.01, cumulative_return=0.01,
    )
    session.add(perf)
    await session.commit()

    resp = await client.get(f"/v1/analytics/indices/{iid}/performance")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["points"]) == 1
    assert data["points"][0]["index_level"] == pytest.approx(1010.0, abs=0.1)


@pytest.mark.asyncio
async def test_archive_index(client: AsyncClient, session: AsyncSession):
    iid = uuid.uuid4()
    await _seed_index(session, iid)
    resp = await client.delete(f"/v1/analytics/indices/{iid}")
    assert resp.status_code == 204
