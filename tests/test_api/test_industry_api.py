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


# ── Computed-from-fundamentals tests (on-demand producer) ────────────


async def _seed_gics_companies(session: AsyncSession, gics="45102010", n=4):
    from src.models.entity import Entity
    from src.models.fundamentals import (
        BalanceSheet, CashFlowStatement, FinancialPeriod, IncomeStatement,
    )
    for i in range(n):
        e = Entity(
            entity_id=uuid.uuid4(), entity_type="PUBLIC_COMPANY",
            legal_name=f"GICS Co {i}", status="ACTIVE", source="TEST",
            gics_sub_industry=gics, gics_industry=gics[:6],
            gics_industry_group=gics[:4], gics_sector=gics[:2],
        )
        session.add(e)
        await session.flush()
        for year, rev in [(2022, 100e6 * (i + 1)), (2023, 120e6 * (i + 1)), (2024, 150e6 * (i + 1))]:
            fp = FinancialPeriod(
                period_id=uuid.uuid4(), entity_id=e.entity_id,
                period_end_date=date(year, 12, 31), period_type="ANNUAL", fiscal_year=year,
            )
            session.add(fp)
            await session.flush()
            session.add(IncomeStatement(
                statement_id=uuid.uuid4(), period_id=fp.period_id,
                total_revenue=rev, cost_of_revenue=rev * 0.55, gross_profit=rev * 0.45,
                operating_income=rev * 0.2, net_income=rev * 0.14, ebitda=rev * 0.28,
            ))
            session.add(BalanceSheet(
                statement_id=uuid.uuid4(), period_id=fp.period_id,
                total_assets=rev * 1.5, total_debt=rev * 0.3, cash_and_equivalents=rev * 0.1,
                total_equity=rev * 0.9,
            ))
            session.add(CashFlowStatement(
                statement_id=uuid.uuid4(), period_id=fp.period_id,
                capital_expenditures=-rev * 0.06, free_cash_flow=rev * 0.15,
            ))
            await session.flush()
    await session.commit()


@pytest.mark.asyncio
async def test_industry_overview_computed(client: AsyncClient, session: AsyncSession):
    """GET /v3/industry/{gics}/overview computes a profile on-demand from the
    GICS member companies' fundamentals (was 404 forever, no writer)."""
    await _seed_gics_companies(session, gics="45102010", n=4)
    resp = await client.get("/v3/industry/45102010/overview")
    assert resp.status_code == 200
    data = resp.json()
    assert data["company_count"] == 4
    assert data["median_operating_margin"] is not None

    # Structure + cycle now compute too.
    struct = await client.get("/v3/industry/45102010/structure")
    assert struct.status_code == 200
    assert struct.json()["hhi_index"] is not None
    cycle = await client.get("/v3/industry/45102010/cycle")
    assert cycle.status_code == 200
    assert cycle.json()["cycle_position"] is not None
