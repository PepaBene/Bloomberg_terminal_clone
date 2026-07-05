"""Earnings Intelligence P2 API endpoints (Pillar 3 Phase 2)."""

import uuid
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_session
from src.models.entity import Entity
from src.models.earnings_transcript import EarningsCallTranscript
from src.models.earnings_intelligence import EarningsSurprise, GuidanceTracking
from src.models.calendar import CalendarEvent
from src.schemas.earnings_transcript import (
    CallSentimentHistoryResponse,
    EarningsCalendarResponse,
    GuidanceCredibilityResponse,
    GuidanceResponse,
    SentimentHistoryPoint,
    SurpriseResponse,
    TranscriptResponse,
    TranscriptSentimentResponse,
    TranscriptSummaryResponse,
    TranscriptTopicsResponse,
)

router = APIRouter(tags=["Earnings Intelligence"])


async def _get_entity(session: AsyncSession, entity_id: uuid.UUID) -> Entity:
    result = await session.execute(
        select(Entity).where(Entity.entity_id == entity_id)
    )
    entity = result.scalar_one_or_none()
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
    return entity


# ── Static routes (MUST be before parametric) ────────────────────────


@router.get(
    "/earnings/surprises/today",
    response_model=list[SurpriseResponse],
)
async def get_todays_surprises(
    session: AsyncSession = Depends(get_session),
):
    """Get all earnings surprises announced today."""
    today = date.today()
    stmt = (
        select(EarningsSurprise)
        .where(EarningsSurprise.announcement_date == today)
        .order_by(EarningsSurprise.eps_surprise_pct.desc().nulls_last())
    )
    result = await session.execute(stmt)
    rows = result.scalars().all()

    return [
        SurpriseResponse(
            id=r.surprise_id,
            entity_id=r.entity_id,
            fiscal_year=r.fiscal_year,
            fiscal_quarter=r.fiscal_quarter,
            actual_eps=float(r.actual_eps) if r.actual_eps is not None else None,
            consensus_eps=float(r.consensus_eps) if r.consensus_eps is not None else None,
            eps_surprise_pct=float(r.eps_surprise_pct) if r.eps_surprise_pct is not None else None,
            actual_revenue=float(r.actual_revenue) if r.actual_revenue is not None else None,
            revenue_surprise_pct=float(r.revenue_surprise_pct) if r.revenue_surprise_pct is not None else None,
            ebitda_surprise_pct=float(r.ebitda_surprise_pct) if r.ebitda_surprise_pct is not None else None,
            beat_and_fell=r.beat_and_fell,
            consecutive_beats=r.consecutive_beats,
            price_reaction_pct=float(r.price_reaction_pct) if r.price_reaction_pct is not None else None,
            price_reaction_5d_pct=float(r.price_reaction_5d_pct) if r.price_reaction_5d_pct is not None else None,
        )
        for r in rows
    ]


@router.get(
    "/earnings/calendar",
    response_model=EarningsCalendarResponse,
)
async def get_earnings_calendar(
    session: AsyncSession = Depends(get_session),
    target_date: date | None = Query(None, alias="date", description="Target date (defaults to today)"),
):
    """Get earnings calendar for a specific date."""
    d = target_date or date.today()
    stmt = (
        select(CalendarEvent)
        .where(
            and_(
                CalendarEvent.event_date == d,
                CalendarEvent.event_type.in_(["EARNINGS", "EARNINGS_RELEASE"]),
            )
        )
        .order_by(CalendarEvent.event_date)
    )
    result = await session.execute(stmt)
    rows = result.scalars().all()

    events = [
        {
            "event_id": str(r.event_id),
            "entity_id": str(r.entity_id) if r.entity_id else None,
            "event_type": r.event_type,
            "event_date": r.event_date.isoformat(),
            "event_description": r.event_description,
        }
        for r in rows
    ]
    return EarningsCalendarResponse(events=events, total_count=len(events))


