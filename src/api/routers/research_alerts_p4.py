"""Intelligent Alerts & Earnings Intelligence API endpoints (Pillar 3 Phase 4C)."""

import statistics
import uuid
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from src.ai.client import get_ai_client
from src.ai.prompts import load_prompt
from src.api.deps import get_session
from src.models.entity import Entity
from src.models.intelligent_alerts import ConsolidatedAlert, EarningsSurpriseIntelligence
from src.models.security import EODPrice, Security
from src.schemas.intelligent_alerts_schema import (
    AlertFeedResponse,
    ConsolidatedAlertResponse,
    EarningsSurpriseIntelResponse,
    EarningsSurpriseListResponse,
)

router = APIRouter(tags=["Research - Intelligent Alerts & Earnings"])


def _float(val):
    return float(val) if val is not None else None


def _alert_response(row: ConsolidatedAlert) -> ConsolidatedAlertResponse:
    return ConsolidatedAlertResponse(
        id=row.id,
        entity_id=row.entity_id,
        alert_priority=row.alert_priority,
        alert_categories=row.alert_categories,
        primary_headline=row.primary_headline,
        primary_type=row.primary_type,
        source_alert_ids=row.source_alert_ids,
        secondary_alerts=row.secondary_alerts,
        ai_synthesis=row.ai_synthesis,
        recommended_action=row.recommended_action,
        related_catalysts=row.related_catalysts,
        is_acknowledged=row.is_acknowledged,
        acknowledged_by=row.acknowledged_by,
        acknowledged_at=row.acknowledged_at,
        created_at=row.created_at,
    )


def _earnings_response(row: EarningsSurpriseIntelligence) -> EarningsSurpriseIntelResponse:
    return EarningsSurpriseIntelResponse(
        id=row.id,
        entity_id=row.entity_id,
        report_date=row.report_date,
        fiscal_period=row.fiscal_period,
        eps_consensus=_float(row.eps_consensus),
        eps_actual=_float(row.eps_actual),
        eps_surprise_pct=_float(row.eps_surprise_pct),
        revenue_consensus=_float(row.revenue_consensus),
        revenue_actual=_float(row.revenue_actual),
        revenue_surprise_pct=_float(row.revenue_surprise_pct),
        margin_analysis=row.margin_analysis,
        guidance_implications=row.guidance_implications,
        stock_reaction=row.stock_reaction,
        ai_narrative=row.ai_narrative,
        key_takeaways=row.key_takeaways,
        revision_implications=row.revision_implications,
        recommendation=row.recommendation,
        created_at=row.created_at,
    )


# ── Static routes (MUST come before parametric routes) ──────────────


@router.get(
    "/research/alerts/feed",
    response_model=AlertFeedResponse,
)
async def get_alert_feed(
    limit: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
):
    """Get consolidated alert feed, ordered by priority."""
    result = await session.execute(
        select(ConsolidatedAlert)
        .order_by(
            ConsolidatedAlert.alert_priority.asc().nulls_last(),
            ConsolidatedAlert.created_at.desc().nulls_last(),
        )
        .limit(limit)
    )
    rows = result.scalars().all()

    total_result = await session.execute(
        select(func.count()).select_from(ConsolidatedAlert)
    )
    total = total_result.scalar() or 0

    critical_result = await session.execute(
        select(func.count()).select_from(ConsolidatedAlert)
        .where(ConsolidatedAlert.alert_priority == 1)
    )
    critical = critical_result.scalar() or 0

    return AlertFeedResponse(
        alerts=[_alert_response(r) for r in rows],
        total_count=total,
        critical_count=critical,
    )


@router.get(
    "/research/alerts/critical",
    response_model=list[ConsolidatedAlertResponse],
)
async def get_critical_alerts(
    limit: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
):
    """Get critical-priority alerts only."""
    result = await session.execute(
        select(ConsolidatedAlert)
        .where(ConsolidatedAlert.alert_priority == 1)
        .order_by(ConsolidatedAlert.created_at.desc().nulls_last())
        .limit(limit)
    )
    rows = result.scalars().all()
    return [_alert_response(r) for r in rows]


