"""API tests for Duration & Convexity Analytics (Pillar 2 FI Supplement – Part 2)."""

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
        legal_name="Duration Test Corp",
        short_name="DURTEST",
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
    cusip: str = "DUR000001",
    bond_id: uuid.UUID | None = None,
    **kwargs,
) -> CorporateBond:
    bid = bond_id or uuid.uuid4()
    defaults = {
        "bond_id": bid,
        "cusip": cusip,
        "issuer_entity_id": entity_id,
        "issuer_name": "Duration Test Corp",
        "name": "DurTest 5.00% 2035",
        "coupon_rate": 5.0,
        "coupon_type": "FIXED",
        "coupon_frequency": 2,
        "maturity_date": date(2035, 6, 15),
        "seniority": "SENIOR_UNSECURED",
        "currency": "USD",
        "is_investment_grade": True,
        "is_callable": False,
        "status": "OUTSTANDING",
    }
    defaults.update(kwargs)
    bond = CorporateBond(**defaults)
    session.add(bond)
    await session.commit()
    return bond


# ── Tests ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_duration(client: AsyncClient, session: AsyncSession):
    """GET /v2/analytics/bonds/{cusip}/duration returns duration metrics."""
    eid = uuid.uuid4()
    await _seed_entity(session, eid)
    bond = await _seed_bond(session, eid, cusip="DUR100001")

    # Seed an EOD price so the endpoint can resolve price
    eod = BondEODPrice(
        bond_id=bond.bond_id,
        price_date=date(2025, 10, 1),
        last_trade_price=98.5,
        yield_to_maturity=0.0520,
        has_sufficient_trades=True,
    )
    session.add(eod)
    await session.commit()

    resp = await client.get("/v2/analytics/bonds/DUR100001/duration")
    assert resp.status_code == 200
    data = resp.json()
    assert data["cusip"] == "DUR100001"
    assert data["modified_duration"] > 0
    assert data["macaulay_duration"] > 0
    assert data["dv01"] > 0
    assert data["convexity"] > 0


@pytest.mark.asyncio
async def test_get_duration_with_price_override(client: AsyncClient, session: AsyncSession):
    """GET /v2/analytics/bonds/{cusip}/duration?price=100 uses override price."""
    eid = uuid.uuid4()
    await _seed_entity(session, eid)
    await _seed_bond(session, eid, cusip="DUR100002")

    resp = await client.get("/v2/analytics/bonds/DUR100002/duration", params={"price": 100.0})
    assert resp.status_code == 200
    data = resp.json()
    assert data["modified_duration"] > 0


@pytest.mark.asyncio
async def test_get_duration_404(client: AsyncClient):
    """GET /v2/analytics/bonds/NOTFOUND1/duration returns 404."""
    resp = await client.get("/v2/analytics/bonds/NOTFOUND1/duration")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_duration_history(client: AsyncClient, session: AsyncSession):
    """GET /v2/analytics/bonds/{cusip}/duration/history returns time series."""
    eid = uuid.uuid4()
    await _seed_entity(session, eid)
    bond = await _seed_bond(session, eid, cusip="DUR200001")

    for d in [date(2025, 9, 28), date(2025, 9, 29), date(2025, 9, 30)]:
        session.add(BondEODPrice(
            bond_id=bond.bond_id,
            price_date=d,
            last_trade_price=99.0,
            has_sufficient_trades=True,
        ))
    await session.commit()

    resp = await client.get("/v2/analytics/bonds/DUR200001/duration/history")
    assert resp.status_code == 200
    data = resp.json()
    assert data["cusip"] == "DUR200001"
    assert len(data["history"]) == 3
    for item in data["history"]:
        assert "modified_duration" in item
        assert "dv01" in item
        assert "price_date" in item


@pytest.mark.asyncio
async def test_duration_history_404(client: AsyncClient):
    """GET /v2/analytics/bonds/NOTFOUND2/duration/history returns 404."""
    resp = await client.get("/v2/analytics/bonds/NOTFOUND2/duration/history")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_portfolio_duration(client: AsyncClient):
    """POST /v2/analytics/bonds/portfolio/duration computes portfolio aggregates."""
    body = {
        "positions": [
            {
                "cusip": "AAA000001",
                "weight": 0.6,
                "modified_duration": 5.0,
                "dv01": 0.05,
                "convexity": 30.0,
            },
            {
                "cusip": "AAA000002",
                "weight": 0.4,
                "modified_duration": 10.0,
                "dv01": 0.10,
                "convexity": 120.0,
            },
        ]
    }
    resp = await client.post("/v2/analytics/bonds/portfolio/duration", json=body)
    assert resp.status_code == 200
    data = resp.json()
    assert data["position_count"] == 2
    assert data["weighted_avg_duration"] == pytest.approx(7.0, abs=0.1)
    assert data["portfolio_dv01"] > 0
    assert data["weighted_avg_convexity"] > 0


@pytest.mark.asyncio
async def test_rate_sensitivity(client: AsyncClient, session: AsyncSession):
    """POST /v2/analytics/bonds/{cusip}/rate-sensitivity returns price impact table."""
    eid = uuid.uuid4()
    await _seed_entity(session, eid)
    bond = await _seed_bond(session, eid, cusip="DUR300001")

    session.add(BondEODPrice(
        bond_id=bond.bond_id,
        price_date=date(2025, 10, 1),
        last_trade_price=100.0,
        has_sufficient_trades=True,
    ))
    await session.commit()

    resp = await client.post("/v2/analytics/bonds/DUR300001/rate-sensitivity")
    assert resp.status_code == 200
    data = resp.json()
    assert data["cusip"] == "DUR300001"
    assert data["base_price"] == pytest.approx(100.0, abs=0.1)
    assert len(data["sensitivity"]) == 10

    # Positive shift should produce negative price change
    for item in data["sensitivity"]:
        if item["shift_bps"] > 0:
            assert item["price_change_pct"] < 0
        elif item["shift_bps"] < 0:
            assert item["price_change_pct"] > 0


@pytest.mark.asyncio
async def test_rate_sensitivity_404(client: AsyncClient):
    """POST /v2/analytics/bonds/NOTFOUND3/rate-sensitivity returns 404."""
    resp = await client.post("/v2/analytics/bonds/NOTFOUND3/rate-sensitivity")
    assert resp.status_code == 404
