"""Tests for Pillar 3 Phase 1: Watchlist & Alert models."""

import uuid
from datetime import date, datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from src.models.entity import Entity
from src.models.sentiment import AlertEvent, AlertRule, Watchlist


# ── Helpers ──────────────────────────────────────────────────────────


async def _seed_entity(session, entity_id: uuid.UUID | None = None) -> Entity:
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


async def _seed_alert_rule(session, user_id: str = "user_001") -> AlertRule:
    rid = uuid.uuid4()
    rule = AlertRule(
        id=rid,
        user_id=user_id,
        alert_type="INSIDER_TRADE",
        entity_scope={"entity_ids": [str(uuid.uuid4())]},
        conditions={"min_value": 100000, "transaction_type": "PURCHASE"},
        priority_threshold="HIGH",
        delivery_preference="REAL_TIME",
        is_active=True,
    )
    session.add(rule)
    await session.flush()
    return rule


# ── Tests ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_watchlist_entry(session):
    """Create a watchlist entry with user_id, entity_id, added_date."""
    entity = await _seed_entity(session)
    wid = uuid.uuid4()

    entry = Watchlist(
        id=wid,
        user_id="analyst_42",
        entity_id=entity.entity_id,
        added_date=date(2025, 9, 1),
        notes="Monitoring for Q3 earnings surprise potential.",
    )
    session.add(entry)
    await session.flush()

    result = await session.execute(
        select(Watchlist).where(Watchlist.id == wid)
    )
    fetched = result.scalar_one()
    assert fetched.user_id == "analyst_42"
    assert fetched.entity_id == entity.entity_id
    assert fetched.added_date == date(2025, 9, 1)
    assert fetched.notes == "Monitoring for Q3 earnings surprise potential."


@pytest.mark.asyncio
async def test_watchlist_unique_constraint(session):
    """user_id + entity_id should be unique."""
    entity = await _seed_entity(session)
    session.add(Watchlist(
        user_id="analyst_unique",
        entity_id=entity.entity_id,
        added_date=date(2025, 9, 1),
    ))
    await session.flush()

    session.add(Watchlist(
        user_id="analyst_unique",
        entity_id=entity.entity_id,
        added_date=date(2025, 10, 1),
    ))
    with pytest.raises(IntegrityError):
        await session.flush()
    await session.rollback()


@pytest.mark.asyncio
async def test_create_alert_rule(session):
    """Create an alert rule with JSONB entity_scope and conditions."""
    entity = await _seed_entity(session)
    rid = uuid.uuid4()
    entity_scope = {
        "entity_ids": [str(entity.entity_id)],
        "sectors": ["TECHNOLOGY"],
    }
    conditions = {
        "min_value": 500000,
        "transaction_type": "PURCHASE",
        "insider_roles": ["CEO", "CFO"],
    }

    rule = AlertRule(
        id=rid,
        user_id="portfolio_mgr_1",
        alert_type="INSIDER_CLUSTER_BUY",
        entity_scope=entity_scope,
        conditions=conditions,
        priority_threshold="HIGH",
        delivery_preference="REAL_TIME",
        is_active=True,
        quiet_hours_start="22:00",
        quiet_hours_end="07:00",
    )
    session.add(rule)
    await session.flush()

    result = await session.execute(
        select(AlertRule).where(AlertRule.id == rid)
    )
    fetched = result.scalar_one()
    assert fetched.user_id == "portfolio_mgr_1"
    assert fetched.alert_type == "INSIDER_CLUSTER_BUY"
    assert fetched.entity_scope == entity_scope
    assert fetched.conditions == conditions
    assert fetched.priority_threshold == "HIGH"
    assert fetched.delivery_preference == "REAL_TIME"
    assert fetched.is_active is True
    assert fetched.quiet_hours_start == "22:00"
    assert fetched.quiet_hours_end == "07:00"


