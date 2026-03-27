"""API tests for Industry Intelligence endpoints (Pillar 3 Phase 3A)."""

import uuid
from datetime import date
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.industry_intelligence import (
    IndustryCompetitiveStructure,
    IndustryCyclePosition,
    IndustryProfile,
)


# ── Helpers ──────────────────────────────────────────────────────────


async def _seed_profile(session, gics_code="45102010", gics_name="Application Software"):
    pid = uuid.uuid4()
    profile = IndustryProfile(
        id=pid,
        gics_code=gics_code,
        gics_level="SUB_INDUSTRY",
        gics_name=gics_name,
        as_of_date=date(2025, 6, 30),
        company_count=150,
        total_market_cap=Decimal("5500000000000.00"),
        median_market_cap=Decimal("12000000000.00"),
        revenue_growth_3y_cagr=Decimal("0.1520"),
        revenue_growth_5y_cagr=Decimal("0.1340"),
        median_gross_margin=Decimal("0.7200"),
        median_operating_margin=Decimal("0.2500"),
        median_roic=Decimal("0.1800"),
        median_wacc=Decimal("0.0950"),
        roic_wacc_spread=Decimal("0.0850"),
        capital_cycle_indicator="EXPANSION",
    )
    session.add(profile)
    await session.flush()
    return profile


async def _seed_cycle(session, gics_code="45102010"):
    cid = uuid.uuid4()
    cycle = IndustryCyclePosition(
        id=cid,
        gics_code=gics_code,
        as_of_date=date(2025, 6, 30),
        cycle_position="EXPANSION",
        cycle_confidence=Decimal("75.50"),
        prior_cycle_position="RECOVERY",
        cycle_duration_quarters=6,
    )
    session.add(cycle)
    await session.flush()
    return cycle


async def _seed_structure(session, gics_code="45102010"):
    sid = uuid.uuid4()
    structure = IndustryCompetitiveStructure(
        id=sid,
        gics_code=gics_code,
        as_of_date=date(2025, 6, 30),
        hhi_index=Decimal("1250.50"),
        hhi_classification="MODERATE",
        top3_market_share=Decimal("0.5500"),
        barrier_to_entry="HIGH",
        pricing_power="STRONG",
        competitive_dynamics="OLIGOPOLY",
    )
    session.add(structure)
    await session.flush()
    return structure


# ── Overview endpoint ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_overview_no_data(client: AsyncClient, session: AsyncSession):
    """GET /v3/industry/{gics_code}/overview returns 404 when no data."""
    resp = await client.get("/v3/industry/99999999/overview")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_overview_with_data(client: AsyncClient, session: AsyncSession):
    """GET /v3/industry/{gics_code}/overview returns profile data."""
    await _seed_profile(session)
    resp = await client.get("/v3/industry/45102010/overview")
    assert resp.status_code == 200
    data = resp.json()
    assert data["gics_code"] == "45102010"
    assert data["gics_name"] == "Application Software"
    assert data["company_count"] == 150
    assert data["capital_cycle_indicator"] == "EXPANSION"


# ── Companies endpoint ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_companies_no_data(client: AsyncClient, session: AsyncSession):
    """GET /v3/industry/{gics_code}/companies returns 404 when no data."""
    resp = await client.get("/v3/industry/99999999/companies")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_companies_with_data(client: AsyncClient, session: AsyncSession):
    """GET /v3/industry/{gics_code}/companies returns company count."""
    await _seed_profile(session)
    resp = await client.get("/v3/industry/45102010/companies")
    assert resp.status_code == 200
    data = resp.json()
    assert data["gics_code"] == "45102010"
    assert data["company_count"] == 150


# ── Economics endpoint ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_economics_no_data(client: AsyncClient, session: AsyncSession):
    """GET /v3/industry/{gics_code}/economics returns 404 when no data."""
    resp = await client.get("/v3/industry/99999999/economics")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_economics_with_data(client: AsyncClient, session: AsyncSession):
    """GET /v3/industry/{gics_code}/economics returns economic profile."""
    await _seed_profile(session)
    resp = await client.get("/v3/industry/45102010/economics")
    assert resp.status_code == 200
    data = resp.json()
    assert data["median_roic"] is not None
    assert data["median_gross_margin"] is not None
    assert data["roic_wacc_spread"] is not None


