"""Tests for E3 Quality Scoring engines (Piotroski, Altman, Beneish)."""

import uuid
from datetime import date

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.entity import Entity
from src.models.fundamentals import (
    BalanceSheet,
    CashFlowStatement,
    FinancialPeriod,
    IncomeStatement,
)
from src.models.security import Security


# ---------------------------------------------------------------------------
# Fixtures — seeded entity with 2 annual periods for YoY comparison
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def entity_for_scores(session: AsyncSession) -> Entity:
    """Entity with GICS classification for Altman model selection."""
    entity = Entity(
        entity_id=uuid.uuid4(),
        legal_name="Quality Score Test Corp",
        entity_type="PUBLIC_COMPANY",
        status="ACTIVE",
        incorporation_country="US",
        gics_sector="45",
        gics_sub_industry="45103010",
        source="TEST",
    )
    session.add(entity)
    await session.flush()
    return entity


@pytest_asyncio.fixture
async def security_for_scores(session: AsyncSession, entity_for_scores: Entity) -> Security:
    security = Security(
        security_id=uuid.uuid4(),
        name="Quality Score Test Corp Common Stock",
        security_type="COMMON_STOCK",
        asset_class="EQUITY",
        status="ACTIVE",
        issuer_entity_id=entity_for_scores.entity_id,
    )
    session.add(security)
    await session.flush()
    return security


@pytest_asyncio.fixture
async def two_annual_periods(
    session: AsyncSession,
    entity_for_scores: Entity,
) -> tuple[FinancialPeriod, FinancialPeriod]:
    """Create two annual financial periods with full statements."""
    # Prior year
    fp_prior = FinancialPeriod(
        period_id=uuid.uuid4(),
        entity_id=entity_for_scores.entity_id,
        period_end_date=date(2023, 12, 31),
        period_type="ANNUAL",
        fiscal_year=2023,
        fiscal_quarter=None,
    )
    session.add(fp_prior)
    await session.flush()

    session.add(IncomeStatement(
        statement_id=uuid.uuid4(),
        period_id=fp_prior.period_id,
        total_revenue=500_000_000.0,
        cost_of_revenue=300_000_000.0,
        gross_profit=200_000_000.0,
        operating_income=80_000_000.0,
        pretax_income=70_000_000.0,
        net_income=56_000_000.0,
        selling_general_admin=70_000_000.0,
        depreciation_amortization=20_000_000.0,
        diluted_shares_outstanding=50_000_000.0,
    ))
    session.add(BalanceSheet(
        statement_id=uuid.uuid4(),
        period_id=fp_prior.period_id,
        total_assets=800_000_000.0,
        total_current_assets=250_000_000.0,
        total_current_liabilities=150_000_000.0,
        total_liabilities=500_000_000.0,
        total_equity=300_000_000.0,
        total_debt=200_000_000.0,
        long_term_debt=180_000_000.0,
        retained_earnings=150_000_000.0,
        accounts_receivable=60_000_000.0,
        ppe_net=200_000_000.0,
        working_capital=100_000_000.0,
    ))
    session.add(CashFlowStatement(
        statement_id=uuid.uuid4(),
        period_id=fp_prior.period_id,
        cash_from_operations=70_000_000.0,
        depreciation_amortization=20_000_000.0,
    ))
    await session.flush()

    # Current year — improved fundamentals for Piotroski scoring
    fp_current = FinancialPeriod(
        period_id=uuid.uuid4(),
        entity_id=entity_for_scores.entity_id,
        period_end_date=date(2024, 12, 31),
        period_type="ANNUAL",
        fiscal_year=2024,
        fiscal_quarter=None,
    )
    session.add(fp_current)
    await session.flush()

    session.add(IncomeStatement(
        statement_id=uuid.uuid4(),
        period_id=fp_current.period_id,
        total_revenue=600_000_000.0,
        cost_of_revenue=340_000_000.0,
        gross_profit=260_000_000.0,  # margin improved: 43.3% vs 40%
        operating_income=110_000_000.0,
        pretax_income=100_000_000.0,
        net_income=80_000_000.0,  # positive → F1=1
        selling_general_admin=80_000_000.0,
        depreciation_amortization=22_000_000.0,
        diluted_shares_outstanding=50_000_000.0,  # no dilution
    ))
    session.add(BalanceSheet(
        statement_id=uuid.uuid4(),
        period_id=fp_current.period_id,
        total_assets=900_000_000.0,
        total_current_assets=300_000_000.0,  # current ratio improved
        total_current_liabilities=140_000_000.0,
        total_liabilities=530_000_000.0,
        total_equity=370_000_000.0,
        total_debt=180_000_000.0,  # deleveraged from 200M
        long_term_debt=160_000_000.0,  # decreased
        retained_earnings=220_000_000.0,
        accounts_receivable=70_000_000.0,
        ppe_net=220_000_000.0,
        working_capital=160_000_000.0,  # 300M - 140M
    ))
    session.add(CashFlowStatement(
        statement_id=uuid.uuid4(),
        period_id=fp_current.period_id,
        cash_from_operations=95_000_000.0,  # positive → F2=1, > net income → F4=1
        depreciation_amortization=22_000_000.0,
    ))
    await session.flush()

    return fp_prior, fp_current


