"""Tests for the DuPont Decomposition engine."""

import uuid
from datetime import date

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from src.engines.e1_dupont import DuPontEngine
from src.models.entity import Entity
from src.models.fundamentals import BalanceSheet, FinancialPeriod, IncomeStatement
from src.models.security import Security


@pytest_asyncio.fixture
async def seeded_security_dupont(session: AsyncSession) -> Security:
    """Create a security with fundamentals suitable for DuPont decomposition."""
    entity = Entity(
        entity_id=uuid.uuid4(),
        legal_name="DuPont Test Corp",
        entity_type="PUBLIC_COMPANY",
        status="ACTIVE",
        incorporation_country="US",
        source="TEST",
    )
    session.add(entity)
    await session.flush()

    security = Security(
        security_id=uuid.uuid4(),
        name="DuPont Test Corp Common Stock",
        security_type="COMMON_STOCK",
        asset_class="EQUITY",
        status="ACTIVE",
        issuer_entity_id=entity.entity_id,
    )
    session.add(security)
    await session.flush()

    fp = FinancialPeriod(
        period_id=uuid.uuid4(),
        entity_id=entity.entity_id,
        period_end_date=date(2025, 3, 31),
        period_type="QUARTERLY",
        fiscal_year=2025,
        fiscal_quarter=1,
    )
    session.add(fp)
    await session.flush()

    # Known values for deterministic testing
    # ROE = 72M / 200M = 0.36
    # 3-factor: (72/400) × (400/1000) × (1000/200) = 0.18 × 0.40 × 5.0 = 0.36 ✓
    session.add(IncomeStatement(
        statement_id=uuid.uuid4(),
        period_id=fp.period_id,
        total_revenue=400_000_000.0,
        operating_income=100_000_000.0,
        pretax_income=90_000_000.0,
        net_income=72_000_000.0,
    ))
    session.add(BalanceSheet(
        statement_id=uuid.uuid4(),
        period_id=fp.period_id,
        total_assets=1_000_000_000.0,
        total_equity=200_000_000.0,
    ))
    await session.flush()

    return security


@pytest.mark.asyncio
async def test_three_factor_decomposition(session: AsyncSession, seeded_security_dupont: Security):
    """3-factor: margin × turnover × multiplier should ≈ ROE."""
    engine = DuPontEngine()
    results = await engine.compute(session, security_id=seeded_security_dupont.security_id)

    by_name = {r.metric_name: r.value for r in results}

    margin = by_name.get("dupont_net_profit_margin")
    turnover = by_name.get("dupont_asset_turnover")
    multiplier = by_name.get("dupont_equity_multiplier")

    assert margin is not None
    assert turnover is not None
    assert multiplier is not None

    # margin = 72/400 = 0.18, turnover = 400/1000 = 0.40, mult = 1000/200 = 5.0
    assert margin == pytest.approx(0.18, abs=0.01)
    assert turnover == pytest.approx(0.40, abs=0.01)
    assert multiplier == pytest.approx(5.0, abs=0.1)

    # Product should equal ROE
    computed_roe = margin * turnover * multiplier
    assert computed_roe == pytest.approx(0.36, abs=0.01)


@pytest.mark.asyncio
async def test_five_factor_decomposition(session: AsyncSession, seeded_security_dupont: Security):
    """5-factor should also decompose ROE."""
    engine = DuPontEngine()
    results = await engine.compute(session, security_id=seeded_security_dupont.security_id)

    by_name = {r.metric_name: r.value for r in results}

    tax_burden = by_name.get("dupont_tax_burden")  # 72/90 = 0.80
    interest_burden = by_name.get("dupont_interest_burden")  # 90/100 = 0.90
    op_margin = by_name.get("dupont_operating_margin")  # 100/400 = 0.25

    assert tax_burden is not None
    assert interest_burden is not None
    assert op_margin is not None

    assert tax_burden == pytest.approx(0.80, abs=0.01)
    assert interest_burden == pytest.approx(0.90, abs=0.01)
    assert op_margin == pytest.approx(0.25, abs=0.01)


@pytest.mark.asyncio
async def test_both_models_returned(session: AsyncSession, seeded_security_dupont: Security):
    """Should produce outputs for both 3-factor and 5-factor components."""
    engine = DuPontEngine()
    results = await engine.compute(session, security_id=seeded_security_dupont.security_id)
    names = {r.metric_name for r in results}
    # 3-factor
    assert "dupont_net_profit_margin" in names
    assert "dupont_asset_turnover" in names
    assert "dupont_equity_multiplier" in names
    # 5-factor
    assert "dupont_tax_burden" in names
    assert "dupont_interest_burden" in names
    assert "dupont_operating_margin" in names


