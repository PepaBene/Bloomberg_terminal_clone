"""Research Briefings API endpoints (Pillar 3 Phase 4A)."""

import uuid
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_session
from src.models.morning_briefing import MorningBriefing, BriefingPreference
from src.schemas.morning_briefing_schema import (
    BriefingPreferenceRequest,
    BriefingPreferenceResponse,
    MorningBriefingResponse,
)

router = APIRouter(tags=["Research - Morning Briefings"])


def _briefing_response(row: MorningBriefing) -> MorningBriefingResponse:
    return MorningBriefingResponse(
        id=row.id,
        user_id=row.user_id,
        briefing_date=row.briefing_date,
        regional_context=row.regional_context,
        executive_summary=row.executive_summary,
        portfolio_impact=row.portfolio_impact,
        key_news=row.key_news,
        thesis_updates=row.thesis_updates,
        macro_context=row.macro_context,
        actionable_insights=row.actionable_insights,
        delivery_format=row.delivery_format,
        ai_enabled=row.ai_enabled,
    )


# ── Static routes (MUST come before parametric routes) ──────────────


@router.get(
    "/research/briefings/today",
    response_model=list[MorningBriefingResponse],
)
async def get_todays_briefing(
    user_id: str = Query(default="default_user"),
    session: AsyncSession = Depends(get_session),
):
    """Get today's morning briefing."""
    today = date.today()
    result = await session.execute(
        select(MorningBriefing)
        .where(MorningBriefing.user_id == user_id)
        .where(MorningBriefing.briefing_date == today)
        .order_by(MorningBriefing.briefing_date.desc())
    )
    rows = result.scalars().all()
    return [_briefing_response(row) for row in rows]


@router.get(
    "/research/briefings/history",
    response_model=list[MorningBriefingResponse],
)
async def get_briefing_history(
    user_id: str = Query(default="default_user"),
    limit: int = Query(default=30, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
):
    """Get past briefings for a user."""
    result = await session.execute(
        select(MorningBriefing)
        .where(MorningBriefing.user_id == user_id)
        .order_by(MorningBriefing.briefing_date.desc())
        .limit(limit)
    )
    rows = result.scalars().all()
    return [_briefing_response(row) for row in rows]


@router.get(
    "/research/briefings/preferences",
    response_model=BriefingPreferenceResponse | None,
)
async def get_briefing_preferences(
    user_id: str = Query(default="default_user"),
    session: AsyncSession = Depends(get_session),
):
    """Get briefing preferences for a user."""
    result = await session.execute(
        select(BriefingPreference)
        .where(BriefingPreference.user_id == user_id)
    )
    row = result.scalar_one_or_none()
    if not row:
        return None

    return BriefingPreferenceResponse(
        id=row.id,
        user_id=row.user_id,
        portfolio_entity_ids=row.portfolio_entity_ids,
        watchlist_entity_ids=row.watchlist_entity_ids,
        sector_focus=row.sector_focus,
        risk_tolerance=row.risk_tolerance,
        delivery_time_utc=row.delivery_time_utc,
        delivery_format=row.delivery_format,
        timezone=row.timezone,
        is_active=row.is_active,
    )


@router.put(
    "/research/briefings/preferences",
    response_model=BriefingPreferenceResponse,
)
async def update_briefing_preferences(
    body: BriefingPreferenceRequest,
    session: AsyncSession = Depends(get_session),
):
    """Create or update briefing preferences."""
    result = await session.execute(
        select(BriefingPreference)
        .where(BriefingPreference.user_id == body.user_id)
    )
    pref = result.scalar_one_or_none()

    if pref:
        pref.portfolio_entity_ids = body.portfolio_entity_ids
        pref.watchlist_entity_ids = body.watchlist_entity_ids
        pref.sector_focus = body.sector_focus
        pref.risk_tolerance = body.risk_tolerance
        pref.delivery_time_utc = body.delivery_time_utc
        pref.delivery_format = body.delivery_format
        pref.timezone = body.timezone
        pref.is_active = body.is_active
    else:
        pref = BriefingPreference(
            id=uuid.uuid4(),
            user_id=body.user_id,
            portfolio_entity_ids=body.portfolio_entity_ids,
            watchlist_entity_ids=body.watchlist_entity_ids,
            sector_focus=body.sector_focus,
            risk_tolerance=body.risk_tolerance,
            delivery_time_utc=body.delivery_time_utc,
            delivery_format=body.delivery_format,
            timezone=body.timezone,
            is_active=body.is_active,
        )
        session.add(pref)

    await session.commit()

    return BriefingPreferenceResponse(
        id=pref.id,
        user_id=pref.user_id,
        portfolio_entity_ids=pref.portfolio_entity_ids,
        watchlist_entity_ids=pref.watchlist_entity_ids,
        sector_focus=pref.sector_focus,
        risk_tolerance=pref.risk_tolerance,
        delivery_time_utc=pref.delivery_time_utc,
        delivery_format=pref.delivery_format,
        timezone=pref.timezone,
        is_active=pref.is_active,
    )


@router.get(
    "/research/briefings/portfolio-impact",
    response_model=dict,
)
async def get_portfolio_impact(
    user_id: str = Query(default="default_user"),
    session: AsyncSession = Depends(get_session),
):
    """Get portfolio impact section from today's briefing."""
    today = date.today()
    result = await session.execute(
        select(MorningBriefing)
        .where(MorningBriefing.user_id == user_id)
        .where(MorningBriefing.briefing_date == today)
        .order_by(MorningBriefing.briefing_date.desc())
        .limit(1)
    )
    row = result.scalar_one_or_none()
    if not row:
        return {"portfolio_impact": None, "briefing_date": str(today)}

    return {
        "portfolio_impact": row.portfolio_impact,
        "briefing_date": str(row.briefing_date),
    }


@router.get(
    "/research/briefings/macro-summary",
    response_model=dict,
)
async def get_macro_summary(
    user_id: str = Query(default="default_user"),
    session: AsyncSession = Depends(get_session),
):
    """Get macro context section from today's briefing."""
    today = date.today()
    result = await session.execute(
        select(MorningBriefing)
        .where(MorningBriefing.user_id == user_id)
        .where(MorningBriefing.briefing_date == today)
        .order_by(MorningBriefing.briefing_date.desc())
        .limit(1)
    )
    row = result.scalar_one_or_none()
    if not row:
        return {"macro_context": None, "briefing_date": str(today)}

    return {
        "macro_context": row.macro_context,
        "briefing_date": str(row.briefing_date),
    }


@router.post(
    "/research/briefings/generate",
    response_model=MorningBriefingResponse,
)
async def generate_briefing(
    user_id: str = Query(default="default_user"),
    session: AsyncSession = Depends(get_session),
):
    """Generate an on-demand briefing."""
    today = date.today()
    briefing = MorningBriefing(
        id=uuid.uuid4(),
        user_id=user_id,
        briefing_date=today,
        regional_context="US",
        executive_summary="On-demand briefing generated.",
        delivery_format="FULL",
        ai_enabled=False,
    )
    session.add(briefing)
    await session.commit()

    return _briefing_response(briefing)


# ── Parametric routes ───────────────────────────────────────────────


@router.get(
    "/research/briefings/{briefing_id}",
    response_model=MorningBriefingResponse,
)
async def get_briefing_by_id(
    briefing_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get a specific briefing by ID."""
    result = await session.execute(
        select(MorningBriefing)
        .where(MorningBriefing.id == briefing_id)
    )
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Briefing not found")

    return _briefing_response(row)