# ---------------------------------------------------------------------------
# Piotroski F-Score Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_piotroski_full_score(
    session: AsyncSession,
    security_for_scores: Security,
    two_annual_periods: tuple,
):
    """Full Piotroski computation with all 9 components."""
    from src.engines.e3_piotroski import PiotroskiEngine

    engine = PiotroskiEngine()
    results = await engine.compute(session, security_id=security_for_scores.security_id)

    by_name = {r.metric_name: r.value for r in results}
    assert "piotroski_f_score" in by_name
    score = by_name["piotroski_f_score"]
    assert score is not None
    assert 0 <= score <= 9

    # Check individual components are present
    for i in range(1, 10):
        key = f"piotroski_f{i}_"
        matching = [k for k in by_name if k.startswith(key)]
        assert len(matching) >= 1, f"Missing component F{i}"

    # F1: net_income > 0 → should be 1
    assert by_name.get("piotroski_f1_positive_income") == 1
    # F2: OCF > 0 → should be 1
    assert by_name.get("piotroski_f2_positive_ocf") == 1
    # F4: OCF > net_income (95M > 80M) → should be 1
    assert by_name.get("piotroski_f4_earnings_quality") == 1


@pytest.mark.asyncio
async def test_piotroski_zone_classification(
    session: AsyncSession,
    security_for_scores: Security,
    two_annual_periods: tuple,
):
    """Zone should be STRONG, MODERATE, or WEAK based on score."""
    from src.engines.e3_piotroski import PiotroskiEngine

    engine = PiotroskiEngine()
    results = await engine.compute(session, security_id=security_for_scores.security_id)

    by_name = {r.metric_name: r for r in results}
    zone_output = by_name.get("piotroski_zone")
    assert zone_output is not None
    # Zone is stored in inputs with name="zone", the label is in the "period" field
    zone_label = None
    if zone_output.inputs:
        for inp in zone_output.inputs:
            if inp.get("name") == "zone":
                zone_label = inp.get("period")
    assert zone_label in ("STRONG", "MODERATE", "WEAK")


@pytest.mark.asyncio
async def test_piotroski_engine_id(
    session: AsyncSession,
    security_for_scores: Security,
    two_annual_periods: tuple,
):
    """All outputs should use engine_id E3."""
    from src.engines.e3_piotroski import PiotroskiEngine

    engine = PiotroskiEngine()
    results = await engine.compute(session, security_id=security_for_scores.security_id)
    for r in results:
        assert r.engine_id == "E3"
        assert r.metric_category == "QUALITY"


@pytest.mark.asyncio
async def test_piotroski_no_data(session: AsyncSession, security_for_scores: Security):
    """No financial data → empty results."""
    from src.engines.e3_piotroski import PiotroskiEngine

    engine = PiotroskiEngine()
    results = await engine.compute(session, security_id=security_for_scores.security_id)
    # No annual periods seeded (fixture not used) → empty or INSUFFICIENT_DATA
    assert len(results) == 0 or all(r.data_quality == "INSUFFICIENT_DATA" for r in results)


