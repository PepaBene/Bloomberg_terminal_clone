"""Tests for Pillar 3 Phase 4C: Consolidated Alert & Earnings Surprise Intelligence models."""

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import select

from src.models.entity import Entity
from src.models.intelligent_alerts import ConsolidatedAlert, EarningsSurpriseIntelligence


# ── Helpers ──────────────────────────────────────────────────────────


async def _seed_entity(session, entity_id=None):
    eid = entity_id or uuid.uuid4()
    entity = Entity(
        entity_id=eid,
        entity_type="PUBLIC_COMPANY",
        legal_name="Alert Test Corp",
        status="ACTIVE",
        source="SEC_EDGAR",
    )
    session.add(entity)
    await session.flush()
    return entity


# ── ConsolidatedAlert Tests ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_consolidated_alert(session):
    """Create a consolidated alert with all fields."""
    entity = await _seed_entity(session)
    aid = uuid.uuid4()
    alert = ConsolidatedAlert(
        id=aid,
        entity_id=entity.entity_id,
        alert_priority=1,
        alert_categories={"categories": ["EARNINGS", "GUIDANCE"]},
        primary_headline="Major earnings miss with guidance cut",
        primary_type="EARNINGS_ALERT",
        source_alert_ids={"ids": [str(uuid.uuid4()), str(uuid.uuid4())]},
        secondary_alerts={"count": 3, "types": ["NEWS", "FILING"]},
        ai_synthesis="Company reported significant miss on both revenue and EPS.",
        recommended_action="REVIEW",
        related_catalysts={"catalysts": ["earnings_call", "sec_filing"]},
    )
    session.add(alert)
    await session.flush()

    result = await session.execute(
        select(ConsolidatedAlert).where(ConsolidatedAlert.id == aid)
    )
    fetched = result.scalar_one()
    assert fetched.entity_id == entity.entity_id
    assert fetched.alert_priority == 1
    assert fetched.primary_headline == "Major earnings miss with guidance cut"
    assert fetched.primary_type == "EARNINGS_ALERT"
    assert fetched.ai_synthesis is not None
    assert fetched.recommended_action == "REVIEW"
    assert fetched.is_acknowledged is False


@pytest.mark.asyncio
async def test_alert_acknowledge(session):
    """Test acknowledging an alert."""
    entity = await _seed_entity(session)
    aid = uuid.uuid4()
    alert = ConsolidatedAlert(
        id=aid,
        entity_id=entity.entity_id,
        alert_priority=2,
        primary_headline="Moderate filing alert",
        primary_type="FILING_ALERT",
    )
    session.add(alert)
    await session.flush()

    # Acknowledge
    result = await session.execute(
        select(ConsolidatedAlert).where(ConsolidatedAlert.id == aid)
    )
    fetched = result.scalar_one()
    fetched.is_acknowledged = True
    fetched.acknowledged_by = "analyst_001"
    fetched.acknowledged_at = datetime.now(timezone.utc)
    await session.flush()

    result2 = await session.execute(
        select(ConsolidatedAlert).where(ConsolidatedAlert.id == aid)
    )
    updated = result2.scalar_one()
    assert updated.is_acknowledged is True
    assert updated.acknowledged_by == "analyst_001"
    assert updated.acknowledged_at is not None


@pytest.mark.asyncio
async def test_alert_minimal_fields(session):
    """Create an alert with only required fields."""
    entity = await _seed_entity(session)
    aid = uuid.uuid4()
    alert = ConsolidatedAlert(
        id=aid,
        entity_id=entity.entity_id,
    )
    session.add(alert)
    await session.flush()

    result = await session.execute(
        select(ConsolidatedAlert).where(ConsolidatedAlert.id == aid)
    )
    fetched = result.scalar_one()
    assert fetched.alert_priority is None
    assert fetched.primary_headline is None
    assert fetched.is_acknowledged is False


@pytest.mark.asyncio
async def test_multiple_alerts_per_entity(session):
    """An entity can have multiple consolidated alerts."""
    entity = await _seed_entity(session)
    for priority in [1, 2, 3]:
        session.add(ConsolidatedAlert(
            id=uuid.uuid4(),
            entity_id=entity.entity_id,
            alert_priority=priority,
            primary_headline=f"Alert priority {priority}",
            primary_type="NEWS_ALERT",
        ))
    await session.flush()

    result = await session.execute(
        select(ConsolidatedAlert).where(ConsolidatedAlert.entity_id == entity.entity_id)
    )
    rows = result.scalars().all()
    assert len(rows) >= 3


@pytest.mark.asyncio
async def test_alert_jsonb_categories(session):
    """Round-trip JSONB alert_categories field."""
    entity = await _seed_entity(session)
    aid = uuid.uuid4()
    categories = {
        "primary": "EARNINGS",
        "secondary": ["GUIDANCE", "SENTIMENT"],
        "severity": "HIGH",
    }
    session.add(ConsolidatedAlert(
        id=aid,
        entity_id=entity.entity_id,
        alert_categories=categories,
    ))
    await session.flush()

    result = await session.execute(
        select(ConsolidatedAlert).where(ConsolidatedAlert.id == aid)
    )
    fetched = result.scalar_one()
    assert fetched.alert_categories["primary"] == "EARNINGS"
    assert "GUIDANCE" in fetched.alert_categories["secondary"]


# ── EarningsSurpriseIntelligence Tests ──────────────────────────────