@pytest.mark.asyncio
async def test_create_alert_event(session):
    """Create an alert event with priority, title, JSONB detail."""
    entity = await _seed_entity(session)
    rule = await _seed_alert_rule(session, user_id="alert_user_1")
    eid = uuid.uuid4()
    detail = {
        "insider_name": "John CEO",
        "shares_purchased": 25000,
        "total_value": 3750000,
        "transaction_date": "2025-10-15",
    }

    event = AlertEvent(
        id=eid,
        rule_id=rule.id,
        user_id="alert_user_1",
        entity_id=entity.entity_id,
        alert_type="INSIDER_TRADE",
        priority="HIGH",
        title="Significant insider purchase detected at Alert Test Corp",
        detail=detail,
        is_acknowledged=False,
        acknowledged_at=None,
    )
    session.add(event)
    await session.flush()

    result = await session.execute(
        select(AlertEvent).where(AlertEvent.id == eid)
    )
    fetched = result.scalar_one()
    assert fetched.rule_id == rule.id
    assert fetched.user_id == "alert_user_1"
    assert fetched.entity_id == entity.entity_id
    assert fetched.alert_type == "INSIDER_TRADE"
    assert fetched.priority == "HIGH"
    assert fetched.title == "Significant insider purchase detected at Alert Test Corp"
    assert fetched.detail == detail
    assert fetched.detail["shares_purchased"] == 25000
    assert fetched.is_acknowledged is False
    assert fetched.acknowledged_at is None


@pytest.mark.asyncio
async def test_alert_acknowledge(session):
    """Create event, update is_acknowledged to True + acknowledged_at."""
    entity = await _seed_entity(session)
    eid = uuid.uuid4()
    event = AlertEvent(
        id=eid,
        user_id="ack_user",
        entity_id=entity.entity_id,
        alert_type="NEWS_ALERT",
        priority="MEDIUM",
        title="Negative news coverage detected",
        is_acknowledged=False,
    )
    session.add(event)
    await session.flush()

    # Verify default unacknowledged state
    result = await session.execute(
        select(AlertEvent).where(AlertEvent.id == eid)
    )
    fetched = result.scalar_one()
    assert fetched.is_acknowledged is False
    assert fetched.acknowledged_at is None

    # Acknowledge the alert
    ack_time = datetime(2025, 10, 16, 14, 30, 0, tzinfo=timezone.utc)
    fetched.is_acknowledged = True
    fetched.acknowledged_at = ack_time
    await session.flush()

    result2 = await session.execute(
        select(AlertEvent).where(AlertEvent.id == eid)
    )
    updated = result2.scalar_one()
    assert updated.is_acknowledged is True
    assert updated.acknowledged_at is not None


@pytest.mark.asyncio
async def test_query_alerts_by_user(session):
    """Create multiple alerts, filter unacknowledged only."""
    entity = await _seed_entity(session)
    user_id = f"filter_user_{uuid.uuid4().hex[:8]}"

    # Create 3 acknowledged + 2 unacknowledged alerts
    for i in range(5):
        session.add(AlertEvent(
            user_id=user_id,
            entity_id=entity.entity_id,
            alert_type="FILING_ALERT",
            priority="MEDIUM",
            title=f"Alert event {i + 1}",
            is_acknowledged=i < 3,  # first 3 acknowledged
            acknowledged_at=(
                datetime(2025, 10, 20, 10, i, 0, tzinfo=timezone.utc)
                if i < 3 else None
            ),
        ))
    await session.flush()

    # Query only unacknowledged for this user
    result = await session.execute(
        select(AlertEvent)
        .where(AlertEvent.user_id == user_id)
        .where(AlertEvent.is_acknowledged == False)  # noqa: E712
    )
    unacked = result.scalars().all()
    assert len(unacked) == 2
    for alert in unacked:
        assert alert.is_acknowledged is False
        assert alert.acknowledged_at is None

    # Query all for this user
    result_all = await session.execute(
        select(AlertEvent).where(AlertEvent.user_id == user_id)
    )
    all_alerts = result_all.scalars().all()
    assert len(all_alerts) == 5