# ---------------------------------------------------------------------------
# Altman Z-Score Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_altman_non_manufacturing(
    session: AsyncSession,
    security_for_scores: Security,
    two_annual_periods: tuple,
):
    """IT company should use Z'-Score (non-manufacturing model)."""
    from src.engines.e3_altman import AltmanZScoreEngine as AltmanEngine

    engine = AltmanEngine()
    results = await engine.compute(session, security_id=security_for_scores.security_id)

    by_name = {r.metric_name: r for r in results}
    assert "altman_z_score" in by_name
    z = by_name["altman_z_score"].value
    assert z is not None

    # Check model type is NON_MANUFACTURING (IT company, GICS 45)
    model_output = by_name.get("altman_model")
    assert model_output is not None
    assert model_output.data_quality == "NON_MANUFACTURING"


@pytest.mark.asyncio
async def test_altman_zone_classification(
    session: AsyncSession,
    security_for_scores: Security,
    two_annual_periods: tuple,
):
    """Z-Score should produce SAFE, GREY, or DISTRESS zone."""
    from src.engines.e3_altman import AltmanZScoreEngine as AltmanEngine

    engine = AltmanEngine()
    results = await engine.compute(session, security_id=security_for_scores.security_id)

    by_name = {r.metric_name: r for r in results}
    zone_output = by_name.get("altman_zone")
    assert zone_output is not None
    assert zone_output.data_quality in ("SAFE", "GREY", "DISTRESS", "NOT_APPLICABLE")


@pytest.mark.asyncio
async def test_altman_components_present(
    session: AsyncSession,
    security_for_scores: Security,
    two_annual_periods: tuple,
):
    """All X1-X4 components should be computed."""
    from src.engines.e3_altman import AltmanZScoreEngine as AltmanEngine

    engine = AltmanEngine()
    results = await engine.compute(session, security_id=security_for_scores.security_id)

    by_name = {r.metric_name: r.value for r in results}
    for comp in ["altman_x1_wc_ta", "altman_x2_re_ta", "altman_x3_ebit_ta", "altman_x4_value"]:
        assert comp in by_name, f"Missing component {comp}"
        assert by_name[comp] is not None, f"Component {comp} is None"


@pytest.mark.asyncio
async def test_altman_financial_sector_excluded(session: AsyncSession):
    """Financial sector companies should return NOT_APPLICABLE."""
    from src.engines.e3_altman import AltmanZScoreEngine as AltmanEngine

    entity = Entity(
        entity_id=uuid.uuid4(),
        legal_name="Test Bank Corp",
        entity_type="PUBLIC_COMPANY",
        status="ACTIVE",
        incorporation_country="US",
        gics_sector="40",
        source="TEST",
    )
    session.add(entity)
    await session.flush()

    security = Security(
        security_id=uuid.uuid4(),
        name="Test Bank Common Stock",
        security_type="COMMON_STOCK",
        asset_class="EQUITY",
        status="ACTIVE",
        issuer_entity_id=entity.entity_id,
    )
    session.add(security)
    await session.flush()

    engine = AltmanEngine()
    results = await engine.compute(session, security_id=security.security_id)

    by_name = {r.metric_name: r for r in results}
    zone_output = by_name.get("altman_zone")
    if zone_output:
        assert zone_output.data_quality == "NOT_APPLICABLE"


# ---------------------------------------------------------------------------
# Beneish M-Score Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_beneish_full_computation(
    session: AsyncSession,
    security_for_scores: Security,
    two_annual_periods: tuple,
):
    """Full Beneish computation with all 8 components."""
    from src.engines.e3_beneish import BeneishEngine

    engine = BeneishEngine()
    results = await engine.compute(session, security_id=security_for_scores.security_id)

    by_name = {r.metric_name: r.value for r in results}
    assert "beneish_m_score" in by_name
    m_score = by_name["beneish_m_score"]
    # M-Score should be a number (could be positive or negative)
    assert m_score is not None
    assert isinstance(m_score, float)