@router.get(
    "/earnings/calendar/upcoming",
    response_model=EarningsCalendarResponse,
)
async def get_upcoming_earnings(
    session: AsyncSession = Depends(get_session),
    days: int = Query(7, ge=1, le=90, description="Number of days ahead"),
):
    """Get upcoming earnings events for the next N days."""
    today = date.today()
    end = today + timedelta(days=days)
    stmt = (
        select(CalendarEvent)
        .where(
            and_(
                CalendarEvent.event_date >= today,
                CalendarEvent.event_date <= end,
                CalendarEvent.event_type.in_(["EARNINGS", "EARNINGS_RELEASE"]),
            )
        )
        .order_by(CalendarEvent.event_date)
    )
    result = await session.execute(stmt)
    rows = result.scalars().all()

    events = [
        {
            "event_id": str(r.event_id),
            "entity_id": str(r.entity_id) if r.entity_id else None,
            "event_type": r.event_type,
            "event_date": r.event_date.isoformat(),
            "event_description": r.event_description,
        }
        for r in rows
    ]
    return EarningsCalendarResponse(events=events, total_count=len(events))


# ── Parametric routes ─────────────────────────────────────────────────


@router.get(
    "/earnings/{entity_id}/calls",
    response_model=list[TranscriptResponse],
)
async def list_transcripts(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    limit: int = Query(20, ge=1, le=100),
):
    """List earnings call transcripts for an entity."""
    await _get_entity(session, entity_id)

    stmt = (
        select(EarningsCallTranscript)
        .where(EarningsCallTranscript.entity_id == entity_id)
        .order_by(EarningsCallTranscript.call_date.desc())
        .limit(limit)
    )
    result = await session.execute(stmt)
    rows = result.scalars().all()

    return [
        TranscriptResponse(
            id=r.id,
            entity_id=r.entity_id,
            call_date=r.call_date,
            fiscal_year=r.fiscal_year,
            fiscal_quarter=r.fiscal_quarter,
            call_type=r.call_type,
            participants=r.participants,
            overall_tone=float(r.overall_tone) if r.overall_tone is not None else None,
            prepared_tone=float(r.prepared_tone) if r.prepared_tone is not None else None,
            qa_tone=float(r.qa_tone) if r.qa_tone is not None else None,
            tone_divergence=float(r.tone_divergence) if r.tone_divergence is not None else None,
            hedging_ratio=float(r.hedging_ratio) if r.hedging_ratio is not None else None,
            confidence_ratio=float(r.confidence_ratio) if r.confidence_ratio is not None else None,
            forward_looking_pct=float(r.forward_looking_pct) if r.forward_looking_pct is not None else None,
            management_outlook=r.management_outlook,
            source_url=r.source_url,
            ai_enabled=r.ai_enabled,
        )
        for r in rows
    ]


