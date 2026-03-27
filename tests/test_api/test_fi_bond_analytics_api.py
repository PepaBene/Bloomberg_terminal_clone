"""API tests for FI Bond Analytics endpoints (Pillar 2 FI Supplement -- Part 1)."""

import uuid
from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.corporate_bond import (
    BondCallSchedule,
    BondEODPrice,
    CorporateBond,
)
from src.models.entity import Entity


# ── Helpers ──────────────────────────────────────────────────────────


async def _seed_entity(session: AsyncSession, entity_id: uuid.UUID) -> Entity:
    entity = Entity(
        entity_id=entity_id,
        entity_type="CORPORATION",
        legal_name="E9 Test Corp",
        short_name="E9TEST",
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
    cusip: str,
    bond_id: uuid.UUID | None = None,
    **kwargs,
) -> CorporateBond:
    bid = bond_id or uuid.uuid4()
    defaults = {
        "bond_id": bid,
        "cusip": cusip,
        "issuer_entity_id": entity_id,
        "issuer_name": "E9 Test Corp",
        "name": "E9 Test 5.00% 2035",
        "coupon_rate": 0.05,
        "coupon_type": "FIXED",
        "coupon_frequency": 2,
        "day_count_convention": "30/360",
        "maturity_date": date(2035, 6, 15),
        "seniority": "SENIOR_UNSECURED",
        "currency": "USD",
        "is_investment_grade": True,
        "status": "OUTSTANDING",
        "is_callable": False,
    }
    defaults.update(kwargs)
    bond = CorporateBond(**defaults)
    session.add(bond)
    await session.commit()
    return bond


async def _seed_eod_price(
    session: AsyncSession,
    bond_id: uuid.UUID,
    price_date: date,
    price: float = 100.0,
    **kwargs,
) -> BondEODPrice:
    defaults = {
        "bond_id": bond_id,
        "price_date": price_date,
        "last_trade_price": price,
        "has_sufficient_trades": True,
        "price_source": "TRACE",
    }
    defaults.update(kwargs)
    eod = BondEODPrice(**defaults)
    session.add(eod)
    await session.commit()
    return eod


# ── Tests ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_bond_price(client: AsyncClient, session: AsyncSession):
    """GET /v2/analytics/bonds/{cusip}/price returns computed analytics."""
    eid = uuid.uuid4()
    await _seed_entity(session, eid)
    bond = await _seed_bond(session, eid, cusip="E9PRCE001")
    await _seed_eod_price(session, bond.bond_id, date(2025, 10, 1), price=98.5)

    resp = await client.get("/v2/analytics/bonds/E9PRCE001/price")
    assert resp.status_code == 200
    data = resp.json()
    assert data["cusip"] == "E9PRCE001"
    assert data["clean_price"] == pytest.approx(98.5, abs=0.1)
    assert data["dirty_price"] >= data["clean_price"]
    assert data["yield_to_maturity"] > 0


@pytest.mark.asyncio
async def test_get_bond_price_404(client: AsyncClient):
    """GET /v2/analytics/bonds/NOEXIST01/price returns 404."""
    resp = await client.get("/v2/analytics/bonds/NOEXIST01/price")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_bond_price_no_eod(client: AsyncClient, session: AsyncSession):
    """GET /v2/analytics/bonds/{cusip}/price returns 404 when no EOD price exists."""
    eid = uuid.uuid4()
    await _seed_entity(session, eid)
    await _seed_bond(session, eid, cusip="E9NOEOD01")

    resp = await client.get("/v2/analytics/bonds/E9NOEOD01/price")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_bond_price_history(client: AsyncClient, session: AsyncSession):
    """GET /v2/analytics/bonds/{cusip}/price-history returns history items."""
    eid = uuid.uuid4()
    await _seed_entity(session, eid)
    bond = await _seed_bond(session, eid, cusip="E9HIST001")

    for d in [date(2025, 10, 1), date(2025, 10, 2), date(2025, 10, 3)]:
        await _seed_eod_price(session, bond.bond_id, d, price=99.0)

    resp = await client.get("/v2/analytics/bonds/E9HIST001/price-history")
    assert resp.status_code == 200
    data = resp.json()
    assert data["cusip"] == "E9HIST001"
    assert len(data["history"]) == 3


