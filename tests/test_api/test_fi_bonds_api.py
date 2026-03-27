"""API tests for corporate bonds endpoints (D11 FI Supplement – Part 4)."""

import uuid
from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.corporate_bond import (
    BondCallSchedule,
    BondEODPrice,
    BondTrade,
    CorporateBond,
)
from src.models.entity import Entity


# ── Helpers ──────────────────────────────────────────────────────────


async def _seed_entity(session: AsyncSession, entity_id: uuid.UUID) -> Entity:
    entity = Entity(
        entity_id=entity_id,
        entity_type="CORPORATION",
        legal_name="Test Corp",
        short_name="TEST",
        status="ACTIVE",
        source="TEST",
        confidence_score=0.99,
    )
    session.add(entity)
    await session.commit()
    return entity


async def _seed_bond(
    session: AsyncSession,
    entity_id: uuid.UUID,
    cusip: str = "037833AK6",
    bond_id: uuid.UUID | None = None,
    **kwargs,
) -> CorporateBond:
    bid = bond_id or uuid.uuid4()
    defaults = {
        "bond_id": bid,
        "cusip": cusip,
        "issuer_entity_id": entity_id,
        "issuer_name": "Test Corp",
        "name": "Test Corp 5.00% 2035",
        "coupon_rate": 5.0,
        "coupon_type": "FIXED",
        "coupon_frequency": 2,
        "maturity_date": date(2035, 6, 15),
        "seniority": "SENIOR_UNSECURED",
        "currency": "USD",
        "is_investment_grade": True,
        "status": "OUTSTANDING",
    }
    defaults.update(kwargs)
    bond = CorporateBond(**defaults)
    session.add(bond)
    await session.commit()
    return bond


# ── Tests ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_bonds(client: AsyncClient, session: AsyncSession):
    """GET /v1/fixed-income/bonds returns seeded bonds."""
    eid = uuid.uuid4()
    await _seed_entity(session, eid)
    await _seed_bond(session, eid, cusip="AAABBB001")
    await _seed_bond(session, eid, cusip="AAABBB002")

    resp = await client.get("/v1/fixed-income/bonds")
    assert resp.status_code == 200
    data = resp.json()
    cusips = [b["cusip"] for b in data["data"]]
    assert "AAABBB001" in cusips
    assert "AAABBB002" in cusips


@pytest.mark.asyncio
async def test_get_by_cusip(client: AsyncClient, session: AsyncSession):
    """GET /v1/fixed-income/bonds/{cusip} returns correct bond."""
    eid = uuid.uuid4()
    await _seed_entity(session, eid)
    await _seed_bond(session, eid, cusip="CCCDDD001")

    resp = await client.get("/v1/fixed-income/bonds/CCCDDD001")
    assert resp.status_code == 200
    data = resp.json()
    assert data["cusip"] == "CCCDDD001"
    assert data["name"] == "Test Corp 5.00% 2035"


@pytest.mark.asyncio
async def test_get_by_cusip_404(client: AsyncClient):
    """GET /v1/fixed-income/bonds/NONEXIST1 returns 404."""
    resp = await client.get("/v1/fixed-income/bonds/NONEXIST1")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_bonds_by_issuer(client: AsyncClient, session: AsyncSession):
    """GET /v1/fixed-income/issuers/{entity_id}/bonds returns issuer's bonds."""
    eid = uuid.uuid4()
    await _seed_entity(session, eid)
    await _seed_bond(session, eid, cusip="EEEFFF001")
    await _seed_bond(session, eid, cusip="EEEFFF002")

    resp = await client.get(f"/v1/fixed-income/issuers/{eid}/bonds")
    assert resp.status_code == 200
    data = resp.json()
    cusips = [b["cusip"] for b in data["data"]]
    assert "EEEFFF001" in cusips
    assert "EEEFFF002" in cusips


@pytest.mark.asyncio
async def test_call_schedule(client: AsyncClient, session: AsyncSession):
    """GET /v1/fixed-income/bonds/{cusip}/call-schedule returns call entries."""
    eid = uuid.uuid4()
    await _seed_entity(session, eid)
    bond = await _seed_bond(session, eid, cusip="GGGHHH001", is_callable=True)

    cs1 = BondCallSchedule(
        bond_id=bond.bond_id,
        call_date=date(2030, 6, 15),
        call_price=101.0,
        call_type="MAKE_WHOLE",
    )
    cs2 = BondCallSchedule(
        bond_id=bond.bond_id,
        call_date=date(2032, 6, 15),
        call_price=100.5,
        call_type="PAR",
    )
    session.add_all([cs1, cs2])
    await session.commit()

    resp = await client.get("/v1/fixed-income/bonds/GGGHHH001/call-schedule")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2


