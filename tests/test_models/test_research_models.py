"""Tests for Pillar 3 Phase 4A: Company Primer, Morning Briefing, Anomaly Detection models."""

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from src.models.entity import Entity
from src.models.company_primer_model import CompanyPrimer, PrimerRefreshLog
from src.models.morning_briefing import MorningBriefing, BriefingPreference
from src.models.anomaly_detection import DetectedAnomaly, AnomalyRule


# ── Helpers ──────────────────────────────────────────────────────────


async def _seed_entity(session, entity_id: uuid.UUID | None = None) -> Entity:
    eid = entity_id or uuid.uuid4()
    entity = Entity(
        entity_id=eid,
        entity_type="PUBLIC_COMPANY",
        legal_name="Research Test Corp",
        status="ACTIVE",
        source="SEC_EDGAR",
    )
    session.add(entity)
    await session.flush()
    return entity


# ── CompanyPrimer Tests ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_company_primer(session):
    """Create a company primer with all fields and verify."""
    entity = await _seed_entity(session)
    pid = uuid.uuid4()
    primer = CompanyPrimer(
        id=pid,
        primer_id=uuid.uuid4(),
        generated_date=date(2025, 10, 15),
        entity_id=entity.entity_id,
        primer_version=1,
        executive_summary="Strong growth company in tech sector.",
        business_model={"type": "SaaS", "recurring_revenue_pct": 85},
        competitive_landscape={"moat": "HIGH", "top_competitors": ["CompA", "CompB"]},
        financial_health={"debt_to_equity": 0.45, "current_ratio": 2.1},
        strategic_initiatives={"focus": ["AI", "Cloud Expansion"]},
        risk_factors={"regulatory": "MEDIUM", "concentration": "HIGH"},
        analyst_consensus={"target_price": 185.0, "rating": "BUY"},
        recent_catalysts={"events": ["Q3 earnings beat", "New product launch"]},
        data_completeness_score=Decimal("87.50"),
        last_filing_date=date(2025, 10, 15),
        last_earnings_call_date=date(2025, 10, 20),
        ai_enabled=True,
        prompt_template_used="v2_comprehensive",
    )
    session.add(primer)
    await session.flush()

    result = await session.execute(
        select(CompanyPrimer).where(CompanyPrimer.id == pid)
    )
    fetched = result.scalar_one()
    assert fetched.entity_id == entity.entity_id
    assert fetched.primer_version == 1
    assert fetched.executive_summary == "Strong growth company in tech sector."
    assert fetched.data_completeness_score == Decimal("87.50")
    assert fetched.ai_enabled is True
    assert fetched.prompt_template_used == "v2_comprehensive"


@pytest.mark.asyncio
async def test_company_primer_jsonb_roundtrip(session):
    """Verify JSONB fields round-trip correctly."""
    entity = await _seed_entity(session)
    pid = uuid.uuid4()
    risk_factors = {"regulatory": "HIGH", "market": "MEDIUM", "operational": "LOW"}
    business_model = {"revenue_streams": ["subscriptions", "services"], "margin": 72.5}

    primer = CompanyPrimer(
        id=pid,
        primer_id=uuid.uuid4(),
        generated_date=date(2025, 10, 1),
        entity_id=entity.entity_id,
        primer_version=1,
        risk_factors=risk_factors,
        business_model=business_model,
    )
    session.add(primer)
    await session.flush()

    result = await session.execute(
        select(CompanyPrimer).where(CompanyPrimer.id == pid)
    )
    fetched = result.scalar_one()
    assert fetched.risk_factors == risk_factors
    assert fetched.business_model == business_model


@pytest.mark.asyncio
async def test_company_primer_decimal_precision(session):
    """Decimal fields retain correct precision."""
    entity = await _seed_entity(session)
    pid = uuid.uuid4()
    primer = CompanyPrimer(
        id=pid,
        primer_id=uuid.uuid4(),
        generated_date=date(2025, 10, 1),
        entity_id=entity.entity_id,
        primer_version=1,
        data_completeness_score=Decimal("99.99"),
    )
    session.add(primer)
    await session.flush()

    result = await session.execute(
        select(CompanyPrimer).where(CompanyPrimer.id == pid)
    )
    fetched = result.scalar_one()
    assert fetched.data_completeness_score == Decimal("99.99")


