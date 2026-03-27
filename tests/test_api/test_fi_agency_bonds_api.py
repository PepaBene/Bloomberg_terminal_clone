"""API tests for agency bonds endpoints (D11 FI Supplement – Part 8)."""

import uuid
from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.agency_bond import AgencyBond


# ── Helpers ──────────────────────────────────────────────────────────


async def _seed_bond(
    session: AsyncSession,
    cusip: str,
    agency_type: str = "FNMA",
    bond_id: uuid.UUID | None = None,
    **kwargs,
) -> AgencyBond:
    bid = bond_id or uuid.uuid4()
    defaults = {
        "bond_id": bid,
        "cusip": cusip,
        "issuer_name": "Federal National Mortgage Association",
        "agency_type": agency_type,
        "backing_type": "CONSERVATORSHIP",
        "coupon_rate": 4.25,
        "coupon_type": "FIXED",
        "coupon_frequency": 2,
        "maturity_date": date(2034, 6, 15),
        "issue_date": date(2024, 6, 15),
        "currency": "USD",
        "is_callable": False,
        "is_outstanding": True,
        "status": "OUTSTANDING",
    }
    defaults.update(kwargs)
    bond = AgencyBond(**defaults)
    session.add(bond)
    await session.commit()
    return bond


# ── Tests ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_agency_bonds(client: AsyncClient, session: AsyncSession):
    """GET /v1/fixed-income/agency-bonds returns seeded bonds."""
    await _seed_bond(session, cusip="AGAPI00A1")
    await _seed_bond(session, cusip="AGAPI00A2")

    resp = await client.get("/v1/fixed-income/agency-bonds")
    assert resp.status_code == 200
    data = resp.json()
    cusips = [b["cusip"] for b in data["data"]]
    assert "AGAPI00A1" in cusips
    assert "AGAPI00A2" in cusips


@pytest.mark.asyncio
async def test_filter_by_agency_type(client: AsyncClient, session: AsyncSession):
    """GET /v1/fixed-income/agency-bonds?agency_type=FHLB filters correctly."""
    await _seed_bond(session, cusip="AGAPI00B1", agency_type="FHLB")
    await _seed_bond(session, cusip="AGAPI00B2", agency_type="FHLMC")

    resp = await client.get("/v1/fixed-income/agency-bonds", params={"agency_type": "FHLB"})
    assert resp.status_code == 200
    data = resp.json()
    cusips = [b["cusip"] for b in data["data"]]
    assert "AGAPI00B1" in cusips
    assert "AGAPI00B2" not in cusips


@pytest.mark.asyncio
async def test_by_agency(client: AsyncClient, session: AsyncSession):
    """GET /v1/fixed-income/agency-bonds/by-agency/FNMA returns FNMA bonds."""
    await _seed_bond(session, cusip="AGAPI00C1", agency_type="FNMA")
    await _seed_bond(session, cusip="AGAPI00C2", agency_type="TVA")

    resp = await client.get("/v1/fixed-income/agency-bonds/by-agency/FNMA")
    assert resp.status_code == 200
    data = resp.json()
    cusips = [b["cusip"] for b in data["data"]]
    assert "AGAPI00C1" in cusips
    assert "AGAPI00C2" not in cusips


@pytest.mark.asyncio
async def test_get_by_cusip(client: AsyncClient, session: AsyncSession):
    """GET /v1/fixed-income/agency-bonds/{cusip} returns correct bond."""
    await _seed_bond(session, cusip="AGAPI00D1")

    resp = await client.get("/v1/fixed-income/agency-bonds/AGAPI00D1")
    assert resp.status_code == 200
    data = resp.json()
    assert data["cusip"] == "AGAPI00D1"
    assert data["agency_type"] == "FNMA"
    assert data["issuer_name"] == "Federal National Mortgage Association"


@pytest.mark.asyncio
async def test_get_by_cusip_404(client: AsyncClient):
    """GET /v1/fixed-income/agency-bonds/NONEXIST1 returns 404."""
    resp = await client.get("/v1/fixed-income/agency-bonds/NONEXIST1")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_filter_outstanding(client: AsyncClient, session: AsyncSession):
    """GET /v1/fixed-income/agency-bonds?is_outstanding=true filters correctly."""
    await _seed_bond(session, cusip="AGAPI00E1", is_outstanding=True)
    await _seed_bond(session, cusip="AGAPI00E2", is_outstanding=False)

    resp = await client.get("/v1/fixed-income/agency-bonds", params={"is_outstanding": "true"})
    assert resp.status_code == 200
    data = resp.json()
    cusips = [b["cusip"] for b in data["data"]]
    assert "AGAPI00E1" in cusips
    assert "AGAPI00E2" not in cusips
