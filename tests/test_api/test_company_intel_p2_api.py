"""API tests for Company Intelligence P2 endpoints (Pillar 3 Phase 2)."""

import uuid
from datetime import date
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select
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


# ── Previously-missing endpoints: real backend implementations ────────


async def _seed_segments(session: AsyncSession, entity: Entity, periods: list) -> None:
    """Seed BUSINESS + GEOGRAPHIC segments across the entity's periods,
    with a clearly growing and a clearly shrinking product segment."""
    from src.models.fundamentals import SegmentData

    growth = [180e6, 260e6]  # grows YoY
    drag = [140e6, 90e6]  # shrinks YoY
    for period, g_rev, d_rev in zip(periods, growth, drag):
        session.add(SegmentData(
            segment_id=uuid.uuid4(), period_id=period.period_id, entity_id=entity.entity_id,
            segment_type="BUSINESS", segment_name="Cloud", revenue=g_rev,
        ))
        session.add(SegmentData(
            segment_id=uuid.uuid4(), period_id=period.period_id, entity_id=entity.entity_id,
            segment_type="BUSINESS", segment_name="Legacy", revenue=d_rev,
        ))
        session.add(SegmentData(
            segment_id=uuid.uuid4(), period_id=period.period_id, entity_id=entity.entity_id,
            segment_type="GEOGRAPHIC", segment_name="Americas", revenue=(g_rev + d_rev) * 0.6,
        ))
    await session.commit()


@pytest.mark.asyncio
async def test_get_revenue_drivers_404_no_fundamentals(client: AsyncClient, session: AsyncSession):
    """GET /v3/company/{entity_id}/revenue-drivers 404s with no fundamentals."""
    resp = await client.get(f"/v3/company/{uuid4()}/revenue-drivers")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_revenue_drivers_real_segment_decomposition(client: AsyncClient, session: AsyncSession):
    """GET /v3/company/{entity_id}/revenue-drivers returns real per-segment
    growth decomposition, not a placeholder -- a growing segment is
    classified GROWTH_DRIVER, a shrinking one DRAG."""
    entity = await _seed_entity_with_fundamentals(session)
    periods = (
        await session.execute(
            select(FinancialPeriod)
            .where(FinancialPeriod.entity_id == entity.entity_id)
            .order_by(FinancialPeriod.period_end_date.asc())
        )
    ).scalars().all()
    await _seed_segments(session, entity, periods)

    resp = await client.get(f"/v3/company/{entity.entity_id}/revenue-drivers")
    assert resp.status_code == 200
    data = resp.json()
    assert data["periods_analyzed"] == 2
    by_name = {d["segment_name"]: d for d in data["drivers"]}
    assert by_name["Cloud"]["classification"] == "GROWTH_DRIVER"
    assert by_name["Legacy"]["classification"] == "DRAG"
    # Geographic segments are excluded from the drivers list.
    assert "Americas" not in by_name
    assert data["revenue_concentration_hhi"] is not None


@pytest.mark.asyncio
async def test_get_cost_structure_404_no_fundamentals(client: AsyncClient, session: AsyncSession):
    resp = await client.get(f"/v3/company/{uuid4()}/cost-structure")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_cost_structure_real_trend(client: AsyncClient, session: AsyncSession):
    """GET /v3/company/{entity_id}/cost-structure returns real COGS/SG&A
    percent-of-revenue figures derived from seeded fundamentals."""
    entity = await _seed_entity_with_fundamentals(session)
    resp = await client.get(f"/v3/company/{entity.entity_id}/cost-structure")
    assert resp.status_code == 200
    data = resp.json()
    assert data["periods_analyzed"] == 2
    by_cat = {i["category"]: i for i in data["items"]}
    # 2024: cogs=340e6, revenue=600e6 -> 56.67%
    assert by_cat["COGS"]["pct_of_revenue"] == pytest.approx(56.67, abs=0.1)
    assert by_cat["SG&A"]["pct_of_revenue"] is not None


@pytest.mark.asyncio
async def test_get_margin_analysis_404_no_fundamentals(client: AsyncClient, session: AsyncSession):
    resp = await client.get(f"/v3/company/{uuid4()}/margin-analysis")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_margin_analysis_real_trend(client: AsyncClient, session: AsyncSession):
    """GET /v3/company/{entity_id}/margin-analysis returns real gross/
    operating/net margin figures, not a placeholder."""
    entity = await _seed_entity_with_fundamentals(session)
    resp = await client.get(f"/v3/company/{entity.entity_id}/margin-analysis")
    assert resp.status_code == 200
    data = resp.json()
    assert data["periods_analyzed"] == 2
    by_metric = {m["metric"]: m for m in data["margins"]}
    # 2024: opinc=120e6, revenue=600e6 -> 20.0%
    assert by_metric["operating_margin"]["current_pct"] == pytest.approx(20.0, abs=0.1)
    assert by_metric["operating_margin"]["trend"] in ("EXPANDING", "STABLE")