@pytest.mark.asyncio
async def test_company_primer_defaults(session):
    """Verify default values for ai_enabled."""
    entity = await _seed_entity(session)
    pid = uuid.uuid4()
    primer = CompanyPrimer(
        id=pid,
        primer_id=uuid.uuid4(),
        generated_date=date(2025, 10, 1),
        entity_id=entity.entity_id,
        primer_version=1,
    )
    session.add(primer)
    await session.flush()

    result = await session.execute(
        select(CompanyPrimer).where(CompanyPrimer.id == pid)
    )
    fetched = result.scalar_one()
    assert fetched.ai_enabled is False


# ── PrimerRefreshLog Tests ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_primer_refresh_log(session):
    """Create a primer refresh log and verify fields."""
    entity = await _seed_entity(session)
    rid = uuid.uuid4()
    now = datetime.now(timezone.utc)

    refresh = PrimerRefreshLog(
        id=rid,
        entity_id=entity.entity_id,
        refresh_type="MANUAL",
        trigger_event="API_REQUEST",
        status="PENDING",
        started_at=now,
    )
    session.add(refresh)
    await session.flush()

    result = await session.execute(
        select(PrimerRefreshLog).where(PrimerRefreshLog.id == rid)
    )
    fetched = result.scalar_one()
    assert fetched.entity_id == entity.entity_id
    assert fetched.refresh_type == "MANUAL"
    assert fetched.trigger_event == "API_REQUEST"
    assert fetched.status == "PENDING"


# ── MorningBriefing Tests ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_morning_briefing(session):
    """Create a morning briefing with all JSONB fields."""
    bid = uuid.uuid4()
    briefing = MorningBriefing(
        id=bid,
        user_id="analyst_001",
        briefing_date=date(2025, 11, 1),
        regional_context="US",
        executive_summary="Markets mixed amid Fed uncertainty.",
        portfolio_impact={"top_movers": [{"ticker": "AAPL", "change_pct": 2.5}]},
        key_news={"headlines": ["Fed holds rates", "Tech earnings beat"]},
        thesis_updates={"updates": [{"entity": "MSFT", "status": "CONFIRMED"}]},
        macro_context={"us_10y": 4.25, "vix": 18.5},
        actionable_insights={"actions": ["Review AAPL position"]},
        delivery_format="FULL",
        ai_enabled=True,
    )
    session.add(briefing)
    await session.flush()

    result = await session.execute(
        select(MorningBriefing).where(MorningBriefing.id == bid)
    )
    fetched = result.scalar_one()
    assert fetched.user_id == "analyst_001"
    assert fetched.briefing_date == date(2025, 11, 1)
    assert fetched.regional_context == "US"
    assert fetched.portfolio_impact["top_movers"][0]["ticker"] == "AAPL"
    assert fetched.ai_enabled is True


@pytest.mark.asyncio
async def test_morning_briefing_defaults(session):
    """Verify default values for ai_enabled."""
    bid = uuid.uuid4()
    briefing = MorningBriefing(
        id=bid,
        user_id="analyst_002",
        briefing_date=date(2025, 11, 2),
    )
    session.add(briefing)
    await session.flush()

    result = await session.execute(
        select(MorningBriefing).where(MorningBriefing.id == bid)
    )
    fetched = result.scalar_one()
    assert fetched.ai_enabled is False


# ── BriefingPreference Tests ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_briefing_preference(session):
    """Create briefing preferences with JSONB portfolio IDs."""
    pid = uuid.uuid4()
    pref = BriefingPreference(
        id=pid,
        user_id="analyst_003",
        portfolio_entity_ids={"ids": ["uuid1", "uuid2"]},
        watchlist_entity_ids={"ids": ["uuid3"]},
        sector_focus={"sectors": ["Technology", "Healthcare"]},
        risk_tolerance="MODERATE",
        delivery_time_utc="06:30",
        delivery_format="SUMMARY",
        timezone="America/New_York",
        is_active=True,
    )
    session.add(pref)
    await session.flush()

    result = await session.execute(
        select(BriefingPreference).where(BriefingPreference.id == pid)
    )
    fetched = result.scalar_one()
    assert fetched.user_id == "analyst_003"
    assert fetched.portfolio_entity_ids == {"ids": ["uuid1", "uuid2"]}
    assert fetched.risk_tolerance == "MODERATE"
    assert fetched.delivery_time_utc == "06:30"
    assert fetched.is_active is True


