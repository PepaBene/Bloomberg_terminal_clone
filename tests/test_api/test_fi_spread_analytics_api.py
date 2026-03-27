"""API tests for FI Spread Analytics endpoints (Pillar 2 FI Supplement Part 3)."""

import uuid
from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.corporate_bond import BondEODPrice, CorporateBond
from src.models.entity import Entity


# ── Helpers ──────────────────────────────────────────────────────────


async def _seed_entity(session: AsyncSession, entity_id: uuid.UUID) -> Entity:
    entity = Entity(
        entity_id=entity_id,
        entity_type="CORPORATION",
        legal_name="Spread Test Corp",
        short_name="SPREADTEST",
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
    cusip: str = "SPRD00001",
    bond_id: uuid.UUID | None = None,
    **kwargs,
) -> CorporateBond:
    bid = bond_id or uuid.uuid4()
    defaults = {
        "bond_id": bid,
        "cusip": cusip,
        "issuer_entity_id": entity_id,
        "issuer_name": "Spread Test Corp",
        "name": "Spread Test Corp 5.00% 2035",
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


async def _seed_eod(
    session: AsyncSession,
    bond_id: uuid.UUID,
    price_date: date,
    g_spread_bps: int | None = 150,
    last_trade_price: float = 98.5,
    ytm: float = 0.052,
) -> BondEODPrice:
    eod = BondEODPrice(
        bond_id=bond_id,
        price_date=price_date,
        last_trade_price=last_trade_price,
        yield_to_maturity=ytm,
        g_spread_bps=g_spread_bps,
        has_sufficient_trades=True,
        price_source="TRACE",
    )
    session.add(eod)
    await session.commit()
    return eod


# ── Tests ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_spreads(client: AsyncClient, session: AsyncSession):
    """GET /v2/analytics/bonds/{cusip}/spreads returns spread data."""
    eid = uuid.uuid4()
    await _seed_entity(session, eid)
    bond = await _seed_bond(session, eid, cusip="SPAA00001")
    await _seed_eod(session, bond.bond_id, date(2025, 10, 1), g_spread_bps=150)

    resp = await client.get("/v2/analytics/bonds/SPAA00001/spreads")
    assert resp.status_code == 200
    data = resp.json()
    assert data["cusip"] == "SPAA00001"
    assert data["g_spread_bps"] == 150


@pytest.mark.asyncio
async def test_get_spreads_404(client: AsyncClient):
    """GET /v2/analytics/bonds/{cusip}/spreads returns 404 for unknown CUSIP."""
    resp = await client.get("/v2/analytics/bonds/NONEXIST9/spreads")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_spread_history(client: AsyncClient, session: AsyncSession):
    """GET /v2/analytics/bonds/{cusip}/spreads/history returns spread history."""
    eid = uuid.uuid4()
    await _seed_entity(session, eid)
    bond = await _seed_bond(session, eid, cusip="SPBB00001")

    for i, d in enumerate([date(2025, 10, 1), date(2025, 10, 2), date(2025, 10, 3)]):
        await _seed_eod(session, bond.bond_id, d, g_spread_bps=140 + i * 5)

    resp = await client.get("/v2/analytics/bonds/SPBB00001/spreads/history")
    assert resp.status_code == 200
    data = resp.json()
    assert data["cusip"] == "SPBB00001"
    assert len(data["history"]) == 3
    # Should be ordered by date ascending
    assert data["history"][0]["price_date"] == "2025-10-01"
    assert data["history"][0]["g_spread_bps"] == 140


@pytest.mark.asyncio
async def test_relative_value(client: AsyncClient, session: AsyncSession):
    """GET /v2/analytics/bonds/{cusip}/relative-value returns relative value data."""
    eid = uuid.uuid4()
    await _seed_entity(session, eid)
    bond = await _seed_bond(session, eid, cusip="SPCC00001")

    # Seed multiple EOD prices to build history
    for i, d in enumerate([
        date(2025, 9, 1), date(2025, 9, 15),
        date(2025, 10, 1), date(2025, 10, 15),
        date(2025, 11, 1),
    ]):
        await _seed_eod(
            session, bond.bond_id, d,
            g_spread_bps=130 + i * 10,
        )

    resp = await client.get("/v2/analytics/bonds/SPCC00001/relative-value")
    assert resp.status_code == 200
    data = resp.json()
    assert data["cusip"] == "SPCC00001"
    assert "own_percentile" in data
    assert "own_z_score" in data
    assert "rich_cheap_score" in data
    assert data["assessment"] in ("RICH", "FAIR", "CHEAP")


@pytest.mark.asyncio
async def test_breakeven(client: AsyncClient, session: AsyncSession):
    """GET /v2/analytics/bonds/{cusip}/breakeven returns breakeven data."""
    eid = uuid.uuid4()
    await _seed_entity(session, eid)
    bond = await _seed_bond(session, eid, cusip="SPDD00001")
    await _seed_eod(
        session, bond.bond_id, date(2025, 10, 1),
        g_spread_bps=150, last_trade_price=98.5,
    )

    resp = await client.get("/v2/analytics/bonds/SPDD00001/breakeven")
    assert resp.status_code == 200
    data = resp.json()
    assert data["cusip"] == "SPDD00001"
    assert data["spread_bps"] == 150.0
    assert data["carry_bps"] > 0
    assert data["breakeven_widening_bps"] > 0
    assert data["modified_duration"] > 0


@pytest.mark.asyncio
async def test_breakeven_custom_horizon(client: AsyncClient, session: AsyncSession):
    """GET /v2/analytics/bonds/{cusip}/breakeven?horizon_years=0.5 uses custom horizon."""
    eid = uuid.uuid4()
    await _seed_entity(session, eid)
    bond = await _seed_bond(session, eid, cusip="SPEE00001")
    await _seed_eod(
        session, bond.bond_id, date(2025, 10, 1),
        g_spread_bps=200, last_trade_price=97.0,
    )

    resp = await client.get(
        "/v2/analytics/bonds/SPEE00001/breakeven",
        params={"horizon_years": 0.5},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["horizon_years"] == 0.5
    # Carry should be half of spread for 6-month horizon
    assert data["carry_bps"] == pytest.approx(100.0, abs=1.0)


@pytest.mark.asyncio
async def test_spread_screen(client: AsyncClient, session: AsyncSession):
    """POST /v2/analytics/bonds/spread-screen returns filtered bonds."""
    eid = uuid.uuid4()
    await _seed_entity(session, eid)

    bond1 = await _seed_bond(session, eid, cusip="SPFF00001", name="Wide Spread Bond")
    await _seed_eod(session, bond1.bond_id, date(2025, 10, 1), g_spread_bps=300)

    bond2 = await _seed_bond(session, eid, cusip="SPFF00002", name="Tight Spread Bond")
    await _seed_eod(session, bond2.bond_id, date(2025, 10, 1), g_spread_bps=80)

    # Screen for min 200 bps spread
    resp = await client.post(
        "/v2/analytics/bonds/spread-screen",
        json={"min_spread_bps": 200},
    )
    assert resp.status_code == 200
    data = resp.json()
    cusips = [r["cusip"] for r in data["results"]]
    assert "SPFF00001" in cusips
    assert "SPFF00002" not in cusips


@pytest.mark.asyncio
async def test_spread_screen_max_filter(client: AsyncClient, session: AsyncSession):
    """POST /v2/analytics/bonds/spread-screen with max_spread_bps filter."""
    eid = uuid.uuid4()
    await _seed_entity(session, eid)

    bond1 = await _seed_bond(session, eid, cusip="SPGG00001", name="Moderate Spread")
    await _seed_eod(session, bond1.bond_id, date(2025, 10, 1), g_spread_bps=150)

    bond2 = await _seed_bond(session, eid, cusip="SPGG00002", name="Very Wide Spread")
    await _seed_eod(session, bond2.bond_id, date(2025, 10, 1), g_spread_bps=500)

    resp = await client.post(
        "/v2/analytics/bonds/spread-screen",
        json={"max_spread_bps": 200},
    )
    assert resp.status_code == 200
    data = resp.json()
    cusips = [r["cusip"] for r in data["results"]]
    assert "SPGG00001" in cusips
    assert "SPGG00002" not in cusips