@pytest.mark.asyncio
async def test_get_growth_profile_404_no_fundamentals(client: AsyncClient, session: AsyncSession):
    resp = await client.get(f"/v3/company/{uuid4()}/growth-profile")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_growth_profile_real_yoy(client: AsyncClient, session: AsyncSession):
    """GET /v3/company/{entity_id}/growth-profile returns real YoY growth
    for revenue/net_income/eps/fcf from seeded fundamentals."""
    entity = await _seed_entity_with_fundamentals(session)
    resp = await client.get(f"/v3/company/{entity.entity_id}/growth-profile")
    assert resp.status_code == 200
    data = resp.json()
    assert data["periods_analyzed"] == 2
    by_metric = {s["metric"]: s for s in data["growth_series"]}
    # revenue: 500e6 -> 600e6 = +20%
    assert by_metric["revenue"]["latest_yoy_growth_pct"] == pytest.approx(20.0, abs=0.1)


@pytest.mark.asyncio
async def test_get_operating_leverage_404_no_fundamentals(client: AsyncClient, session: AsyncSession):
    resp = await client.get(f"/v3/company/{uuid4()}/operating-leverage")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_operating_leverage_real_trend(client: AsyncClient, session: AsyncSession):
    entity = await _seed_entity_with_fundamentals(session)
    resp = await client.get(f"/v3/company/{entity.entity_id}/operating-leverage")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["operating_leverage_trend"]) >= 1


@pytest.mark.asyncio
async def test_get_quality_metrics_404_no_data(client: AsyncClient, session: AsyncSession):
    resp = await client.get(f"/v3/company/{uuid4()}/quality-metrics")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_quality_metrics_real_scores(client: AsyncClient, session: AsyncSession):
    """GET /v3/company/{entity_id}/quality-metrics re-exposes real,
    already-computed Piotroski/Altman/Beneish scores."""
    from src.models.analytics import AnalyticsResult
    from src.models.security import Security

    entity = await _seed_entity_with_fundamentals(session)
    security = Security(
        security_id=uuid.uuid4(), name="Quality Test Corp Common Stock",
        security_type="COMMON_STOCK", asset_class="EQUITY", status="ACTIVE",
        issuer_entity_id=entity.entity_id,
    )
    session.add(security)
    await session.flush()
    today = date.today()
    for name, val in [("piotroski_f_score", 8.0), ("altman_z_score", 3.5), ("beneish_m_score", -2.1)]:
        session.add(AnalyticsResult(
            result_id=uuid.uuid4(), security_id=security.security_id, entity_id=entity.entity_id,
            engine_id="E3", metric_name=name, metric_category="QUALITY", value=val,
            period="TTM", as_of_date=today,
        ))
    await session.commit()

    resp = await client.get(f"/v3/company/{entity.entity_id}/quality-metrics")
    assert resp.status_code == 200
    data = resp.json()
    assert data["piotroski_f_score"] == 8.0
    assert data["altman_z_score"] == 3.5
    assert data["beneish_m_score"] == -2.1


@pytest.mark.asyncio
async def test_get_risk_profile_404_no_signals(client: AsyncClient, session: AsyncSession):
    resp = await client.get(f"/v3/company/{uuid4()}/risk-profile")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_risk_profile_real_composite(client: AsyncClient, session: AsyncSession):
    """GET /v3/company/{entity_id}/risk-profile combines real, already-
    computed signals (z-score from the balance-sheet-risk assessment) into
    a composite risk view."""
    entity = await _seed_entity_with_fundamentals(session)
    # Trigger real computation/persistence of BalanceSheetRiskAssessment.
    intel_resp = await client.get(f"/v3/company/{entity.entity_id}/intelligence")
    assert intel_resp.status_code == 200

    resp = await client.get(f"/v3/company/{entity.entity_id}/risk-profile")
    assert resp.status_code == 200
    data = resp.json()
    assert data["overall_risk_tier"] in ("LOW", "MODERATE", "ELEVATED", "HIGH")
    assert data["data_completeness"] > 0.0


@pytest.mark.asyncio
async def test_get_working_capital_404_no_assessment(client: AsyncClient, session: AsyncSession):
    resp = await client.get(f"/v3/company/{uuid4()}/working-capital")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_working_capital_real_ccc(client: AsyncClient, session: AsyncSession):
    """GET /v3/company/{entity_id}/working-capital exposes the real
    CCC/DIO/DSO/DPO breakdown already computed by the capital-allocation
    engine."""
    entity = await _seed_entity_with_fundamentals(session)
    intel_resp = await client.get(f"/v3/company/{entity.entity_id}/intelligence")
    assert intel_resp.status_code == 200

    resp = await client.get(f"/v3/company/{entity.entity_id}/working-capital")
    assert resp.status_code == 200
    data = resp.json()
    assert data["working_capital"] is not None
    assert "ccc" in data["working_capital"]


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