@pytest.mark.asyncio
async def test_roe_uses_ttm_flow_not_single_quarter(session: AsyncSession):
    """Regression test: ROE flows must be summed over the trailing 4
    quarters, not read from a single quarter.

    Seeds 4 quarters each with net_income=18M / total_revenue=100M
    (so TTM net_income=72M, TTM total_revenue=400M -- identical totals to
    the single-quarter fixture above) against a single latest-quarter
    balance sheet (total_assets=1B, total_equity=200M). Before the fix,
    reading only the latest quarter's flows (18M / 100M) against the full
    balance sheet understated margin/turnover/ROE by ~4x versus this TTM
    figure (margin 0.18 vs the buggy 0.18/4-scale... concretely: buggy ROE
    = 18M/200M = 0.09, correct ROE = 72M/200M = 0.36).
    """
    entity = Entity(
        entity_id=uuid.uuid4(),
        legal_name="DuPont TTM Test Corp",
        entity_type="PUBLIC_COMPANY",
        status="ACTIVE",
        incorporation_country="US",
        source="TEST",
    )
    session.add(entity)
    await session.flush()

    security = Security(
        security_id=uuid.uuid4(),
        name="DuPont TTM Test Corp Common Stock",
        security_type="COMMON_STOCK",
        asset_class="EQUITY",
        status="ACTIVE",
        issuer_entity_id=entity.entity_id,
    )
    session.add(security)
    await session.flush()

    quarter_ends = [date(2025, 3, 31), date(2024, 12, 31), date(2024, 9, 30), date(2024, 6, 30)]
    for i, end_date in enumerate(quarter_ends):
        fp = FinancialPeriod(
            period_id=uuid.uuid4(),
            entity_id=entity.entity_id,
            period_end_date=end_date,
            period_type="QUARTERLY",
            fiscal_year=2025 if i == 0 else 2024,
            fiscal_quarter=1 if i == 0 else 4 - i,
        )
        session.add(fp)
        await session.flush()

        session.add(IncomeStatement(
            statement_id=uuid.uuid4(),
            period_id=fp.period_id,
            total_revenue=100_000_000.0,
            operating_income=25_000_000.0,
            pretax_income=22_500_000.0,
            net_income=18_000_000.0,
        ))
        # Only the latest quarter needs a balance sheet (DuPont uses the
        # most recent quarter with BOTH statements as its BS anchor).
        if i == 0:
            session.add(BalanceSheet(
                statement_id=uuid.uuid4(),
                period_id=fp.period_id,
                total_assets=1_000_000_000.0,
                total_equity=200_000_000.0,
            ))
        await session.flush()

    engine = DuPontEngine()
    results = await engine.compute(session, security_id=security.security_id)
    by_name = {r.metric_name: r.value for r in results}

    # TTM net_income = 4*18M = 72M, TTM total_revenue = 4*100M = 400M.
    assert by_name["dupont_net_profit_margin"] == pytest.approx(72_000_000 / 400_000_000)
    assert by_name["dupont_asset_turnover"] == pytest.approx(400_000_000 / 1_000_000_000)
    assert by_name["dupont_equity_multiplier"] == pytest.approx(1_000_000_000 / 200_000_000)
    assert by_name["dupont_roe_3f"] == pytest.approx(72_000_000 / 200_000_000)
    assert by_name["dupont_roe_direct"] == pytest.approx(72_000_000 / 200_000_000)


@pytest.mark.asyncio
async def test_missing_data_returns_empty(session: AsyncSession):
    """No data at all should return empty list."""
    engine = DuPontEngine()
    results = await engine.compute(session, security_id=uuid.uuid4())
    assert results == []


@pytest.mark.asyncio
async def test_engine_metadata(session: AsyncSession, seeded_security_dupont: Security):
    """All outputs should carry correct engine metadata."""
    engine = DuPontEngine()
    results = await engine.compute(session, security_id=seeded_security_dupont.security_id)
    for r in results:
        assert r.engine_id == "E1"
        assert r.metric_category == "DUPONT"
        assert r.security_id == seeded_security_dupont.security_id
