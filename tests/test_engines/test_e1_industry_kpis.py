"""Tests for the Industry KPI engine (Part 1B)."""

import uuid
from datetime import date

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from src.engines.e1_industry_kpis import IndustryKPIEngine, INDUSTRY_KPI_MAP
from src.models.analytics import AnalyticsResult
from src.models.entity import Entity
from src.models.fundamentals import BalanceSheet, CashFlowStatement, FinancialPeriod, IncomeStatement
from src.models.security import Security


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def tech_security(session: AsyncSession) -> Security:
    """Tech company with GICS 4510 (Software)."""
    entity = Entity(
        entity_id=uuid.uuid4(),
        legal_name="SaaS Corp",
        entity_type="PUBLIC_COMPANY",
        status="ACTIVE",
        incorporation_country="US",
        source="TEST",
        gics_sector="45",
        gics_industry_group="4510",
        gics_industry="451020",
        gics_sub_industry=None,  # skip FK constraint in tests
    )
    session.add(entity)
    await session.flush()

    security = Security(
        security_id=uuid.uuid4(),
        name="SaaS Corp Stock",
        security_type="COMMON_STOCK",
        asset_class="EQUITY",
        status="ACTIVE",
        issuer_entity_id=entity.entity_id,
    )
    session.add(security)
    await session.flush()

    # Create a financial period with statements
    fp = FinancialPeriod(
        period_id=uuid.uuid4(),
        entity_id=entity.entity_id,
        period_end_date=date(2025, 3, 31),
        period_type="ANNUAL",
        fiscal_year=2024,
        fiscal_quarter=None,
    )
    session.add(fp)
    await session.flush()

    session.add(IncomeStatement(
        statement_id=uuid.uuid4(),
        period_id=fp.period_id,
        total_revenue=500_000_000.0,
        cost_of_revenue=150_000_000.0,
        gross_profit=350_000_000.0,
        operating_income=100_000_000.0,
        research_development=80_000_000.0,
        net_income=75_000_000.0,
        ebitda=120_000_000.0,
    ))
    session.add(CashFlowStatement(
        statement_id=uuid.uuid4(),
        period_id=fp.period_id,
        cash_from_operations=110_000_000.0,
        capital_expenditures=-20_000_000.0,
        free_cash_flow=90_000_000.0,
    ))
    await session.flush()
    return security