@pytest.mark.asyncio
async def test_eod_price(client: AsyncClient, session: AsyncSession):
    """GET /v1/fixed-income/bonds/{cusip}/price returns latest EOD price."""
    eid = uuid.uuid4()
    await _seed_entity(session, eid)
    bond = await _seed_bond(session, eid, cusip="IIIJJJ001")

    eod = BondEODPrice(
        bond_id=bond.bond_id,
        price_date=date(2025, 10, 1),
        last_trade_price=98.5,
        vwap=98.45,
        trade_count=12,
        yield_to_maturity=0.0520,
        g_spread_bps=150,
        has_sufficient_trades=True,
        price_source="TRACE",
    )
    session.add(eod)
    await session.commit()

    resp = await client.get("/v1/fixed-income/bonds/IIIJJJ001/price")
    assert resp.status_code == 200
    data = resp.json()
    assert data["last_trade_price"] == pytest.approx(98.5, abs=0.1)
    assert data["g_spread_bps"] == 150


@pytest.mark.asyncio
async def test_price_history(client: AsyncClient, session: AsyncSession):
    """GET /v1/fixed-income/bonds/{cusip}/price-history returns multiple dates."""
    eid = uuid.uuid4()
    await _seed_entity(session, eid)
    bond = await _seed_bond(session, eid, cusip="KKKLL001")

    for d in [date(2025, 10, 1), date(2025, 10, 2), date(2025, 10, 3)]:
        session.add(BondEODPrice(
            bond_id=bond.bond_id,
            price_date=d,
            last_trade_price=98.5,
        ))
    await session.commit()

    resp = await client.get("/v1/fixed-income/bonds/KKKLL001/price-history")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["data"]) == 3


@pytest.mark.asyncio
async def test_filter_by_seniority(client: AsyncClient, session: AsyncSession):
    """GET /v1/fixed-income/bonds?seniority=SENIOR_UNSECURED filters correctly."""
    eid = uuid.uuid4()
    await _seed_entity(session, eid)
    await _seed_bond(session, eid, cusip="MMMNN001", seniority="SENIOR_UNSECURED")
    await _seed_bond(session, eid, cusip="MMMNN002", seniority="SUBORDINATED")

    resp = await client.get("/v1/fixed-income/bonds", params={"seniority": "SENIOR_UNSECURED"})
    assert resp.status_code == 200
    data = resp.json()
    cusips = [b["cusip"] for b in data["data"]]
    assert "MMMNN001" in cusips
    assert "MMMNN002" not in cusips


@pytest.mark.asyncio
async def test_search(client: AsyncClient, session: AsyncSession):
    """GET /v1/fixed-income/bonds/search?q=Apple returns matching bonds."""
    eid = uuid.uuid4()
    await _seed_entity(session, eid)
    await _seed_bond(session, eid, cusip="OOOPP001", issuer_name="Apple Inc.", name="Apple 4.25% 2030")
    await _seed_bond(session, eid, cusip="OOOPP002", issuer_name="Google LLC", name="Google 3.50% 2028")

    resp = await client.get("/v1/fixed-income/bonds/search", params={"q": "Apple"})
    assert resp.status_code == 200
    data = resp.json()
    cusips = [b["cusip"] for b in data["data"]]
    assert "OOOPP001" in cusips
    assert "OOOPP002" not in cusips


@pytest.mark.asyncio
async def test_bond_analytics(client: AsyncClient, session: AsyncSession):
    """GET /v1/fixed-income/bonds/{cusip}/analytics?price=100 returns ytm, duration, convexity."""
    eid = uuid.uuid4()
    await _seed_entity(session, eid)
    await _seed_bond(
        session, eid, cusip="QQQRR001",
        coupon_rate=5.0, coupon_frequency=2,
        maturity_date=date(2035, 6, 15),
    )

    resp = await client.get("/v1/fixed-income/bonds/QQQRR001/analytics", params={"price": 100.0})
    assert resp.status_code == 200
    data = resp.json()
    assert "ytm" in data
    assert "ytw" in data
    assert "modified_duration" in data
    assert "macaulay_duration" in data
    assert "convexity" in data
    assert data["ytm"] > 0
    assert data["modified_duration"] > 0
    assert data["convexity"] > 0
