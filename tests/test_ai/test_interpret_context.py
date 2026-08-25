"""Tests for src/ai/interpret/context.py — subject context assembly."""
from __future__ import annotations

import uuid
from datetime import date

from src.ai.interpret.context import assemble_entity_context, classify_trend


# --------------------------------------------------------------------------- #
# classify_trend (pure)
# --------------------------------------------------------------------------- #
def test_classify_trend_improving():
    assert classify_trend(20.0, 15.0) == "IMPROVING"


def test_classify_trend_deteriorating():
    assert classify_trend(10.0, 15.0) == "DETERIORATING"


def test_classify_trend_stable():
    assert classify_trend(15.0, 15.0) == "STABLE"


def test_classify_trend_none_when_missing_either_side():
    assert classify_trend(None, 15.0) is None
    assert classify_trend(15.0, None) is None
    assert classify_trend(None, None) is None


def test_classify_trend_near_zero_delta_is_stable():
    assert classify_trend(15.0000000001, 15.0) == "STABLE"


# --------------------------------------------------------------------------- #
# assemble_entity_context (DB-backed, SQLite test engine)
# --------------------------------------------------------------------------- #
async def _seed_entity(session) -> uuid.UUID:
    from src.models.entity import Entity

    entity_id = uuid.uuid4()
    session.add(Entity(
        entity_id=entity_id, entity_type="PUBLIC_COMPANY",
        legal_name="MegaCorp Inc.", status="ACTIVE", source="TEST",
    ))
    await session.flush()
    return entity_id


async def _seed_security(session, entity_id: uuid.UUID) -> uuid.UUID:
    from src.models.security import Security

    security_id = uuid.uuid4()
    session.add(Security(
        security_id=security_id, security_type="COMMON_STOCK",
        issuer_entity_id=entity_id, name="MegaCorp Common Stock",
        status="ACTIVE", asset_class="EQUITY",
    ))
    await session.flush()
    return security_id


async def test_assemble_entity_context_empty_for_unknown_entity(session):
    ctx = await assemble_entity_context(session, uuid.uuid4())
    assert ctx.metrics == []
    assert ctx.subject_type == "ENTITY"


async def test_assemble_entity_context_analytics_results_with_trend(session):
    from src.models.analytics import AnalyticsResult

    entity_id = await _seed_entity(session)
    security_id = await _seed_security(session, entity_id)

    session.add(AnalyticsResult(
        result_id=uuid.uuid4(), security_id=security_id, entity_id=entity_id,
        engine_id="E1", metric_name="ROE", metric_category="PROFITABILITY",
        value=12.0, unit="PERCENT", period="FY2024", as_of_date=date(2025, 1, 1),
        inputs=[{"name": "net_income", "source": "fundamentals", "value": 100.0}],
    ))
    session.add(AnalyticsResult(
        result_id=uuid.uuid4(), security_id=security_id, entity_id=entity_id,
        engine_id="E1", metric_name="ROE", metric_category="PROFITABILITY",
        value=18.0, unit="PERCENT", period="FY2025", as_of_date=date(2026, 1, 1),
        inputs=[{"name": "net_income", "source": "fundamentals", "value": 150.0}],
    ))
    await session.flush()

    ctx = await assemble_entity_context(session, entity_id)
    roe = next(m for m in ctx.metrics if m.metric_name == "ROE")
    assert roe.value == 18.0
    assert roe.trend == "IMPROVING"
    assert roe.as_of_date == date(2026, 1, 1)
    assert roe.source_table == "analytics_results"
    assert roe.lineage == [{"name": "net_income", "source": "fundamentals", "value": 150.0}]
    assert "1:2026-01-01" == ctx.analytics_version  # 1 metric, latest date


async def test_assemble_entity_context_dedupes_to_latest_per_metric(session):
    from src.models.analytics import AnalyticsResult

    entity_id = await _seed_entity(session)
    security_id = await _seed_security(session, entity_id)
    for i, (value, as_of) in enumerate([(10.0, date(2024, 1, 1)), (12.0, date(2025, 1, 1)), (15.0, date(2026, 1, 1))]):
        session.add(AnalyticsResult(
            result_id=uuid.uuid4(), security_id=security_id, entity_id=entity_id,
            engine_id="E1", metric_name="CURRENT_RATIO", metric_category="LIQUIDITY",
            value=value, unit="RATIO", period=f"FY202{4+i}", as_of_date=as_of,
        ))
    await session.flush()

    ctx = await assemble_entity_context(session, entity_id)
    matches = [m for m in ctx.metrics if m.metric_name == "CURRENT_RATIO"]
    assert len(matches) == 1
    assert matches[0].value == 15.0


async def test_assemble_entity_context_credit_risk(session):
    from src.models.default_risk import DefaultRiskScore

    entity_id = await _seed_entity(session)
    session.add(DefaultRiskScore(
        score_id=uuid.uuid4(), entity_id=entity_id,
        calculation_date=date(2026, 1, 1),
        composite_score=72.5, implied_rating="BBB", trend="IMPROVING",
    ))
    await session.flush()

    ctx = await assemble_entity_context(session, entity_id)
    credit = next(m for m in ctx.metrics if m.metric_name == "CREDIT_COMPOSITE_SCORE")
    assert credit.value == 72.5
    assert credit.trend == "IMPROVING"
    assert credit.source_table == "default_risk_scores"


