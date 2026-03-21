"""API tests for security finder endpoints (Pillar 2 Supplement – Part 5)."""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.security import Security


async def _seed_securities(session: AsyncSession):
    for name, short, stype in [
        ("Apple Inc", "AAPL", "COMMON_STOCK"),
        ("Microsoft Corp", "MSFT", "COMMON_STOCK"),
        ("Alphabet Inc", "GOOGL", "COMMON_STOCK"),
    ]:
        session.add(Security(
            security_id=uuid.uuid4(), name=name, short_name=short,
            security_type=stype, asset_class="EQUITY", status="ACTIVE",
        ))
    await session.commit()


@pytest.mark.asyncio
async def test_find_securities(client: AsyncClient, session: AsyncSession):
    await _seed_securities(session)
    resp = await client.get("/v1/securities/find", params={"q": "apple"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_results"] >= 1
    assert any("Apple" in r["name"] for r in data["results"])


@pytest.mark.asyncio
async def test_find_securities_no_match(client: AsyncClient, session: AsyncSession):
    await _seed_securities(session)
    resp = await client.get("/v1/securities/find", params={"q": "zzznonexistent"})
    assert resp.status_code == 200
    assert resp.json()["total_results"] == 0


@pytest.mark.asyncio
async def test_suggest_securities(client: AsyncClient, session: AsyncSession):
    await _seed_securities(session)
    resp = await client.get("/v1/securities/find/suggest", params={"q": "AA"})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
