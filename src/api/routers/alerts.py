"""Alerts & Watchlist API endpoints (Pillar 3 Phase 1)."""

import uuid
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, and_, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_session
from src.engines import alert_engine
from src.models.entity import Entity
from src.models.filing_intelligence import EightKEvent
from src.models.security import EODPrice, Security
from src.models.sentiment import AlertEvent, AlertRule, Watchlist
from src.schemas.alerts import (
    AlertEventResponse,
    AlertRuleCreateRequest,
    AlertRuleResponse,
    WatchlistAddRequest,
    WatchlistEntryResponse,
)

router = APIRouter(tags=["Alerts & Watchlist"])

# Default user ID for single-user mode (can be replaced with auth dependency)
DEFAULT_USER_ID = "default"

# 8-K item number → alert_engine alert_type + priority.
_EIGHT_K_ALERT_MAP = {
    "5.02": ("MANAGEMENT_CHANGE", "HIGH"),
    "4.01": ("AUDITOR_CHANGE", "CRITICAL"),
    "4.02": ("RESTATEMENT", "CRITICAL"),
}


def _rule_to_engine_dict(rule: AlertRule) -> dict:
    return {
        "alert_type": rule.alert_type,
        "entity_scope": rule.entity_scope or {},
        "conditions": rule.conditions or {},
        "priority_threshold": rule.priority_threshold or "LOW",
        "is_active": rule.is_active,
    }


async def _get_entity(session: AsyncSession, entity_id: uuid.UUID) -> Entity:
    result = await session.execute(
        select(Entity).where(Entity.entity_id == entity_id)
    )
    entity = result.scalar_one_or_none()
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
    return entity


# ── Alert Events ───────────────────────────────────────────────────────


@router.get(
    "/alerts",
    response_model=list[AlertEventResponse],
)
async def get_alerts(
    session: AsyncSession = Depends(get_session),
    priority: str | None = Query(None, description="Filter by priority (HIGH, MEDIUM, LOW)"),
    entity_id: uuid.UUID | None = Query(None, description="Filter by entity"),
):
    """Get alert events for the current user."""
    stmt = select(AlertEvent).where(AlertEvent.user_id == DEFAULT_USER_ID)

    if priority:
        stmt = stmt.where(AlertEvent.priority == priority)
    if entity_id:
        stmt = stmt.where(AlertEvent.entity_id == entity_id)

    stmt = stmt.order_by(AlertEvent.created_at.desc()).limit(100)
    result = await session.execute(stmt)
    rows = result.scalars().all()

    return [
        AlertEventResponse(
            id=row.id,
            alert_type=row.alert_type,
            priority=row.priority,
            entity_id=row.entity_id,
            title=row.title,
            detail=row.detail,
            is_acknowledged=row.is_acknowledged,
            created_at=row.created_at,
        )
        for row in rows
    ]