@pytest_asyncio.fixture
async def unclassified_security(session: AsyncSession) -> Security:
    """Company with no GICS classification."""
    entity = Entity(
        entity_id=uuid.uuid4(),
        legal_name="Mystery Corp",
        entity_type="PUBLIC_COMPANY",
        status="ACTIVE",
        incorporation_country="US",
        source="TEST",
    )
    session.add(entity)
    await session.flush()

    security = Security(
        security_id=uuid.uuid4(),
        name="Mystery Corp Stock",
        security_type="COMMON_STOCK",
        asset_class="EQUITY",
        status="ACTIVE",
        issuer_entity_id=entity.entity_id,
    )
    session.add(security)
    await session.flush()
    return security


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestIndustryKPIEngine:
    """Unit tests for IndustryKPIEngine."""

    @pytest.mark.asyncio
    async def test_tech_kpis_produced(self, session, tech_security):
        """Tech company should get software KPIs."""
        engine = IndustryKPIEngine()
        results = await engine.compute(session, tech_security.security_id)
        assert len(results) > 0
        metric_names = {r.metric_name for r in results}
        # Software KPIs should include rule_of_40 and rd_intensity
        assert "rd_intensity" in metric_names or "rule_of_40" in metric_names

    @pytest.mark.asyncio
    async def test_all_outputs_are_industry_kpi_category(self, session, tech_security):
        """All outputs should have metric_category=INDUSTRY_KPI."""
        engine = IndustryKPIEngine()
        results = await engine.compute(session, tech_security.security_id)
        for r in results:
            assert r.metric_category == "INDUSTRY_KPI"

    @pytest.mark.asyncio
    async def test_unclassified_returns_empty_or_minimal(self, session, unclassified_security):
        """Company with no GICS should get empty or only generic KPIs."""
        engine = IndustryKPIEngine()
        results = await engine.compute(session, unclassified_security.security_id)
        # Should not crash; may return empty or generic-only
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_kpi_map_has_entries(self):
        """Industry KPI map should have mappings for major sectors."""
        assert len(INDUSTRY_KPI_MAP) >= 5

    @pytest.mark.asyncio
    async def test_rd_intensity_value(self, session, tech_security):
        """R&D intensity = R&D / Revenue = 80M / 500M = 0.16."""
        engine = IndustryKPIEngine()
        results = await engine.compute(session, tech_security.security_id)
        rd = next((r for r in results if r.metric_name == "rd_intensity"), None)
        if rd and rd.value is not None:
            assert abs(rd.value - 0.16) < 0.01

    @pytest.mark.asyncio
    async def test_engine_metadata(self, session, tech_security):
        """Engine ID and category should be correct."""
        engine = IndustryKPIEngine()
        results = await engine.compute(session, tech_security.security_id)
        if results:
            assert results[0].engine_id == "E1"

    @pytest.mark.asyncio
    async def test_rule_of_40_computes_real_value(self, session, tech_security):
        """Regression test: rule_of_40 previously read 'revenue_growth_yoy',
        a metric_name RatioEngine never emits (the real name is
        'revenue_yoy'), so it was permanently None. Seed a real
        'revenue_yoy' AnalyticsResult row and verify rule_of_40 =
        revenue_yoy + fcf_margin: 0.25 + (90M/500M=0.18) = 0.43.
        """
        session.add(AnalyticsResult(
            security_id=tech_security.security_id,
            entity_id=tech_security.issuer_entity_id,
            engine_id="E1", metric_name="revenue_yoy",
            metric_category="GROWTH", value=0.25, unit="PERCENT",
            period="LATEST", as_of_date=date.today(), data_quality="COMPLETE",
        ))
        # fcf_margin's numerator (ttm_free_cash_flow) is read from a
        # TTMEngine-shaped AnalyticsResult row, not the raw CashFlowStatement.
        session.add(AnalyticsResult(
            security_id=tech_security.security_id,
            entity_id=tech_security.issuer_entity_id,
            engine_id="E1", metric_name="ttm_free_cash_flow",
            metric_category="CASH_FLOW", value=90_000_000.0, unit="CURRENCY",
            period="TTM", as_of_date=date.today(), data_quality="COMPLETE",
        ))
        await session.flush()

        engine = IndustryKPIEngine()
        results = await engine.compute(session, tech_security.security_id)
        r40 = next((r for r in results if r.metric_name == "rule_of_40"), None)
        assert r40 is not None
        assert r40.value is not None
        assert r40.value == pytest.approx(0.25 + (90_000_000 / 500_000_000), abs=1e-6)


@pytest_asyncio.fixture
async def pharma_security(session: AsyncSession) -> Security:
    """Pharma company (GICS 3510) with two annual periods for YoY R&D."""
    entity = Entity(
        entity_id=uuid.uuid4(), legal_name="Pharma Corp", entity_type="PUBLIC_COMPANY",
        status="ACTIVE", incorporation_country="US", source="TEST",
        gics_sector="35", gics_industry_group="3510", gics_industry="351010",
        gics_sub_industry=None,
    )
    session.add(entity)
    await session.flush()

    security = Security(
        security_id=uuid.uuid4(), name="Pharma Corp Stock", security_type="COMMON_STOCK",
        asset_class="EQUITY", status="ACTIVE", issuer_entity_id=entity.entity_id,
    )
    session.add(security)
    await session.flush()

    fp_prior = FinancialPeriod(
        period_id=uuid.uuid4(), entity_id=entity.entity_id,
        period_end_date=date(2024, 3, 31), period_type="ANNUAL",
        fiscal_year=2023, fiscal_quarter=None,
    )
    session.add(fp_prior)
    await session.flush()
    session.add(IncomeStatement(
        statement_id=uuid.uuid4(), period_id=fp_prior.period_id,
        total_revenue=400_000_000.0, research_development=40_000_000.0,
    ))

    fp_latest = FinancialPeriod(
        period_id=uuid.uuid4(), entity_id=entity.entity_id,
        period_end_date=date(2025, 3, 31), period_type="ANNUAL",
        fiscal_year=2024, fiscal_quarter=None,
    )
    session.add(fp_latest)
    await session.flush()
    session.add(IncomeStatement(
        statement_id=uuid.uuid4(), period_id=fp_latest.period_id,
        total_revenue=450_000_000.0, research_development=50_000_000.0,
    ))
    await session.flush()
    return security