@pytest.mark.asyncio
async def test_create_earnings_surprise_intelligence(session):
    """Create earnings surprise intelligence with all fields."""
    entity = await _seed_entity(session)
    eid = uuid.uuid4()
    earnings = EarningsSurpriseIntelligence(
        id=eid,
        entity_id=entity.entity_id,
        report_date=date(2025, 7, 25),
        fiscal_period="Q2 2025",
        eps_consensus=Decimal("2.1500"),
        eps_actual=Decimal("2.3200"),
        eps_surprise_pct=Decimal("7.9070"),
        revenue_consensus=Decimal("25000000000.00"),
        revenue_actual=Decimal("25500000000.00"),
        revenue_surprise_pct=Decimal("2.0000"),
        margin_analysis={"gross_margin": 45.2, "operating_margin": 28.1},
        guidance_implications={"raised": True, "new_eps_range": [8.5, 9.0]},
        stock_reaction={"day1_pct": 5.2, "day5_pct": 3.8},
        ai_narrative="Strong beat driven by cloud services growth.",
        key_takeaways={"takeaways": ["Cloud growth +30%", "Margin expansion"]},
        revision_implications={"direction": "UP", "magnitude": "MODERATE"},
        recommendation="OVERWEIGHT",
    )
    session.add(earnings)
    await session.flush()

    result = await session.execute(
        select(EarningsSurpriseIntelligence).where(EarningsSurpriseIntelligence.id == eid)
    )
    fetched = result.scalar_one()
    assert fetched.entity_id == entity.entity_id
    assert fetched.report_date == date(2025, 7, 25)
    assert fetched.fiscal_period == "Q2 2025"
    assert fetched.eps_consensus == Decimal("2.1500")
    assert fetched.eps_actual == Decimal("2.3200")
    assert fetched.eps_surprise_pct == Decimal("7.9070")
    assert fetched.revenue_surprise_pct == Decimal("2.0000")
    assert fetched.recommendation == "OVERWEIGHT"


@pytest.mark.asyncio
async def test_earnings_surprise_minimal_fields(session):
    """Create earnings intelligence with only required fields."""
    entity = await _seed_entity(session)
    eid = uuid.uuid4()
    earnings = EarningsSurpriseIntelligence(
        id=eid,
        entity_id=entity.entity_id,
        report_date=date(2025, 10, 1),
    )
    session.add(earnings)
    await session.flush()

    result = await session.execute(
        select(EarningsSurpriseIntelligence).where(EarningsSurpriseIntelligence.id == eid)
    )
    fetched = result.scalar_one()
    assert fetched.eps_consensus is None
    assert fetched.eps_actual is None
    assert fetched.ai_narrative is None


@pytest.mark.asyncio
async def test_earnings_surprise_jsonb_fields(session):
    """Round-trip JSONB fields on earnings intelligence."""
    entity = await _seed_entity(session)
    eid = uuid.uuid4()
    margin_analysis = {"gross_margin": 42.5, "operating_margin": 22.0, "net_margin": 15.5}
    key_takeaways = {"takeaways": ["Beat on cloud", "Miss on hardware", "Strong guidance"]}
    session.add(EarningsSurpriseIntelligence(
        id=eid,
        entity_id=entity.entity_id,
        report_date=date(2025, 8, 15),
        margin_analysis=margin_analysis,
        key_takeaways=key_takeaways,
    ))
    await session.flush()

    result = await session.execute(
        select(EarningsSurpriseIntelligence).where(EarningsSurpriseIntelligence.id == eid)
    )
    fetched = result.scalar_one()
    assert fetched.margin_analysis["gross_margin"] == 42.5
    assert len(fetched.key_takeaways["takeaways"]) == 3


@pytest.mark.asyncio
async def test_multiple_earnings_per_entity(session):
    """An entity can have multiple earnings reports."""
    entity = await _seed_entity(session)
    for month in [1, 4, 7, 10]:
        session.add(EarningsSurpriseIntelligence(
            id=uuid.uuid4(),
            entity_id=entity.entity_id,
            report_date=date(2025, month, 15),
            fiscal_period=f"Q{month // 3 + 1} 2025",
        ))
    await session.flush()

    result = await session.execute(
        select(EarningsSurpriseIntelligence)
        .where(EarningsSurpriseIntelligence.entity_id == entity.entity_id)
    )
    rows = result.scalars().all()
    assert len(rows) >= 4


@pytest.mark.asyncio
async def test_earnings_stock_reaction_jsonb(session):
    """Round-trip stock_reaction JSONB with nested data."""
    entity = await _seed_entity(session)
    eid = uuid.uuid4()
    stock_reaction = {
        "day1_change_pct": -8.5,
        "day5_change_pct": -12.3,
        "volume_vs_avg": 3.5,
        "options_activity": {"puts_calls_ratio": 2.1, "implied_vol_change": 15.0},
    }
    session.add(EarningsSurpriseIntelligence(
        id=eid,
        entity_id=entity.entity_id,
        report_date=date(2025, 9, 1),
        stock_reaction=stock_reaction,
    ))
    await session.flush()

    result = await session.execute(
        select(EarningsSurpriseIntelligence).where(EarningsSurpriseIntelligence.id == eid)
    )
    fetched = result.scalar_one()
    assert fetched.stock_reaction["day1_change_pct"] == -8.5
    assert fetched.stock_reaction["options_activity"]["puts_calls_ratio"] == 2.1