@pytest.mark.asyncio
async def test_get_bond_cash_flows(client: AsyncClient, session: AsyncSession):
    """GET /v2/analytics/bonds/{cusip}/cash-flows returns schedule."""
    eid = uuid.uuid4()
    await _seed_entity(session, eid)
    await _seed_bond(
        session, eid, cusip="E9FLOW001",
        maturity_date=date(2030, 6, 15),
        coupon_rate=0.05,
        coupon_frequency=2,
    )

    resp = await client.get(
        "/v2/analytics/bonds/E9FLOW001/cash-flows",
        params={"settlement_date": "2025-06-15"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["cusip"] == "E9FLOW001"
    assert len(data["cash_flows"]) > 0
    # 5Y semi-annual: 10 coupons + 1 principal = 11 flows
    coupon_flows = [f for f in data["cash_flows"] if f["type"] == "COUPON"]
    principal_flows = [f for f in data["cash_flows"] if f["type"] == "PRINCIPAL"]
    assert len(coupon_flows) == 10
    assert len(principal_flows) == 1
    assert data["total_coupon_payments"] > 0
    assert data["total_cash_flows"] > data["total_coupon_payments"]


@pytest.mark.asyncio
async def test_post_price_from_yield(client: AsyncClient):
    """POST /v2/analytics/bonds/price-from-yield computes prices."""
    payload = {
        "coupon_rate": 0.05,
        "face_value": 100.0,
        "settlement_date": "2025-06-15",
        "maturity_date": "2035-06-15",
        "yield_value": 0.05,
        "frequency": 2,
        "day_count": "30/360",
    }
    resp = await client.post("/v2/analytics/bonds/price-from-yield", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    # At par yield, clean price ~100
    assert data["clean_price"] == pytest.approx(100.0, abs=1.0)
    assert data["yield_value"] == 0.05


@pytest.mark.asyncio
async def test_post_yield_from_price(client: AsyncClient):
    """POST /v2/analytics/bonds/yield-from-price computes yield."""
    payload = {
        "coupon_rate": 0.05,
        "face_value": 100.0,
        "settlement_date": "2025-06-15",
        "maturity_date": "2035-06-15",
        "clean_price": 100.0,
        "frequency": 2,
        "day_count": "30/360",
    }
    resp = await client.post("/v2/analytics/bonds/yield-from-price", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["yield_to_maturity"] == pytest.approx(0.05, abs=0.005)
    assert data["clean_price"] == 100.0


@pytest.mark.asyncio
async def test_post_ytw_no_calls(client: AsyncClient):
    """POST /v2/analytics/bonds/ytw without call schedule: ytw == ytm."""
    payload = {
        "coupon_rate": 0.05,
        "face_value": 100.0,
        "settlement_date": "2025-06-15",
        "maturity_date": "2035-06-15",
        "clean_price": 100.0,
        "frequency": 2,
        "day_count": "30/360",
    }
    resp = await client.post("/v2/analytics/bonds/ytw", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["yield_to"] == "MATURITY"
    assert data["exercise_date"] is None
    assert data["yield_to_worst"] == pytest.approx(data["yield_to_maturity"], abs=1e-6)


@pytest.mark.asyncio
async def test_post_ytw_with_calls(client: AsyncClient):
    """POST /v2/analytics/bonds/ytw with call schedule computes call yields."""
    payload = {
        "coupon_rate": 0.06,
        "face_value": 100.0,
        "settlement_date": "2025-06-15",
        "maturity_date": "2035-06-15",
        "clean_price": 105.0,
        "frequency": 2,
        "day_count": "30/360",
        "call_schedule": [
            {"call_date": "2028-06-15", "call_price": 100.0},
        ],
    }
    resp = await client.post("/v2/analytics/bonds/ytw", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["call_yields"] is not None
    assert len(data["call_yields"]) == 1
    assert data["yield_to_worst"] <= data["yield_to_maturity"]


@pytest.mark.asyncio
async def test_get_bond_price_history_with_date_filter(client: AsyncClient, session: AsyncSession):
    """GET /v2/analytics/bonds/{cusip}/price-history with start/end filters."""
    eid = uuid.uuid4()
    await _seed_entity(session, eid)
    bond = await _seed_bond(session, eid, cusip="E9FILT001")

    for d in [date(2025, 9, 1), date(2025, 10, 1), date(2025, 11, 1)]:
        await _seed_eod_price(session, bond.bond_id, d, price=99.5)

    resp = await client.get(
        "/v2/analytics/bonds/E9FILT001/price-history",
        params={"start": "2025-10-01", "end": "2025-10-31"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["history"]) == 1
    assert data["history"][0]["price_date"] == "2025-10-01"
