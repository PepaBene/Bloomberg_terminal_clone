"""API tests for FI Issuer Profile endpoints (Pillar 2 FI Supplement -- Part 7)."""

import uuid
from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.corporate_bond import CorporateBond
from src.models.entity import Entity


# ── Helpers ──────────────────────────────────────────────────────────


async def _seed_entity(session: AsyncSession, entity_id: uuid.UUID, name: str = "E14 Test Corp") -> Entity:
    entity = Entity(
        entity_id=entity_id,
        entity_type="CORPORATION",
        legal_name=name,
        short_name="E14TEST",
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
    **kwargs,
) -> CorporateBond:
    defaults = {
        "bond_id": uuid.uuid4(),
        "cusip": cusip,
        "issuer_entity_id": entity_id,
        "issuer_name": "E14 Test Corp",
        "name": f"E14 Test Bond {cusip}",
        "coupon_rate": 0.05,
        "coupon_type": "FIXED",
        "coupon_frequency": 2,
        "day_count_convention": "30/360",
        "maturity_date": date(2030, 6, 15),
        "seniority": "SENIOR_UNSECURED",
        "currency": "USD",
        "is_investment_grade": True,
        "status": "OUTSTANDING",
        "is_callable": False,
        "outstanding_amount": 500_000_000.0,
    }
    defaults.update(kwargs)
    bond = CorporateBond(**defaults)
    session.add(bond)
    await session.commit()
    return bond


# ── Tests ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_fi_profile(client: AsyncClient, session: AsyncSession):
    """GET /v2/analytics/entities/{id}/fi-profile returns full profile."""
    eid = uuid.uuid4()
    await _seed_entity(session, eid)
    await _seed_bond(session, eid, cusip="E14PRF001", maturity_date=date(2027, 6, 15), seniority="SENIOR_SECURED", outstanding_amount=300_000_000.0)
    await _seed_bond(session, eid, cusip="E14PRF002", maturity_date=date(2030, 6, 15), seniority="SENIOR_UNSECURED", outstanding_amount=500_000_000.0)
    await _seed_bond(session, eid, cusip="E14PRF003", maturity_date=date(2035, 6, 15), seniority="SUBORDINATED", outstanding_amount=200_000_000.0)

    resp = await client.get(f"/v2/analytics/entities/{eid}/fi-profile")
    assert resp.status_code == 200
    data = resp.json()
    assert data["entity_id"] == str(eid)
    assert data["entity_name"] == "E14 Test Corp"
    assert data["bond_count"] == 3
    assert data["total_debt_outstanding"] == pytest.approx(1_000_000_000.0, rel=0.01)
    assert data["weighted_avg_coupon"] > 0
    assert data["weighted_avg_maturity_years"] > 0
    assert len(data["maturity_wall"]) > 0
    assert len(data["debt_stack"]) == 3


@pytest.mark.asyncio
async def test_get_fi_profile_entity_not_found(client: AsyncClient):
    """GET /v2/analytics/entities/{id}/fi-profile returns 404 for missing entity."""
    fake_id = uuid.uuid4()
    resp = await client.get(f"/v2/analytics/entities/{fake_id}/fi-profile")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_fi_profile_no_bonds(client: AsyncClient, session: AsyncSession):
    """GET /v2/analytics/entities/{id}/fi-profile returns 404 when entity has no bonds."""
    eid = uuid.uuid4()
    await _seed_entity(session, eid, name="NoBonds Corp")
    resp = await client.get(f"/v2/analytics/entities/{eid}/fi-profile")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_maturity_wall(client: AsyncClient, session: AsyncSession):
    """GET /v2/analytics/entities/{id}/fi-profile/maturity-wall returns wall data."""
    eid = uuid.uuid4()
    await _seed_entity(session, eid)
    await _seed_bond(session, eid, cusip="E14MW001", maturity_date=date(2027, 6, 15), outstanding_amount=400_000_000.0)
    await _seed_bond(session, eid, cusip="E14MW002", maturity_date=date(2029, 6, 15), outstanding_amount=600_000_000.0)

    resp = await client.get(f"/v2/analytics/entities/{eid}/fi-profile/maturity-wall", params={"years_forward": 10})
    assert resp.status_code == 200
    data = resp.json()
    assert data["entity_id"] == str(eid)
    assert data["years_forward"] == 10
    assert data["total_outstanding"] == pytest.approx(1_000_000_000.0, rel=0.01)
    assert len(data["maturity_wall"]) == 10


@pytest.mark.asyncio
async def test_get_debt_stack(client: AsyncClient, session: AsyncSession):
    """GET /v2/analytics/entities/{id}/fi-profile/debt-stack returns stack data."""
    eid = uuid.uuid4()
    await _seed_entity(session, eid)
    await _seed_bond(session, eid, cusip="E14DS001", seniority="SENIOR_SECURED", outstanding_amount=300_000_000.0)
    await _seed_bond(session, eid, cusip="E14DS002", seniority="SENIOR_UNSECURED", outstanding_amount=500_000_000.0)

    resp = await client.get(f"/v2/analytics/entities/{eid}/fi-profile/debt-stack")
    assert resp.status_code == 200
    data = resp.json()
    assert data["entity_id"] == str(eid)
    assert len(data["debt_stack"]) == 2
    # First item should be SENIOR_SECURED (highest priority)
    assert data["debt_stack"][0]["seniority"] == "SENIOR_SECURED"
    assert data["debt_stack"][1]["seniority"] == "SENIOR_UNSECURED"
    assert data["total_outstanding"] == pytest.approx(800_000_000.0, rel=0.01)


@pytest.mark.asyncio
async def test_get_refinancing_risk(client: AsyncClient, session: AsyncSession):
    """GET /v2/analytics/entities/{id}/fi-profile/refinancing-risk returns risk data."""
    eid = uuid.uuid4()
    await _seed_entity(session, eid)
    # Bond maturing soon
    await _seed_bond(session, eid, cusip="E14RR001", maturity_date=date(2026, 3, 15), outstanding_amount=800_000_000.0)
    # Bond maturing far out
    await _seed_bond(session, eid, cusip="E14RR002", maturity_date=date(2035, 6, 15), outstanding_amount=200_000_000.0)

    resp = await client.get(
        f"/v2/analytics/entities/{eid}/fi-profile/refinancing-risk",
        params={"current_spread_bps": 400.0},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["entity_id"] == str(eid)
    assert 0 <= data["score"] <= 100
    assert data["assessment"] in ("LOW", "MODERATE", "ELEVATED", "HIGH")
    assert data["maturity_wall_pct_2y"] >= 0
    assert data["current_spread_bps"] == 400.0


@pytest.mark.asyncio
async def test_get_refinancing_risk_no_bonds(client: AsyncClient, session: AsyncSession):
    """GET refinancing-risk returns 404 when no bonds exist."""
    eid = uuid.uuid4()
    await _seed_entity(session, eid, name="NoBonds2 Corp")
    resp = await client.get(f"/v2/analytics/entities/{eid}/fi-profile/refinancing-risk")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_maturity_wall_custom_window(client: AsyncClient, session: AsyncSession):
    """Maturity wall respects custom years_forward parameter."""
    eid = uuid.uuid4()
    await _seed_entity(session, eid)
    await _seed_bond(session, eid, cusip="E14CW001", maturity_date=date(2028, 1, 1), outstanding_amount=100_000_000.0)

    resp = await client.get(
        f"/v2/analytics/entities/{eid}/fi-profile/maturity-wall",
        params={"years_forward": 3},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["years_forward"] == 3
    assert len(data["maturity_wall"]) == 3