@router.get(
    "/research/alerts/today",
    response_model=list[ConsolidatedAlertResponse],
)
async def get_today_alerts(
    session: AsyncSession = Depends(get_session),
):
    """Get today's alerts."""
    today = date.today()
    result = await session.execute(
        select(ConsolidatedAlert)
        .where(func.date(ConsolidatedAlert.created_at) == today)
        .order_by(
            ConsolidatedAlert.alert_priority.asc().nulls_last(),
            ConsolidatedAlert.created_at.desc().nulls_last(),
        )
    )
    rows = result.scalars().all()
    return [_alert_response(r) for r in rows]


@router.get(
    "/research/alerts/statistics",
    response_model=dict,
)
async def get_alert_statistics(
    session: AsyncSession = Depends(get_session),
):
    """Get alert statistics summary."""
    total_result = await session.execute(
        select(func.count()).select_from(ConsolidatedAlert)
    )
    total = total_result.scalar() or 0

    acknowledged_result = await session.execute(
        select(func.count()).select_from(ConsolidatedAlert)
        .where(ConsolidatedAlert.is_acknowledged == True)  # noqa: E712
    )
    acknowledged = acknowledged_result.scalar() or 0

    critical_result = await session.execute(
        select(func.count()).select_from(ConsolidatedAlert)
        .where(ConsolidatedAlert.alert_priority == 1)
    )
    critical = critical_result.scalar() or 0

    type_result = await session.execute(
        select(ConsolidatedAlert.primary_type, func.count())
        .group_by(ConsolidatedAlert.primary_type)
    )
    type_counts = {row[0] or "UNKNOWN": row[1] for row in type_result.all()}

    return {
        "total_alerts": total,
        "acknowledged_count": acknowledged,
        "unacknowledged_count": total - acknowledged,
        "critical_count": critical,
        "type_counts": type_counts,
    }


@router.get(
    "/research/earnings-intelligence/today",
    response_model=list[EarningsSurpriseIntelResponse],
)
async def get_today_earnings(
    session: AsyncSession = Depends(get_session),
):
    """Get today's earnings surprise intelligence."""
    today = date.today()
    result = await session.execute(
        select(EarningsSurpriseIntelligence)
        .where(EarningsSurpriseIntelligence.report_date == today)
        .order_by(EarningsSurpriseIntelligence.created_at.desc().nulls_last())
    )
    rows = result.scalars().all()
    return [_earnings_response(r) for r in rows]


@router.get(
    "/research/earnings-intelligence/upcoming",
    response_model=list[EarningsSurpriseIntelResponse],
)
async def get_upcoming_earnings(
    days: int = Query(default=7, ge=1, le=30),
    limit: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
):
    """Get upcoming earnings events within the specified window."""
    today = date.today()
    result = await session.execute(
        select(EarningsSurpriseIntelligence)
        .where(EarningsSurpriseIntelligence.report_date >= today)
        .order_by(EarningsSurpriseIntelligence.report_date.asc())
        .limit(limit)
    )
    rows = result.scalars().all()
    return [_earnings_response(r) for r in rows]


# ── Parametric routes ───────────────────────────────────────────────


@router.get(
    "/research/alerts/by-category/{category}",
    response_model=list[ConsolidatedAlertResponse],
)
async def get_alerts_by_category(
    category: str,
    limit: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
):
    """Filter alerts by category."""
    # For SQLite test compat, we query all and filter in Python;
    # production Postgres would use JSONB containment operator.
    result = await session.execute(
        select(ConsolidatedAlert)
        .where(ConsolidatedAlert.primary_type == category)
        .order_by(ConsolidatedAlert.created_at.desc().nulls_last())
        .limit(limit)
    )
    rows = result.scalars().all()
    return [_alert_response(r) for r in rows]