@router.post(
    "/alerts/evaluate",
    response_model=dict,
)
async def evaluate_alerts(
    session: AsyncSession = Depends(get_session),
    days_back: int = Query(default=30, ge=1, le=365, description="Filing look-back window"),
):
    """Evaluate active alert rules against real events and persist fired alerts.

    This is the missing producer for AlertEvent: alert_engine (real, but
    previously only exercised by tests) is now driven by real 8-K filing
    events (from eight_k_events) and real EOD prices (threshold / 52-week
    high-low), then the resulting alerts are deduplicated and persisted so
    GET /alerts returns actual fired events instead of always being empty.
    """
    rules = (
        await session.execute(
            select(AlertRule).where(
                AlertRule.user_id == DEFAULT_USER_ID,
                AlertRule.is_active == True,  # noqa: E712
            )
        )
    ).scalars().all()
    if not rules:
        return {"evaluated_rules": 0, "alerts_created": 0, "alert_types": []}

    rule_dicts = [_rule_to_engine_dict(r) for r in rules]

    # ── Filing events from real 8-K rows ──────────────────────────────
    cutoff = date.today() - timedelta(days=days_back)
    eight_k_rows = (
        await session.execute(
            select(EightKEvent)
            .where(EightKEvent.filing_date >= cutoff)
            .order_by(EightKEvent.filing_date.desc())
            .limit(500)
        )
    ).scalars().all()

    entity_ids = {ev.entity_id for ev in eight_k_rows}
    # Bring in entities named in price-rule scopes as well.
    for rd in rule_dicts:
        for raw in (rd["entity_scope"].get("entity_ids") or []):
            try:
                entity_ids.add(uuid.UUID(str(raw)))
            except (ValueError, TypeError):
                continue

    names: dict = {}
    if entity_ids:
        name_rows = (
            await session.execute(
                select(Entity.entity_id, Entity.legal_name).where(Entity.entity_id.in_(entity_ids))
            )
        ).all()
        names = {eid: nm for eid, nm in name_rows}

    events = []
    for ev in eight_k_rows:
        alert_type, priority = _EIGHT_K_ALERT_MAP.get(
            ev.item_number, ("FILING_8K", "HIGH" if (ev.priority or 5) <= 2 else "MEDIUM")
        )
        events.append({
            "entity_id": str(ev.entity_id),
            "alert_type": alert_type,
            "priority": priority,
            "entity_name": names.get(ev.entity_id, ""),
            "detail": {
                "item_number": ev.item_number,
                "item_description": ev.item_description,
                "filing_date": ev.filing_date.isoformat() if ev.filing_date else None,
            },
            "source_type": "8K",
            "source_id": ev.filing_accession_number or str(ev.id),
        })

    filing_alerts = alert_engine.evaluate_filing_alerts(events, rule_dicts)

    # ── Price alerts from real EOD prices ─────────────────────────────
    # Only evaluate entities explicitly scoped by a price rule, to bound work.
    price_rule_entity_ids: set[uuid.UUID] = set()
    for rd in rule_dicts:
        if rd["alert_type"] in ("PRICE_THRESHOLD", "PRICE_52W_HIGH", "PRICE_52W_LOW"):
            for raw in (rd["entity_scope"].get("entity_ids") or []):
                try:
                    price_rule_entity_ids.add(uuid.UUID(str(raw)))
                except (ValueError, TypeError):
                    continue

    current_prices: dict[str, float] = {}
    hist_highs: dict[str, float] = {}
    hist_lows: dict[str, float] = {}
    price_cutoff = date.today() - timedelta(days=365)
    for eid in price_rule_entity_ids:
        sec = (
            await session.execute(
                select(Security.security_id)
                .where(Security.issuer_entity_id == eid, Security.asset_class == "EQUITY")
                .limit(1)
            )
        ).scalar_one_or_none()
        if sec is None:
            continue
        closes = (
            await session.execute(
                select(EODPrice.close)
                .where(EODPrice.security_id == sec, EODPrice.close.isnot(None),
                       EODPrice.price_date >= price_cutoff)
                .order_by(EODPrice.price_date.desc())
            )
        ).scalars().all()
        vals = [float(c) for c in closes]
        if not vals:
            continue
        current_prices[str(eid)] = vals[0]
        # 52-week high/low over the trailing window (exclude latest so a
        # fresh extreme still triggers).
        prior = vals[1:] or vals
        hist_highs[str(eid)] = max(prior)
        hist_lows[str(eid)] = min(prior)

    price_alerts = alert_engine.evaluate_price_alerts(
        current_prices, rule_dicts, historical_highs=hist_highs, historical_lows=hist_lows
    )

    fired = alert_engine.prioritize_alerts(filing_alerts + price_alerts)

    created = 0
    created_types: set[str] = set()
    for a in fired:
        try:
            entity_uuid = uuid.UUID(a.entity_id)
        except (ValueError, TypeError):
            continue
        # Dedup: skip if an identical unacknowledged alert already exists.
        existing = (
            await session.execute(
                select(AlertEvent).where(
                    AlertEvent.user_id == DEFAULT_USER_ID,
                    AlertEvent.entity_id == entity_uuid,
                    AlertEvent.alert_type == a.alert_type,
                    AlertEvent.title == a.title,
                    AlertEvent.is_acknowledged == False,  # noqa: E712
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            continue
        session.add(AlertEvent(
            id=uuid.uuid4(),
            rule_id=None,
            user_id=DEFAULT_USER_ID,
            entity_id=entity_uuid,
            alert_type=a.alert_type,
            priority=a.priority,
            title=a.title,
            detail=a.detail,
        ))
        created += 1
        created_types.add(a.alert_type)

    if created:
        await session.commit()

    return {
        "evaluated_rules": len(rules),
        "alerts_created": created,
        "alert_types": sorted(created_types),
    }


@router.post(
    "/alerts/acknowledge/{alert_id}",
    response_model=dict,
)
async def acknowledge_alert(
    alert_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Acknowledge an alert event."""
    result = await session.execute(
        select(AlertEvent).where(AlertEvent.id == alert_id)
    )
    alert = result.scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    alert.is_acknowledged = True
    alert.acknowledged_at = datetime.now(timezone.utc)
    await session.commit()

    return {"status": "acknowledged", "alert_id": str(alert_id)}


# ── Alert Rules (Config) ──────────────────────────────────────────────


@router.get(
    "/alerts/config",
    response_model=list[AlertRuleResponse],
)
async def get_alert_config(
    session: AsyncSession = Depends(get_session),
):
    """Get all alert rules for the current user."""
    result = await session.execute(
        select(AlertRule)
        .where(AlertRule.user_id == DEFAULT_USER_ID)
        .order_by(AlertRule.alert_type)
    )
    rows = result.scalars().all()

    return [
        AlertRuleResponse(
            id=row.id,
            alert_type=row.alert_type,
            entity_scope=row.entity_scope,
            conditions=row.conditions,
            priority_threshold=row.priority_threshold,
            delivery_preference=row.delivery_preference,
            is_active=row.is_active,
        )
        for row in rows
    ]


@router.post(
    "/alerts/config",
    response_model=AlertRuleResponse,
    status_code=201,
)
async def create_alert_config(
    body: AlertRuleCreateRequest,
    session: AsyncSession = Depends(get_session),
):
    """Create a new alert rule."""
    rule = AlertRule(
        user_id=DEFAULT_USER_ID,
        alert_type=body.alert_type,
        entity_scope=body.entity_scope,
        conditions=body.conditions,
        priority_threshold=body.priority_threshold,
        delivery_preference=body.delivery_preference,
        is_active=True,
    )
    session.add(rule)
    await session.commit()
    await session.refresh(rule)

    return AlertRuleResponse(
        id=rule.id,
        alert_type=rule.alert_type,
        entity_scope=rule.entity_scope,
        conditions=rule.conditions,
        priority_threshold=rule.priority_threshold,
        delivery_preference=rule.delivery_preference,
        is_active=rule.is_active,
    )


# ── Custom Alert Rules ────────────────────────────────────────────────


@router.post(
    "/alerts/custom",
    response_model=AlertRuleResponse,
    status_code=201,
)
async def create_custom_alert_rule(
    body: AlertRuleCreateRequest,
    session: AsyncSession = Depends(get_session),
):
    """Create a custom alert rule with specific conditions."""
    rule = AlertRule(
        user_id=DEFAULT_USER_ID,
        alert_type=body.alert_type,
        entity_scope=body.entity_scope,
        conditions=body.conditions,
        priority_threshold=body.priority_threshold,
        delivery_preference=body.delivery_preference,
        is_active=True,
    )
    session.add(rule)
    await session.commit()
    await session.refresh(rule)

    return AlertRuleResponse(
        id=rule.id,
        alert_type=rule.alert_type,
        entity_scope=rule.entity_scope,
        conditions=rule.conditions,
        priority_threshold=rule.priority_threshold,
        delivery_preference=rule.delivery_preference,
        is_active=rule.is_active,
    )


@router.get(
    "/alerts/custom",
    response_model=list[AlertRuleResponse],
)
async def get_custom_alert_rules(
    session: AsyncSession = Depends(get_session),
):
    """Get all custom alert rules for the current user."""
    result = await session.execute(
        select(AlertRule)
        .where(AlertRule.user_id == DEFAULT_USER_ID)
        .where(AlertRule.conditions.isnot(None))
        .order_by(AlertRule.alert_type)
    )
    rows = result.scalars().all()

    return [
        AlertRuleResponse(
            id=row.id,
            alert_type=row.alert_type,
            entity_scope=row.entity_scope,
            conditions=row.conditions,
            priority_threshold=row.priority_threshold,
            delivery_preference=row.delivery_preference,
            is_active=row.is_active,
        )
        for row in rows
    ]


@router.delete(
    "/alerts/custom/{rule_id}",
    response_model=dict,
)
async def delete_custom_alert_rule(
    rule_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Delete a custom alert rule."""
    result = await session.execute(
        select(AlertRule).where(
            and_(AlertRule.id == rule_id, AlertRule.user_id == DEFAULT_USER_ID)
        )
    )
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Alert rule not found")

    await session.delete(rule)
    await session.commit()

    return {"status": "deleted", "rule_id": str(rule_id)}


# ── Watchlist ──────────────────────────────────────────────────────────


@router.get(
    "/watchlist",
    response_model=list[WatchlistEntryResponse],
)
async def get_watchlist(
    session: AsyncSession = Depends(get_session),
):
    """Get the current user's watchlist."""
    result = await session.execute(
        select(Watchlist)
        .where(Watchlist.user_id == DEFAULT_USER_ID)
        .order_by(Watchlist.added_date.desc())
    )
    rows = result.scalars().all()

    return [
        WatchlistEntryResponse(
            entity_id=row.entity_id,
            added_date=row.added_date,
            notes=row.notes,
        )
        for row in rows
    ]


@router.post(
    "/watchlist",
    response_model=WatchlistEntryResponse,
    status_code=201,
)
async def add_to_watchlist(
    body: WatchlistAddRequest,
    session: AsyncSession = Depends(get_session),
):
    """Add an entity to the watchlist."""
    await _get_entity(session, body.entity_id)

    # Check if already on watchlist
    existing = await session.execute(
        select(Watchlist).where(
            and_(
                Watchlist.user_id == DEFAULT_USER_ID,
                Watchlist.entity_id == body.entity_id,
            )
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Entity already on watchlist")

    entry = Watchlist(
        user_id=DEFAULT_USER_ID,
        entity_id=body.entity_id,
        added_date=date.today(),
        notes=body.notes,
    )
    session.add(entry)
    await session.commit()
    await session.refresh(entry)

    return WatchlistEntryResponse(
        entity_id=entry.entity_id,
        added_date=entry.added_date,
        notes=entry.notes,
    )


@router.delete(
    "/watchlist/{entity_id}",
    response_model=dict,
)
async def remove_from_watchlist(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Remove an entity from the watchlist."""
    result = await session.execute(
        select(Watchlist).where(
            and_(
                Watchlist.user_id == DEFAULT_USER_ID,
                Watchlist.entity_id == entity_id,
            )
        )
    )
    entry = result.scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=404, detail="Entity not on watchlist")

    await session.delete(entry)
    await session.commit()

    return {"status": "removed", "entity_id": str(entity_id)}


# ── Entity-Specific Alerts (must be AFTER static routes) ─────────────


@router.get(
    "/alerts/{entity_id}",
    response_model=list[AlertEventResponse],
)
async def get_entity_alerts(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get alert events for a specific entity."""
    await _get_entity(session, entity_id)

    result = await session.execute(
        select(AlertEvent)
        .where(
            and_(
                AlertEvent.user_id == DEFAULT_USER_ID,
                AlertEvent.entity_id == entity_id,
            )
        )
        .order_by(AlertEvent.created_at.desc())
        .limit(50)
    )
    rows = result.scalars().all()

    return [
        AlertEventResponse(
            id=row.id,
            alert_type=row.alert_type,
            priority=row.priority,
            entity_id=row.entity_id,
            title=row.title,
            detail=row.detail,
            is_acknowledged=row.is_acknowledged,
            created_at=row.created_at,
        )
        for row in rows
    ]