# ── Structure endpoint ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_structure_no_data(client: AsyncClient, session: AsyncSession):
    """GET /v3/industry/{gics_code}/structure returns 404 when no data."""
    resp = await client.get("/v3/industry/99999999/structure")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_structure_with_data(client: AsyncClient, session: AsyncSession):
    """GET /v3/industry/{gics_code}/structure returns competitive structure."""
    await _seed_structure(session)
    resp = await client.get("/v3/industry/45102010/structure")
    assert resp.status_code == 200
    data = resp.json()
    assert data["hhi_classification"] == "MODERATE"
    assert data["barrier_to_entry"] == "HIGH"
    assert data["pricing_power"] == "STRONG"


# ── Cycle endpoint ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_cycle_no_data(client: AsyncClient, session: AsyncSession):
    """GET /v3/industry/{gics_code}/cycle returns 404 when no data."""
    resp = await client.get("/v3/industry/99999999/cycle")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_cycle_with_data(client: AsyncClient, session: AsyncSession):
    """GET /v3/industry/{gics_code}/cycle returns cycle position."""
    await _seed_cycle(session)
    resp = await client.get("/v3/industry/45102010/cycle")
    assert resp.status_code == 200
    data = resp.json()
    assert data["cycle_position"] == "EXPANSION"
    assert data["prior_cycle_position"] == "RECOVERY"


# ── Compare endpoint ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_compare_no_data(client: AsyncClient, session: AsyncSession):
    """GET /v3/industry/compare with no matching codes returns empty list."""
    resp = await client.get("/v3/industry/compare", params={"codes": "99999999,88888888"})
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_compare_with_data(client: AsyncClient, session: AsyncSession):
    """GET /v3/industry/compare returns side-by-side comparison."""
    await _seed_profile(session, gics_code="45102010", gics_name="Application Software")
    await _seed_profile(session, gics_code="40101010", gics_name="Diversified Banks")
    resp = await client.get("/v3/industry/compare", params={"codes": "45102010,40101010"})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    codes = {entry["gics_code"] for entry in data}
    assert "45102010" in codes
    assert "40101010" in codes


@pytest.mark.asyncio
async def test_compare_single_code(client: AsyncClient, session: AsyncSession):
    """GET /v3/industry/compare with a single code returns one entry."""
    await _seed_profile(session)
    resp = await client.get("/v3/industry/compare", params={"codes": "45102010"})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1


# ── Rankings endpoint ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_rankings_invalid_metric(client: AsyncClient, session: AsyncSession):
    """GET /v3/industry/rankings with invalid metric returns 400."""
    resp = await client.get("/v3/industry/rankings", params={"metric": "invalid_metric"})
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_rankings_no_data(client: AsyncClient, session: AsyncSession):
    """GET /v3/industry/rankings with no data returns empty rankings."""
    resp = await client.get("/v3/industry/rankings", params={"metric": "median_roic"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["metric"] == "median_roic"
    assert data["rankings"] == []


@pytest.mark.asyncio
async def test_rankings_with_data(client: AsyncClient, session: AsyncSession):
    """GET /v3/industry/rankings returns ranked industries."""
    await _seed_profile(session, gics_code="45102010", gics_name="Application Software")
    await _seed_profile(session, gics_code="40101010", gics_name="Diversified Banks")
    resp = await client.get("/v3/industry/rankings", params={"metric": "median_roic"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["metric"] == "median_roic"
    assert len(data["rankings"]) == 2
    # Verify ranking order
    assert data["rankings"][0]["rank"] == 1
    assert data["rankings"][1]["rank"] == 2


@pytest.mark.asyncio
async def test_rankings_different_metrics(client: AsyncClient, session: AsyncSession):
    """GET /v3/industry/rankings works for different allowed metrics."""
    await _seed_profile(session)
    for metric in ["median_roic", "median_gross_margin", "total_market_cap", "company_count"]:
        resp = await client.get("/v3/industry/rankings", params={"metric": metric})
        assert resp.status_code == 200
        data = resp.json()
        assert data["metric"] == metric
