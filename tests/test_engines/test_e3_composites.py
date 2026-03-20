"""Tests for E3 Composite Quality Scores Engine.

Tests earnings quality, financial strength, dividend safety, and
value trap risk composite scores.
"""

import uuid
from datetime import date

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.analytics import AnalyticsResult
from src.models.entity import Entity
from src.models.security import Security


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def comp_entity(session: AsyncSession) -> Entity:
    entity = Entity(
        entity_id=uuid.uuid4(),
        legal_name="Composite Score Test Corp",
        entity_type="PUBLIC_COMPANY",
        status="ACTIVE",
        incorporation_country="US",
        gics_sector="45",
        source="TEST",
    )
    session.add(entity)
    await session.flush()
    return entity


@pytest_asyncio.fixture
async def comp_security(session: AsyncSession, comp_entity: Entity) -> Security:
    security = Security(
        security_id=uuid.uuid4(),
        name="Composite Score Test Corp Common Stock",
        security_type="COMMON_STOCK",
        asset_class="EQUITY",
        status="ACTIVE",
        issuer_entity_id=comp_entity.entity_id,
    )
    session.add(security)
    await session.flush()
    return security


@pytest_asyncio.fixture
async def comp_analytics(
    session: AsyncSession,
    comp_entity: Entity,
    comp_security: Security,
) -> None:
    """Seed AnalyticsResult rows for all composite score inputs."""
    today = date(2025, 3, 14)

    metrics = [
        # Earnings quality inputs
        ("accruals_ratio", "QUALITY", 0.03),
        ("ocf_to_net_income", "QUALITY", 1.1),
        ("beneish_m_score", "QUALITY", -2.8),
        # Financial strength inputs
        ("interest_coverage", "LEVERAGE", 6.0),
        ("net_debt_to_ebitda", "LEVERAGE", 2.0),
        ("current_ratio", "LIQUIDITY", 1.5),
        ("altman_z_score", "QUALITY", 3.5),
        # Dividend safety inputs
        ("payout_ratio", "DIVIDEND", 0.40),
        ("fcf_payout_ratio", "DIVIDEND", 0.35),
        ("piotroski_f_score", "QUALITY", 7.0),
        # Value trap inputs
        ("pe_trailing", "VALUATION", 10.0),
        ("pb", "VALUATION", 0.8),
        ("dividend_yield", "VALUATION", 0.05),
    ]

    for metric_name, category, value in metrics:
        session.add(AnalyticsResult(
            security_id=comp_security.security_id,
            entity_id=comp_entity.entity_id,
            engine_id="E1",
            metric_name=metric_name,
            metric_category=category,
            value=value,
            unit="RATIO",
            period="TTM",
            as_of_date=today,
            data_quality="COMPLETE",
        ))
    await session.flush()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_earnings_quality_computed(
    session: AsyncSession,
    comp_security: Security,
    comp_analytics: None,
):
    """earnings_quality_score should exist and be between 0 and 100."""
    from src.engines.e3_composites import CompositeScoreEngine

    engine = CompositeScoreEngine()
    results = await engine.compute(session, security_id=comp_security.security_id)

    by_name = {r.metric_name: r.value for r in results}
    assert "earnings_quality_score" in by_name
    score = by_name["earnings_quality_score"]
    assert score is not None
    assert 0 <= score <= 100


@pytest.mark.asyncio
async def test_financial_strength_computed(
    session: AsyncSession,
    comp_security: Security,
    comp_analytics: None,
):
    """financial_strength_score should exist and be between 0 and 100."""
    from src.engines.e3_composites import CompositeScoreEngine

    engine = CompositeScoreEngine()
    results = await engine.compute(session, security_id=comp_security.security_id)

    by_name = {r.metric_name: r.value for r in results}
    assert "financial_strength_score" in by_name
    score = by_name["financial_strength_score"]
    assert score is not None
    assert 0 <= score <= 100


@pytest.mark.asyncio
async def test_dividend_safety_classification(
    session: AsyncSession,
    comp_security: Security,
    comp_analytics: None,
):
    """dividend_safety_classification should be one of SAFE/BORDERLINE/AT_RISK/DANGEROUS."""
    from src.engines.e3_composites import CompositeScoreEngine

    engine = CompositeScoreEngine()
    results = await engine.compute(session, security_id=comp_security.security_id)

    by_name = {r.metric_name: r for r in results}
    cls_output = by_name.get("dividend_safety_classification")
    assert cls_output is not None

    # Classification is stored in inputs with name="classification", period=<label>
    classification = None
    if cls_output.inputs:
        for inp in cls_output.inputs:
            if inp.get("name") == "classification":
                classification = inp.get("period")
    assert classification in ("SAFE", "BORDERLINE", "AT_RISK", "DANGEROUS")


