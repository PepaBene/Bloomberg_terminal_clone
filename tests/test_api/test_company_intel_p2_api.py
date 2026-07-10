"""API tests for Company Intelligence P2 endpoints (Pillar 3 Phase 2)."""

import uuid
from datetime import date
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.entity import Entity
from src.models.fundamentals import (
    BalanceSheet,
    CashFlowStatement,
    FinancialPeriod,
    IncomeStatement,
)


async def _seed_entity_with_fundamentals(session: AsyncSession) -> Entity:
    entity = Entity(
        entity_id=uuid.uuid4(), entity_type="PUBLIC_COMPANY",
        legal_name="Deep Intel Test Corp", status="ACTIVE", source="TEST",
    )
    session.add(entity)
    await session.flush()

    for year, rev, opinc, ni, ebitda, cogs, da, debt, cash, ta, ca, cl, capex, fcf in [
        (2023, 500e6, 90e6, 60e6, 120e6, 300e6, 20e6, 200e6, 80e6, 900e6, 250e6, 150e6, -30e6, 65e6),
        (2024, 600e6, 120e6, 85e6, 150e6, 340e6, 22e6, 180e6, 120e6, 1000e6, 300e6, 140e6, -35e6, 95e6),
    ]:
        fp = FinancialPeriod(
            period_id=uuid.uuid4(), entity_id=entity.entity_id,
            period_end_date=date(year, 12, 31), period_type="ANNUAL", fiscal_year=year,
        )
        session.add(fp)
        await session.flush()
        session.add(IncomeStatement(
            statement_id=uuid.uuid4(), period_id=fp.period_id,
            total_revenue=rev, cost_of_revenue=cogs, gross_profit=rev - cogs,
            operating_income=opinc, net_income=ni, ebitda=ebitda,
            selling_general_admin=rev * 0.15, depreciation_amortization=da,
            interest_expense=8e6, diluted_eps=2.5, diluted_shares_outstanding=34e6,
        ))
        session.add(BalanceSheet(
            statement_id=uuid.uuid4(), period_id=fp.period_id,
            total_assets=ta, total_current_assets=ca, total_current_liabilities=cl,
            total_debt=debt, cash_and_equivalents=cash, total_equity=ta - debt - cl,
            accounts_receivable=rev * 0.12, inventory=cogs * 0.2, accounts_payable=cogs * 0.15,
        ))
        session.add(CashFlowStatement(
            statement_id=uuid.uuid4(), period_id=fp.period_id,
            capital_expenditures=capex, free_cash_flow=fcf, dividends_paid=-15e6,
        ))
        await session.flush()

    await session.commit()
    return entity


# ── Intelligence Report tests ────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_company_intelligence(client: AsyncClient, session: AsyncSession):
    """GET /v3/company/{entity_id}/intelligence returns 200 or 404."""
    resp = await client.get(f"/v3/company/{uuid4()}/intelligence")
    assert resp.status_code in (200, 404)


@pytest.mark.asyncio
async def test_intelligence_computed_from_fundamentals(client: AsyncClient, session: AsyncSession):
    """GET /v3/company/{id}/intelligence computes and persists all four deep
    assessments on-demand from real fundamentals (was always all-null)."""
    entity = await _seed_entity_with_fundamentals(session)

    resp = await client.get(f"/v3/company/{entity.entity_id}/intelligence")
    assert resp.status_code == 200
    data = resp.json()
    # All four sub-assessments are now populated (not None).
    assert data["business_model"] is not None
    assert data["capital_allocation"] is not None
    assert data["balance_sheet_risk"] is not None
    assert data["management_quality"] is not None
    # A real leverage figure was computed from the seeded debt/EBITDA.
    assert data["balance_sheet_risk"]["net_debt_ebitda"] is not None

    # The per-dimension endpoints now return data too (previously 404 forever).
    bm = await client.get(f"/v3/company/{entity.entity_id}/business-model")
    assert bm.status_code == 200
    bsr = await client.get(f"/v3/company/{entity.entity_id}/balance-sheet-risk")
    assert bsr.status_code == 200

    # Refresh recomputes and returns the report.
    refreshed = await client.post(f"/v3/company/{entity.entity_id}/intelligence/refresh")
    assert refreshed.status_code == 200


@pytest.mark.asyncio
async def test_get_company_intelligence_summary(client: AsyncClient, session: AsyncSession):
    """GET /v3/company/{entity_id}/intelligence/summary returns 200 or 404."""
    resp = await client.get(f"/v3/company/{uuid4()}/intelligence/summary")
    assert resp.status_code in (200, 404)


# ── Business Model tests ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_business_model(client: AsyncClient, session: AsyncSession):
    """GET /v3/company/{entity_id}/business-model returns 200 or 404."""
    resp = await client.get(f"/v3/company/{uuid4()}/business-model")
    assert resp.status_code in (200, 404)