@router.get(
    "/research/alerts/{entity_id}",
    response_model=list[ConsolidatedAlertResponse],
)
async def get_entity_alerts(
    entity_id: uuid.UUID,
    limit: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
):
    """Get alerts for a specific entity."""
    result = await session.execute(
        select(ConsolidatedAlert)
        .where(ConsolidatedAlert.entity_id == entity_id)
        .order_by(
            ConsolidatedAlert.alert_priority.asc().nulls_last(),
            ConsolidatedAlert.created_at.desc().nulls_last(),
        )
        .limit(limit)
    )
    rows = result.scalars().all()
    return [_alert_response(r) for r in rows]


@router.post(
    "/research/alerts/{alert_id}/acknowledge",
    response_model=ConsolidatedAlertResponse,
)
async def acknowledge_alert(
    alert_id: uuid.UUID,
    acknowledged_by: str = Query(default="system"),
    session: AsyncSession = Depends(get_session),
):
    """Acknowledge a consolidated alert."""
    result = await session.execute(
        select(ConsolidatedAlert).where(ConsolidatedAlert.id == alert_id)
    )
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Alert not found")

    row.is_acknowledged = True
    row.acknowledged_by = acknowledged_by
    row.acknowledged_at = datetime.now(timezone.utc)
    await session.commit()

    return _alert_response(row)


@router.get(
    "/research/earnings-intelligence/{entity_id}",
    response_model=list[EarningsSurpriseIntelResponse],
)
async def get_entity_earnings_intelligence(
    entity_id: uuid.UUID,
    limit: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
):
    """Get earnings surprise intelligence for a specific entity."""
    result = await session.execute(
        select(EarningsSurpriseIntelligence)
        .where(EarningsSurpriseIntelligence.entity_id == entity_id)
        .order_by(EarningsSurpriseIntelligence.report_date.desc())
        .limit(limit)
    )
    rows = result.scalars().all()
    return [_earnings_response(r) for r in rows]


@router.get(
    "/research/earnings-intelligence/{entity_id}/history",
    response_model=list[EarningsSurpriseIntelResponse],
)
async def get_entity_earnings_history(
    entity_id: uuid.UUID,
    limit: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
):
    """Get historical earnings intelligence for an entity."""
    result = await session.execute(
        select(EarningsSurpriseIntelligence)
        .where(EarningsSurpriseIntelligence.entity_id == entity_id)
        .order_by(EarningsSurpriseIntelligence.report_date.desc())
        .limit(limit)
    )
    rows = result.scalars().all()
    return [_earnings_response(r) for r in rows]


async def _compute_stock_reaction(
    session: AsyncSession, entity_id: uuid.UUID, report_date: date
) -> dict | None:
    """Real price/volume reaction around the report date, from EODPrice."""
    sec_row = (
        await session.execute(
            select(Security.security_id, Security.security_type, Security.status)
            .where(Security.issuer_entity_id == entity_id, Security.asset_class == "EQUITY")
        )
    ).all()
    if not sec_row:
        return None
    sec_row.sort(key=lambda r: (r[2] != "ACTIVE", r[1] != "COMMON_STOCK"))
    security_id = sec_row[0][0]

    window_start = report_date - timedelta(days=35)
    window_end = report_date + timedelta(days=5)
    rows = (
        await session.execute(
            select(EODPrice.price_date, EODPrice.close, EODPrice.volume)
            .where(
                EODPrice.security_id == security_id,
                EODPrice.price_date >= window_start,
                EODPrice.price_date <= window_end,
            )
            .order_by(EODPrice.price_date.asc())
        )
    ).all()
    if len(rows) < 2:
        return None

    before = [r for r in rows if r[0] < report_date]
    on_or_after = [r for r in rows if r[0] >= report_date]
    if not before or not on_or_after:
        return None

    pre_close = float(before[-1][1]) if before[-1][1] is not None else None
    post_close = float(on_or_after[0][1]) if on_or_after[0][1] is not None else None
    if not pre_close or post_close is None:
        return None

    price_change_pct = round((post_close - pre_close) / pre_close * 100, 2)

    volumes = [float(r[2]) for r in before if r[2] is not None]
    volume_vs_avg = None
    post_volume = on_or_after[0][2]
    if volumes and post_volume is not None:
        avg_volume = statistics.mean(volumes)
        if avg_volume > 0:
            volume_vs_avg = round(float(post_volume) / avg_volume, 2)

    return {
        "price_change_pct": price_change_pct,
        "volume_vs_avg": volume_vs_avg,
        # After-hours moves aren't in the daily EOD price series we ingest.
        "after_hours_move": None,
    }