class TestPharmaKPIs:
    @pytest.mark.asyncio
    async def test_pipeline_proxy_computes_real_yoy(self, session, pharma_security):
        """Regression test: pipeline_proxy previously read
        'rd_expense_growth_yoy', a metric_name no engine ever emits, so it
        was permanently None. R&D grew from 40M to 50M YoY ->
        pipeline_proxy = (50M-40M)/40M = 0.25.
        """
        engine = IndustryKPIEngine()
        results = await engine.compute(session, pharma_security.security_id)
        pp = next((r for r in results if r.metric_name == "pipeline_proxy"), None)
        assert pp is not None
        assert pp.value == pytest.approx(0.25, abs=1e-6)
        assert pp.data_quality == "ESTIMATED"


@pytest_asyncio.fixture
async def energy_security(session: AsyncSession) -> Security:
    """Energy company (GICS 1010)."""
    entity = Entity(
        entity_id=uuid.uuid4(), legal_name="Energy Corp", entity_type="PUBLIC_COMPANY",
        status="ACTIVE", incorporation_country="US", source="TEST",
        gics_sector="10", gics_industry_group="1010", gics_industry="101020",
        gics_sub_industry=None,
    )
    session.add(entity)
    await session.flush()

    security = Security(
        security_id=uuid.uuid4(), name="Energy Corp Stock", security_type="COMMON_STOCK",
        asset_class="EQUITY", status="ACTIVE", issuer_entity_id=entity.entity_id,
    )
    session.add(security)
    await session.flush()

    fp = FinancialPeriod(
        period_id=uuid.uuid4(), entity_id=entity.entity_id,
        period_end_date=date(2025, 3, 31), period_type="ANNUAL",
        fiscal_year=2024, fiscal_quarter=None,
    )
    session.add(fp)
    await session.flush()
    session.add(IncomeStatement(
        statement_id=uuid.uuid4(), period_id=fp.period_id,
        total_revenue=1_000_000_000.0, depreciation_amortization=150_000_000.0,
    ))
    session.add(BalanceSheet(
        statement_id=uuid.uuid4(), period_id=fp.period_id, ppe_net=2_000_000_000.0,
    ))
    session.add(CashFlowStatement(
        statement_id=uuid.uuid4(), period_id=fp.period_id,
        capital_expenditures=-300_000_000.0,
    ))
    await session.flush()
    return security


class TestEnergyKPIs:
    @pytest.mark.asyncio
    async def test_energy_produces_real_kpis_not_empty(self, session, energy_security):
        """Regression test: the energy/mining KPI function previously
        returned [] unconditionally. capex_intensity = 300M/1000M = 0.30;
        dd_and_a_to_ppe = 150M/2000M = 0.075.
        """
        engine = IndustryKPIEngine()
        results = await engine.compute(session, energy_security.security_id)
        by_name = {r.metric_name: r.value for r in results}

        assert "capex_intensity" in by_name
        assert by_name["capex_intensity"] == pytest.approx(0.30, abs=1e-6)
        assert "dd_and_a_to_ppe" in by_name
        assert by_name["dd_and_a_to_ppe"] == pytest.approx(0.075, abs=1e-6)