@router.get(
    "/earnings/{entity_id}/calls/latest",
    response_model=TranscriptResponse,
)
async def get_latest_transcript(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get the most recent earnings call transcript."""
    await _get_entity(session, entity_id)

    stmt = (
        select(EarningsCallTranscript)
        .where(EarningsCallTranscript.entity_id == entity_id)
        .order_by(EarningsCallTranscript.call_date.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    r = result.scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="No transcripts found for this entity")

    return TranscriptResponse(
        id=r.id,
        entity_id=r.entity_id,
        call_date=r.call_date,
        fiscal_year=r.fiscal_year,
        fiscal_quarter=r.fiscal_quarter,
        call_type=r.call_type,
        participants=r.participants,
        overall_tone=float(r.overall_tone) if r.overall_tone is not None else None,
        prepared_tone=float(r.prepared_tone) if r.prepared_tone is not None else None,
        qa_tone=float(r.qa_tone) if r.qa_tone is not None else None,
        tone_divergence=float(r.tone_divergence) if r.tone_divergence is not None else None,
        hedging_ratio=float(r.hedging_ratio) if r.hedging_ratio is not None else None,
        confidence_ratio=float(r.confidence_ratio) if r.confidence_ratio is not None else None,
        forward_looking_pct=float(r.forward_looking_pct) if r.forward_looking_pct is not None else None,
        management_outlook=r.management_outlook,
        source_url=r.source_url,
        ai_enabled=r.ai_enabled,
    )


@router.get(
    "/earnings/{entity_id}/calls/latest/summary",
    response_model=TranscriptSummaryResponse,
)
async def get_latest_transcript_summary(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get AI-generated summary of the latest earnings call."""
    await _get_entity(session, entity_id)

    stmt = (
        select(EarningsCallTranscript)
        .where(EarningsCallTranscript.entity_id == entity_id)
        .order_by(EarningsCallTranscript.call_date.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    r = result.scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="No transcripts found for this entity")

    return TranscriptSummaryResponse(
        entity_id=r.entity_id,
        call_date=r.call_date,
        ai_summary=r.ai_summary,
        key_takeaways=r.key_takeaways if isinstance(r.key_takeaways, list) else None,
        management_outlook=r.management_outlook,
        analyst_concerns=r.analyst_concerns if isinstance(r.analyst_concerns, list) else None,
        ai_enabled=r.ai_enabled,
    )


@router.get(
    "/earnings/{entity_id}/calls/latest/sentiment",
    response_model=TranscriptSentimentResponse,
)
async def get_latest_transcript_sentiment(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get tone/sentiment breakdown of the latest earnings call."""
    await _get_entity(session, entity_id)

    stmt = (
        select(EarningsCallTranscript)
        .where(EarningsCallTranscript.entity_id == entity_id)
        .order_by(EarningsCallTranscript.call_date.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    r = result.scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="No transcripts found for this entity")

    return TranscriptSentimentResponse(
        entity_id=r.entity_id,
        call_date=r.call_date,
        overall_tone=float(r.overall_tone) if r.overall_tone is not None else None,
        prepared_tone=float(r.prepared_tone) if r.prepared_tone is not None else None,
        qa_tone=float(r.qa_tone) if r.qa_tone is not None else None,
        ceo_tone=float(r.ceo_tone) if r.ceo_tone is not None else None,
        cfo_tone=float(r.cfo_tone) if r.cfo_tone is not None else None,
        tone_divergence=float(r.tone_divergence) if r.tone_divergence is not None else None,
        hedging_ratio=float(r.hedging_ratio) if r.hedging_ratio is not None else None,
        confidence_ratio=float(r.confidence_ratio) if r.confidence_ratio is not None else None,
    )


@router.get(
    "/earnings/{entity_id}/calls/latest/topics",
    response_model=TranscriptTopicsResponse,
)
async def get_latest_transcript_topics(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get topic analysis of the latest earnings call."""
    await _get_entity(session, entity_id)

    stmt = (
        select(EarningsCallTranscript)
        .where(EarningsCallTranscript.entity_id == entity_id)
        .order_by(EarningsCallTranscript.call_date.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    r = result.scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="No transcripts found for this entity")

    return TranscriptTopicsResponse(
        entity_id=r.entity_id,
        call_date=r.call_date,
        mgmt_topics=r.mgmt_topics if isinstance(r.mgmt_topics, list) else [],
        qa_topics=r.qa_topics if isinstance(r.qa_topics, list) else [],
        absent_topics=r.absent_topics if isinstance(r.absent_topics, list) else [],
        new_topics=r.new_topics if isinstance(r.new_topics, list) else [],
        buzzword_counts=r.buzzword_counts if isinstance(r.buzzword_counts, dict) else {},
    )


@router.get(
    "/earnings/{entity_id}/calls/sentiment/history",
    response_model=CallSentimentHistoryResponse,
)
async def get_sentiment_history(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    limit: int = Query(20, ge=1, le=100),
):
    """Get historical tone data across earnings calls."""
    await _get_entity(session, entity_id)

    stmt = (
        select(EarningsCallTranscript)
        .where(EarningsCallTranscript.entity_id == entity_id)
        .order_by(EarningsCallTranscript.call_date.desc())
        .limit(limit)
    )
    result = await session.execute(stmt)
    rows = result.scalars().all()

    history = [
        SentimentHistoryPoint(
            call_date=r.call_date,
            fiscal_year=r.fiscal_year,
            fiscal_quarter=r.fiscal_quarter,
            overall_tone=float(r.overall_tone) if r.overall_tone is not None else None,
            prepared_tone=float(r.prepared_tone) if r.prepared_tone is not None else None,
            qa_tone=float(r.qa_tone) if r.qa_tone is not None else None,
        )
        for r in rows
    ]

    return CallSentimentHistoryResponse(entity_id=entity_id, history=history)


@router.get(
    "/earnings/{entity_id}/surprises",
    response_model=list[SurpriseResponse],
)
async def get_surprise_history(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    limit: int = Query(20, ge=1, le=100),
):
    """Get earnings surprise history for an entity."""
    await _get_entity(session, entity_id)

    stmt = (
        select(EarningsSurprise)
        .where(EarningsSurprise.entity_id == entity_id)
        .order_by(EarningsSurprise.fiscal_year.desc(), EarningsSurprise.fiscal_quarter.desc())
        .limit(limit)
    )
    result = await session.execute(stmt)
    rows = result.scalars().all()

    return [
        SurpriseResponse(
            id=r.surprise_id,
            entity_id=r.entity_id,
            fiscal_year=r.fiscal_year,
            fiscal_quarter=r.fiscal_quarter,
            actual_eps=float(r.actual_eps) if r.actual_eps is not None else None,
            consensus_eps=float(r.consensus_eps) if r.consensus_eps is not None else None,
            eps_surprise_pct=float(r.eps_surprise_pct) if r.eps_surprise_pct is not None else None,
            actual_revenue=float(r.actual_revenue) if r.actual_revenue is not None else None,
            revenue_surprise_pct=float(r.revenue_surprise_pct) if r.revenue_surprise_pct is not None else None,
            ebitda_surprise_pct=float(r.ebitda_surprise_pct) if r.ebitda_surprise_pct is not None else None,
            beat_and_fell=r.beat_and_fell,
            consecutive_beats=r.consecutive_beats,
            price_reaction_pct=float(r.price_reaction_pct) if r.price_reaction_pct is not None else None,
            price_reaction_5d_pct=float(r.price_reaction_5d_pct) if r.price_reaction_5d_pct is not None else None,
        )
        for r in rows
    ]


@router.get(
    "/earnings/{entity_id}/surprises/latest",
    response_model=SurpriseResponse,
)
async def get_latest_surprise(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get the most recent earnings surprise for an entity."""
    await _get_entity(session, entity_id)

    stmt = (
        select(EarningsSurprise)
        .where(EarningsSurprise.entity_id == entity_id)
        .order_by(EarningsSurprise.fiscal_year.desc(), EarningsSurprise.fiscal_quarter.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    r = result.scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="No earnings surprises found for this entity")

    return SurpriseResponse(
        id=r.surprise_id,
        entity_id=r.entity_id,
        fiscal_year=r.fiscal_year,
        fiscal_quarter=r.fiscal_quarter,
        actual_eps=float(r.actual_eps) if r.actual_eps is not None else None,
        consensus_eps=float(r.consensus_eps) if r.consensus_eps is not None else None,
        eps_surprise_pct=float(r.eps_surprise_pct) if r.eps_surprise_pct is not None else None,
        actual_revenue=float(r.actual_revenue) if r.actual_revenue is not None else None,
        revenue_surprise_pct=float(r.revenue_surprise_pct) if r.revenue_surprise_pct is not None else None,
        ebitda_surprise_pct=float(r.ebitda_surprise_pct) if r.ebitda_surprise_pct is not None else None,
        beat_and_fell=r.beat_and_fell,
        consecutive_beats=r.consecutive_beats,
        price_reaction_pct=float(r.price_reaction_pct) if r.price_reaction_pct is not None else None,
        price_reaction_5d_pct=float(r.price_reaction_5d_pct) if r.price_reaction_5d_pct is not None else None,
    )


@router.get(
    "/earnings/{entity_id}/guidance",
    response_model=list[GuidanceResponse],
)
async def get_guidance(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get current guidance for an entity."""
    await _get_entity(session, entity_id)

    # Latest fiscal year guidance
    max_fy_result = await session.execute(
        select(func.max(GuidanceTracking.guidance_fiscal_year)).where(
            GuidanceTracking.entity_id == entity_id
        )
    )
    max_fy = max_fy_result.scalar_one_or_none()
    if max_fy is None:
        return []

    stmt = (
        select(GuidanceTracking)
        .where(
            and_(
                GuidanceTracking.entity_id == entity_id,
                GuidanceTracking.guidance_fiscal_year == max_fy,
            )
        )
        .order_by(GuidanceTracking.guidance_date.desc())
    )
    result = await session.execute(stmt)
    rows = result.scalars().all()

    return [
        GuidanceResponse(
            id=r.guidance_id,
            entity_id=r.entity_id,
            metric=r.metric,
            guidance_low=float(r.guidance_low) if r.guidance_low is not None else None,
            guidance_high=float(r.guidance_high) if r.guidance_high is not None else None,
            guidance_midpoint=float(r.guidance_midpoint) if r.guidance_midpoint is not None else None,
            guidance_type=r.guidance_type,
            guidance_vs_consensus=r.guidance_vs_consensus,
            credibility_score=float(r.credibility_score) if r.credibility_score is not None else None,
        )
        for r in rows
    ]


@router.get(
    "/earnings/{entity_id}/guidance/history",
    response_model=list[GuidanceResponse],
)
async def get_guidance_history(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    limit: int = Query(40, ge=1, le=200),
):
    """Get guidance track record for an entity."""
    await _get_entity(session, entity_id)

    stmt = (
        select(GuidanceTracking)
        .where(GuidanceTracking.entity_id == entity_id)
        .order_by(GuidanceTracking.guidance_date.desc())
        .limit(limit)
    )
    result = await session.execute(stmt)
    rows = result.scalars().all()

    return [
        GuidanceResponse(
            id=r.guidance_id,
            entity_id=r.entity_id,
            metric=r.metric,
            guidance_low=float(r.guidance_low) if r.guidance_low is not None else None,
            guidance_high=float(r.guidance_high) if r.guidance_high is not None else None,
            guidance_midpoint=float(r.guidance_midpoint) if r.guidance_midpoint is not None else None,
            guidance_type=r.guidance_type,
            guidance_vs_consensus=r.guidance_vs_consensus,
            credibility_score=float(r.credibility_score) if r.credibility_score is not None else None,
        )
        for r in rows
    ]


@router.get(
    "/earnings/{entity_id}/guidance/credibility",
    response_model=GuidanceCredibilityResponse,
)
async def get_guidance_credibility(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get guidance credibility score for an entity."""
    await _get_entity(session, entity_id)

    stmt = (
        select(GuidanceTracking)
        .where(
            and_(
                GuidanceTracking.entity_id == entity_id,
                GuidanceTracking.credibility_score.isnot(None),
            )
        )
        .order_by(GuidanceTracking.guidance_date.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    r = result.scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="No credibility data found for this entity")

    return GuidanceCredibilityResponse(
        entity_id=r.entity_id,
        credibility_score=float(r.credibility_score) if r.credibility_score is not None else 0.0,
        historical_accuracy=float(r.historical_accuracy) if r.historical_accuracy is not None else None,
        consistency_score=float(r.consistency_score) if r.consistency_score is not None else None,
    )