@pytest.mark.asyncio
async def test_briefing_preference_unique_user(session):
    """user_id should be unique on briefing_preferences."""
    pid1 = uuid.uuid4()
    pid2 = uuid.uuid4()
    session.add(BriefingPreference(id=pid1, user_id="unique_analyst"))
    await session.flush()

    session.add(BriefingPreference(id=pid2, user_id="unique_analyst"))
    with pytest.raises(IntegrityError):
        await session.flush()
    await session.rollback()


# ── DetectedAnomaly Tests ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_detected_anomaly(session):
    """Create a detected anomaly with all numeric fields."""
    entity = await _seed_entity(session)
    aid = uuid.uuid4()
    anomaly = DetectedAnomaly(
        id=aid,
        entity_id=entity.entity_id,
        anomaly_type="VOLUME_SPIKE",
        severity_score=Decimal("92.50"),
        anomaly_window_start=date(2025, 11, 1),
        anomaly_window_end=date(2025, 11, 1),
        lookback_period="30D",
        observed_value=Decimal("15000000.0000"),
        expected_value=Decimal("5000000.0000"),
        z_score=Decimal("3.5000"),
        percentile_rank=Decimal("99.50"),
        contextual_analysis={"trigger": "earnings_surprise"},
        related_data={"news_ids": ["news1", "news2"]},
        ai_narrative="Unusual volume spike detected post earnings.",
        recommended_actions={"actions": ["Review position", "Check news"]},
        confidence_level=Decimal("0.95"),
        is_acknowledged=False,
    )
    session.add(anomaly)
    await session.flush()

    result = await session.execute(
        select(DetectedAnomaly).where(DetectedAnomaly.id == aid)
    )
    fetched = result.scalar_one()
    assert fetched.anomaly_type == "VOLUME_SPIKE"
    assert fetched.severity_score == Decimal("92.50")
    assert fetched.z_score == Decimal("3.5000")
    assert fetched.percentile_rank == Decimal("99.50")
    assert fetched.confidence_level == Decimal("0.95")
    assert fetched.is_acknowledged is False
    assert fetched.contextual_analysis == {"trigger": "earnings_surprise"}


@pytest.mark.asyncio
async def test_anomaly_acknowledge_flag(session):
    """Test acknowledge flag can be updated."""
    entity = await _seed_entity(session)
    aid = uuid.uuid4()
    anomaly = DetectedAnomaly(
        id=aid,
        entity_id=entity.entity_id,
        anomaly_type="SPREAD_WIDENING",
        severity_score=Decimal("75.00"),
        is_acknowledged=False,
    )
    session.add(anomaly)
    await session.flush()

    # Update acknowledge
    result = await session.execute(
        select(DetectedAnomaly).where(DetectedAnomaly.id == aid)
    )
    fetched = result.scalar_one()
    fetched.is_acknowledged = True
    fetched.acknowledged_by = "analyst_001"
    await session.flush()

    result2 = await session.execute(
        select(DetectedAnomaly).where(DetectedAnomaly.id == aid)
    )
    updated = result2.scalar_one()
    assert updated.is_acknowledged is True
    assert updated.acknowledged_by == "analyst_001"


# ── AnomalyRule Tests ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_anomaly_rule(session):
    """Create an anomaly detection rule with threshold config."""
    rid = uuid.uuid4()
    rule = AnomalyRule(
        id=rid,
        anomaly_type="VOLUME_SPIKE",
        rule_name="High Volume Alert",
        description="Alert when volume exceeds 3x average.",
        threshold_config={"z_score_threshold": 3.0, "lookback_days": 30},
        is_enabled=True,
    )
    session.add(rule)
    await session.flush()

    result = await session.execute(
        select(AnomalyRule).where(AnomalyRule.id == rid)
    )
    fetched = result.scalar_one()
    assert fetched.anomaly_type == "VOLUME_SPIKE"
    assert fetched.rule_name == "High Volume Alert"
    assert fetched.threshold_config == {"z_score_threshold": 3.0, "lookback_days": 30}
    assert fetched.is_enabled is True


@pytest.mark.asyncio
async def test_anomaly_rule_defaults(session):
    """Verify is_enabled defaults to True."""
    rid = uuid.uuid4()
    rule = AnomalyRule(
        id=rid,
        anomaly_type="PRICE_GAP",
        rule_name="Price Gap Rule",
    )
    session.add(rule)
    await session.flush()

    result = await session.execute(
        select(AnomalyRule).where(AnomalyRule.id == rid)
    )
    fetched = result.scalar_one()
    assert fetched.is_enabled is True