@pytest.mark.asyncio
async def test_beneish_flag_classification(
    session: AsyncSession,
    security_for_scores: Security,
    two_annual_periods: tuple,
):
    """Flag should be POSSIBLE_MANIPULATOR or UNLIKELY_MANIPULATOR."""
    from src.engines.e3_beneish import BeneishEngine

    engine = BeneishEngine()
    results = await engine.compute(session, security_id=security_for_scores.security_id)

    by_name = {r.metric_name: r for r in results}
    flag_output = by_name.get("beneish_flag")
    assert flag_output is not None
    # Flag label is in inputs with name="classification", stored in "filing_source"
    flag_label = None
    if flag_output.inputs:
        for inp in flag_output.inputs:
            if inp.get("name") == "classification":
                flag_label = inp.get("filing_source")
    assert flag_label in ("POSSIBLE_MANIPULATOR", "UNLIKELY_MANIPULATOR")


@pytest.mark.asyncio
async def test_beneish_components_present(
    session: AsyncSession,
    security_for_scores: Security,
    two_annual_periods: tuple,
):
    """All 8 M-Score components should be computed."""
    from src.engines.e3_beneish import BeneishEngine

    engine = BeneishEngine()
    results = await engine.compute(session, security_id=security_for_scores.security_id)

    by_name = {r.metric_name: r.value for r in results}
    components = ["beneish_dsri", "beneish_gmi", "beneish_aqi", "beneish_sgi",
                  "beneish_depi", "beneish_sgai", "beneish_tata", "beneish_lvgi"]
    present = sum(1 for c in components if c in by_name and by_name[c] is not None)
    # At least 6 of 8 components should be non-None with our test data
    assert present >= 6, f"Only {present}/8 components present"

    # components_available should match
    assert by_name.get("beneish_components_available") == present


@pytest.mark.asyncio
async def test_beneish_no_prior_year(session: AsyncSession):
    """No prior year data → insufficient data."""
    from src.engines.e3_beneish import BeneishEngine

    entity = Entity(
        entity_id=uuid.uuid4(),
        legal_name="New IPO Corp",
        entity_type="PUBLIC_COMPANY",
        status="ACTIVE",
        incorporation_country="US",
        source="TEST",
    )
    session.add(entity)
    await session.flush()

    security = Security(
        security_id=uuid.uuid4(),
        name="New IPO Common Stock",
        security_type="COMMON_STOCK",
        asset_class="EQUITY",
        status="ACTIVE",
        issuer_entity_id=entity.entity_id,
    )
    session.add(security)
    await session.flush()

    # Only one period — Beneish needs two
    fp = FinancialPeriod(
        period_id=uuid.uuid4(),
        entity_id=entity.entity_id,
        period_end_date=date(2024, 12, 31),
        period_type="ANNUAL",
        fiscal_year=2024,
    )
    session.add(fp)
    await session.flush()

    session.add(IncomeStatement(
        statement_id=uuid.uuid4(), period_id=fp.period_id,
        total_revenue=100_000_000.0, net_income=10_000_000.0,
    ))
    session.add(BalanceSheet(
        statement_id=uuid.uuid4(), period_id=fp.period_id,
        total_assets=200_000_000.0, total_equity=100_000_000.0,
    ))
    await session.flush()

    engine = BeneishEngine()
    results = await engine.compute(session, security_id=security.security_id)

    # Should return empty or all INSUFFICIENT_DATA
    if results:
        assert all(r.data_quality == "INSUFFICIENT_DATA" for r in results)


# ---------------------------------------------------------------------------
# Cross-engine consistency
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_all_e3_engines_same_entity(
    session: AsyncSession,
    security_for_scores: Security,
    two_annual_periods: tuple,
):
    """All three E3 engines should agree on entity_id."""
    from src.engines.e3_piotroski import PiotroskiEngine
    from src.engines.e3_altman import AltmanZScoreEngine as AltmanEngine
    from src.engines.e3_beneish import BeneishEngine

    pio = await PiotroskiEngine().compute(session, security_id=security_for_scores.security_id)
    alt = await AltmanEngine().compute(session, security_id=security_for_scores.security_id)
    ben = await BeneishEngine().compute(session, security_id=security_for_scores.security_id)

    all_results = pio + alt + ben
    entity_ids = {r.entity_id for r in all_results}
    assert len(entity_ids) == 1, f"Multiple entity_ids: {entity_ids}"
    assert security_for_scores.issuer_entity_id in entity_ids