@pytest.mark.asyncio
async def test_value_trap_classification(
    session: AsyncSession,
    comp_security: Security,
    comp_analytics: None,
):
    """value_trap_risk_classification should be LOW_RISK/MODERATE_RISK/HIGH_RISK/VALUE_TRAP_WARNING."""
    from src.engines.e3_composites import CompositeScoreEngine

    engine = CompositeScoreEngine()
    results = await engine.compute(session, security_id=comp_security.security_id)

    by_name = {r.metric_name: r for r in results}
    cls_output = by_name.get("value_trap_risk_classification")
    assert cls_output is not None

    classification = None
    if cls_output.inputs:
        for inp in cls_output.inputs:
            if inp.get("name") == "classification":
                classification = inp.get("period")
    assert classification in ("LOW_RISK", "MODERATE_RISK", "HIGH_RISK", "VALUE_TRAP_WARNING")


@pytest.mark.asyncio
async def test_all_composites_engine_id(
    session: AsyncSession,
    comp_security: Security,
    comp_analytics: None,
):
    """All composite score outputs should have engine_id='E3'."""
    from src.engines.e3_composites import CompositeScoreEngine

    engine = CompositeScoreEngine()
    results = await engine.compute(session, security_id=comp_security.security_id)

    assert len(results) > 0
    for r in results:
        assert r.engine_id == "E3"


@pytest.mark.asyncio
async def test_composite_components_present(
    session: AsyncSession,
    comp_security: Security,
    comp_analytics: None,
):
    """Each composite score should have component inputs in its lineage."""
    from src.engines.e3_composites import CompositeScoreEngine

    engine = CompositeScoreEngine()
    results = await engine.compute(session, security_id=comp_security.security_id)

    # The main score outputs carry component inputs
    score_metrics = [
        "earnings_quality_score",
        "financial_strength_score",
        "dividend_safety_score",
        "value_trap_risk_score",
    ]

    by_name = {r.metric_name: r for r in results}
    for metric in score_metrics:
        output = by_name.get(metric)
        assert output is not None, f"Missing score: {metric}"
        assert output.inputs is not None, f"No inputs for {metric}"
        assert len(output.inputs) >= 2, (
            f"{metric} should have at least 2 component inputs, got {len(output.inputs)}"
        )


@pytest.mark.asyncio
async def test_no_data_returns_insufficient(session: AsyncSession):
    """No AnalyticsResult rows should produce INSUFFICIENT_DATA or empty."""
    from src.engines.e3_composites import CompositeScoreEngine

    entity = Entity(
        entity_id=uuid.uuid4(),
        legal_name="Empty Composite Corp",
        entity_type="PUBLIC_COMPANY",
        status="ACTIVE",
        incorporation_country="US",
        source="TEST",
    )
    session.add(entity)
    await session.flush()

    security = Security(
        security_id=uuid.uuid4(),
        name="Empty Composite Common Stock",
        security_type="COMMON_STOCK",
        asset_class="EQUITY",
        status="ACTIVE",
        issuer_entity_id=entity.entity_id,
    )
    session.add(security)
    await session.flush()

    engine = CompositeScoreEngine()
    results = await engine.compute(session, security_id=security.security_id)

    if results:
        # All score outputs should be INSUFFICIENT_DATA or PARTIAL
        score_outputs = [
            r for r in results
            if r.metric_name.endswith("_score") or r.metric_name.endswith("_classification")
        ]
        for r in score_outputs:
            assert r.data_quality in ("INSUFFICIENT_DATA", "PARTIAL"), (
                f"{r.metric_name} has unexpected quality: {r.data_quality}"
            )


@pytest.mark.asyncio
async def test_partial_data_still_computes(session: AsyncSession):
    """Missing some metrics should still produce a score with PARTIAL quality."""
    from src.engines.e3_composites import CompositeScoreEngine

    entity = Entity(
        entity_id=uuid.uuid4(),
        legal_name="Partial Data Corp",
        entity_type="PUBLIC_COMPANY",
        status="ACTIVE",
        incorporation_country="US",
        source="TEST",
    )
    session.add(entity)
    await session.flush()

    security = Security(
        security_id=uuid.uuid4(),
        name="Partial Data Common Stock",
        security_type="COMMON_STOCK",
        asset_class="EQUITY",
        status="ACTIVE",
        issuer_entity_id=entity.entity_id,
    )
    session.add(security)
    await session.flush()

    today = date(2025, 3, 14)

    # Seed only financial strength metrics (partial — missing FCF-to-debt data)
    partial_metrics = [
        ("interest_coverage", "LEVERAGE", 6.0),
        ("net_debt_to_ebitda", "LEVERAGE", 2.0),
        ("current_ratio", "LIQUIDITY", 1.5),
        ("altman_z_score", "QUALITY", 3.5),
        # Deliberately omit free_cash_flow and total_debt (FCF-to-debt component)
    ]
    for metric_name, category, value in partial_metrics:
        session.add(AnalyticsResult(
            security_id=security.security_id,
            entity_id=entity.entity_id,
            engine_id="E1",
            metric_name=metric_name,
            metric_category=category,
            value=value,
            unit="RATIO",
            period="TTM",
            as_of_date=today,
            data_quality="COMPLETE",
        ))
    await session.flush()

    engine = CompositeScoreEngine()
    results = await engine.compute(
        session,
        security_id=security.security_id,
        score_types={"financial_strength"},
    )

    by_name = {r.metric_name: r for r in results}
    fs_score = by_name.get("financial_strength_score")
    assert fs_score is not None
    assert fs_score.value is not None
    assert fs_score.data_quality == "PARTIAL"