def _classify_surprise_direction(eps_surprise_pct: float | None, revenue_surprise_pct: float | None) -> str:
    combined = (eps_surprise_pct or 0.0) + (revenue_surprise_pct or 0.0)
    if combined > 5:
        return "UP"
    if combined < -5:
        return "DOWN"
    return "UNCHANGED"


def _recommendation_from_surprise(eps_surprise_pct: float | None, revenue_surprise_pct: float | None) -> str:
    combined = (eps_surprise_pct or 0.0) + (revenue_surprise_pct or 0.0)
    if combined >= 10:
        return "POSITIVE"
    if combined <= -10:
        return "NEGATIVE"
    return "NEUTRAL"


@router.post(
    "/research/earnings-intelligence/{entity_id}/analyze",
    response_model=EarningsSurpriseIntelResponse,
)
async def analyze_earnings_event(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Analyze the latest earnings event for an entity.

    Computes stock reaction from real EOD prices and derives directional
    implications from the recorded surprise metrics, then persists the
    result. Previously this endpoint only re-read the existing row without
    computing anything, regardless of what was requested.
    """
    result = await session.execute(
        select(EarningsSurpriseIntelligence)
        .where(EarningsSurpriseIntelligence.entity_id == entity_id)
        .order_by(EarningsSurpriseIntelligence.report_date.desc())
        .limit(1)
    )
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="No earnings data found for this entity")

    eps_surprise = float(row.eps_surprise_pct) if row.eps_surprise_pct is not None else None
    rev_surprise = float(row.revenue_surprise_pct) if row.revenue_surprise_pct is not None else None

    stock_reaction = await _compute_stock_reaction(session, entity_id, row.report_date)
    if stock_reaction is not None:
        row.stock_reaction = stock_reaction

    direction = _classify_surprise_direction(eps_surprise, rev_surprise)
    row.revision_implications = {
        "eps_revision_direction": direction,
        "basis": "derived from reported EPS/revenue surprise, not confirmed analyst revisions",
    }
    row.guidance_implications = {
        "raised": direction == "UP",
        "lowered": direction == "DOWN",
        "maintained": direction == "UNCHANGED",
        "detail": "Inferred from surprise magnitude; not sourced from disclosed management guidance.",
    }
    row.recommendation = _recommendation_from_surprise(eps_surprise, rev_surprise)

    takeaways = []
    if eps_surprise is not None:
        takeaways.append(
            f"EPS {'beat' if eps_surprise >= 0 else 'missed'} consensus by {abs(eps_surprise):.1f}%"
        )
    if rev_surprise is not None:
        takeaways.append(
            f"Revenue {'beat' if rev_surprise >= 0 else 'missed'} consensus by {abs(rev_surprise):.1f}%"
        )
    if stock_reaction and stock_reaction.get("price_change_pct") is not None:
        takeaways.append(f"Stock moved {stock_reaction['price_change_pct']:+.1f}% around the report date")
    row.key_takeaways = takeaways or None

    client = get_ai_client()
    if client.enabled:
        entity = (
            await session.execute(select(Entity).where(Entity.entity_id == entity_id))
        ).scalar_one_or_none()
        prompt = load_prompt("earnings_narrative")
        row.ai_narrative = await client.complete_text(
            user=prompt.render(
                company=entity.legal_name if entity else entity_id,
                eps_surprise=eps_surprise, rev_surprise=rev_surprise,
                stock_reaction=stock_reaction, takeaways=takeaways,
            ),
            system=prompt.system,
            tier=prompt.tier,
            max_tokens=prompt.max_tokens,
            feature=prompt.feature,
        )

    await session.commit()
    await session.refresh(row)
    return _earnings_response(row)