async def test_assemble_entity_context_credit_risk_skipped_when_no_composite_score(session):
    from src.models.default_risk import DefaultRiskScore

    entity_id = await _seed_entity(session)
    session.add(DefaultRiskScore(
        score_id=uuid.uuid4(), entity_id=entity_id,
        calculation_date=date(2026, 1, 1), composite_score=None,
    ))
    await session.flush()
    ctx = await assemble_entity_context(session, entity_id)
    assert not any(m.metric_name == "CREDIT_COMPOSITE_SCORE" for m in ctx.metrics)


async def test_assemble_entity_context_insider_signal(session):
    from src.models.insider_intelligence import InsiderSignal

    entity_id = await _seed_entity(session)
    session.add(InsiderSignal(
        id=uuid.uuid4(), entity_id=entity_id, signal_date=date(2026, 1, 1),
        signal_type="CLUSTER_BUY", signal_strength=85,
        net_value_90d=5_000_000,
    ))
    await session.flush()

    ctx = await assemble_entity_context(session, entity_id)
    signal = next(m for m in ctx.metrics if m.metric_name == "INSIDER_SIGNAL_STRENGTH")
    assert signal.value == 85.0
    assert signal.lineage[0] == {"name": "signal_type", "value": "CLUSTER_BUY"}


async def test_assemble_entity_context_macro_theme_multiple_themes(session):
    from src.models.macro_themes import MacroThemeScore

    entity_id = await _seed_entity(session)
    session.add(MacroThemeScore(
        id=uuid.uuid4(), entity_id=entity_id, theme="RATE_SENSITIVITY",
        exposure_score=60.0, sensitivity_direction="NEGATIVE", as_of_date=date(2026, 1, 1),
    ))
    session.add(MacroThemeScore(
        id=uuid.uuid4(), entity_id=entity_id, theme="AI_ADOPTION",
        exposure_score=80.0, sensitivity_direction="POSITIVE", as_of_date=date(2026, 1, 1),
    ))
    await session.flush()

    ctx = await assemble_entity_context(session, entity_id)
    theme_metrics = {m.metric_name: m for m in ctx.metrics if m.metric_name.startswith("MACRO_THEME_EXPOSURE:")}
    assert theme_metrics["MACRO_THEME_EXPOSURE:RATE_SENSITIVITY"].value == 60.0
    assert theme_metrics["MACRO_THEME_EXPOSURE:AI_ADOPTION"].value == 80.0


async def test_assemble_entity_context_esg_and_governance(session):
    from src.models.esg_temperature import ESGTemperatureScore
    from src.models.governance_intelligence import GovernanceAssessment

    entity_id = await _seed_entity(session)
    session.add(ESGTemperatureScore(
        id=uuid.uuid4(), entity_id=entity_id, as_of_date=date(2026, 1, 1),
        implied_temperature=2.3, alignment="WELL_BELOW_2C",
    ))
    session.add(GovernanceAssessment(
        id=uuid.uuid4(), entity_id=entity_id, assessment_date=date(2026, 1, 1),
        governance_score=88, classification="STRONG",
    ))
    await session.flush()

    ctx = await assemble_entity_context(session, entity_id)
    esg = next(m for m in ctx.metrics if m.metric_name == "ESG_IMPLIED_TEMPERATURE")
    gov = next(m for m in ctx.metrics if m.metric_name == "GOVERNANCE_SCORE")
    assert esg.value == 2.3
    assert gov.value == 88.0
    assert gov.lineage[0]["name"] == "classification"


async def test_assemble_entity_context_combines_all_wired_domains(session):
    from src.models.analytics import AnalyticsResult
    from src.models.default_risk import DefaultRiskScore
    from src.models.esg_temperature import ESGTemperatureScore

    entity_id = await _seed_entity(session)
    security_id = await _seed_security(session, entity_id)
    session.add(AnalyticsResult(
        result_id=uuid.uuid4(), security_id=security_id, entity_id=entity_id,
        engine_id="E1", metric_name="ROE", metric_category="PROFITABILITY",
        value=18.0, unit="PERCENT", period="FY2025", as_of_date=date(2026, 1, 1),
    ))
    session.add(DefaultRiskScore(
        score_id=uuid.uuid4(), entity_id=entity_id,
        calculation_date=date(2026, 1, 1), composite_score=70.0,
    ))
    session.add(ESGTemperatureScore(
        id=uuid.uuid4(), entity_id=entity_id, as_of_date=date(2026, 1, 1),
        implied_temperature=2.0, alignment="ALIGNED",
    ))
    await session.flush()

    ctx = await assemble_entity_context(session, entity_id)
    names = {m.metric_name for m in ctx.metrics}
    assert {"ROE", "CREDIT_COMPOSITE_SCORE", "ESG_IMPLIED_TEMPERATURE"}.issubset(names)
    assert ctx.subject_id == str(entity_id)