@pytest.mark.asyncio
async def test_get_business_segments(client: AsyncClient, session: AsyncSession):
    """GET /v3/company/{entity_id}/business-model/segments returns 200 or 404."""
    resp = await client.get(f"/v3/company/{uuid4()}/business-model/segments")
    assert resp.status_code in (200, 404)


# ── Capital Allocation tests ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_capital_allocation(client: AsyncClient, session: AsyncSession):
    """GET /v3/company/{entity_id}/capital-allocation returns 200 or 404."""
    resp = await client.get(f"/v3/company/{uuid4()}/capital-allocation")
    assert resp.status_code in (200, 404)


@pytest.mark.asyncio
async def test_get_ma_history(client: AsyncClient, session: AsyncSession):
    """GET /v3/company/{entity_id}/capital-allocation/ma-history returns 200 or 404."""
    resp = await client.get(f"/v3/company/{uuid4()}/capital-allocation/ma-history")
    assert resp.status_code in (200, 404)


@pytest.mark.asyncio
async def test_get_buybacks(client: AsyncClient, session: AsyncSession):
    """GET /v3/company/{entity_id}/capital-allocation/buybacks returns 200 or 404."""
    resp = await client.get(f"/v3/company/{uuid4()}/capital-allocation/buybacks")
    assert resp.status_code in (200, 404)


# ── Management & Governance tests ────────────────────────────────────


@pytest.mark.asyncio
async def test_get_management_quality(client: AsyncClient, session: AsyncSession):
    """GET /v3/company/{entity_id}/management returns 200 or 404."""
    resp = await client.get(f"/v3/company/{uuid4()}/management")
    assert resp.status_code in (200, 404)


@pytest.mark.asyncio
async def test_get_governance(client: AsyncClient, session: AsyncSession):
    """GET /v3/company/{entity_id}/governance returns 200 or 404."""
    resp = await client.get(f"/v3/company/{uuid4()}/governance")
    assert resp.status_code in (200, 404)


@pytest.mark.asyncio
async def test_get_governance_red_flags(client: AsyncClient, session: AsyncSession):
    """GET /v3/company/{entity_id}/governance/red-flags returns 200 or 404."""
    resp = await client.get(f"/v3/company/{uuid4()}/governance/red-flags")
    assert resp.status_code in (200, 404)


# ── Balance Sheet Risk tests ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_balance_sheet_risk(client: AsyncClient, session: AsyncSession):
    """GET /v3/company/{entity_id}/balance-sheet-risk returns 200 or 404."""
    resp = await client.get(f"/v3/company/{uuid4()}/balance-sheet-risk")
    assert resp.status_code in (200, 404)


@pytest.mark.asyncio
async def test_get_debt_maturity(client: AsyncClient, session: AsyncSession):
    """GET /v3/company/{entity_id}/debt-maturity returns 200 or 404."""
    resp = await client.get(f"/v3/company/{uuid4()}/debt-maturity")
    assert resp.status_code in (200, 404)


@pytest.mark.asyncio
async def test_get_refinancing_risk(client: AsyncClient, session: AsyncSession):
    """GET /v3/company/{entity_id}/refinancing-risk returns 200 or 404."""
    resp = await client.get(f"/v3/company/{uuid4()}/refinancing-risk")
    assert resp.status_code in (200, 404)


# ── FI Profile tests ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_fi_profile(client: AsyncClient, session: AsyncSession):
    """GET /v3/company/{entity_id}/fi-profile returns 200 or 404."""
    resp = await client.get(f"/v3/company/{uuid4()}/fi-profile")
    assert resp.status_code in (200, 404)


@pytest.mark.asyncio
async def test_get_fi_bonds(client: AsyncClient, session: AsyncSession):
    """GET /v3/company/{entity_id}/fi-profile/bonds returns 200 or 404."""
    resp = await client.get(f"/v3/company/{uuid4()}/fi-profile/bonds")
    assert resp.status_code in (200, 404)


@pytest.mark.asyncio
async def test_get_fi_ratings(client: AsyncClient, session: AsyncSession):
    """GET /v3/company/{entity_id}/fi-profile/ratings returns 200 or 404."""
    resp = await client.get(f"/v3/company/{uuid4()}/fi-profile/ratings")
    assert resp.status_code in (200, 404)


@pytest.mark.asyncio
async def test_get_fi_maturity_wall(client: AsyncClient, session: AsyncSession):
    """GET /v3/company/{entity_id}/fi-profile/maturity-wall returns 200 or 404."""
    resp = await client.get(f"/v3/company/{uuid4()}/fi-profile/maturity-wall")
    assert resp.status_code in (200, 404)


@pytest.mark.asyncio
async def test_get_fi_market_cost_debt(client: AsyncClient, session: AsyncSession):
    """GET /v3/company/{entity_id}/fi-profile/market-cost-debt returns 200 or 404."""
    resp = await client.get(f"/v3/company/{uuid4()}/fi-profile/market-cost-debt")
    assert resp.status_code in (200, 404)
