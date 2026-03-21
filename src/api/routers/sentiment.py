"""Sentiment Analysis API endpoints (Pillar 2 Supplement – Part 8)."""

import uuid
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.ai.llm_client import get_llm_client
from src.api.deps import get_session
from src.engines.sentiment_analysis import (
    keyword_sentiment,
    compute_aggregate_sentiment,
    analyze_earnings_call,
)
from src.models.entity import Entity
from src.models.sentiment import SentimentScore, SentimentAggregate, EarningsCallSentiment
from src.schemas.sentiment import (
    EarningsCallSentimentResponse,
    ScoreTextRequest,
    SentimentAggregateResponse,
    SentimentAnomalyResponse,
    SentimentHistoryPoint,
    SentimentHistoryResponse,
    SentimentScoreResponse,
)

router = APIRouter(tags=["Sentiment Analysis"])


async def _get_entity(session: AsyncSession, entity_id: uuid.UUID) -> Entity:
    result = await session.execute(
        select(Entity).where(Entity.entity_id == entity_id)
    )
    entity = result.scalar_one_or_none()
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
    return entity


# NOTE: /score and /anomalies are static paths — define BEFORE /{entity_id}
@router.post(
    "/analytics/sentiment/score",
    response_model=SentimentScoreResponse,
)
async def score_text(
    body: ScoreTextRequest,
):
    """Score arbitrary text for sentiment (no DB needed)."""
    llm = get_llm_client()
    result = keyword_sentiment(body.text)

    return SentimentScoreResponse(
        sentiment=result.sentiment,
        sentiment_score=result.score,
        confidence=result.confidence,
        ai_enabled=False,
    )


@router.get(
    "/analytics/sentiment/anomalies",
    response_model=list[SentimentAnomalyResponse],
)
async def get_sentiment_anomalies(
    session: AsyncSession = Depends(get_session),
    timeframe: str = Query("ROLLING_30D"),
):
    """Get companies with sentiment anomalies."""
    result = await session.execute(
        select(SentimentAggregate)
        .where(SentimentAggregate.anomaly_flag.is_(True))
        .where(SentimentAggregate.timeframe == timeframe)
        .order_by(SentimentAggregate.as_of_date.desc())
        .limit(50)
    )
    rows = result.scalars().all()

    return [
        SentimentAnomalyResponse(
            entity_id=row.entity_id,
            avg_sentiment=float(row.avg_sentiment),
            anomaly_flag=True,
            timeframe=row.timeframe,
        )
        for row in rows
    ]


@router.get(
    "/analytics/sentiment/{entity_id}",
    response_model=SentimentAggregateResponse,
)
async def get_sentiment_aggregate(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    timeframe: str = Query("ROLLING_30D"),
):
    """Get aggregate sentiment for a company."""
    await _get_entity(session, entity_id)

    # Check for existing aggregate
    result = await session.execute(
        select(SentimentAggregate)
        .where(SentimentAggregate.entity_id == entity_id)
        .where(SentimentAggregate.timeframe == timeframe)
        .order_by(SentimentAggregate.as_of_date.desc())
        .limit(1)
    )
    existing = result.scalar_one_or_none()

    if existing:
        return SentimentAggregateResponse(
            entity_id=existing.entity_id,
            as_of_date=existing.as_of_date,
            timeframe=existing.timeframe,
            avg_sentiment=float(existing.avg_sentiment),
            sentiment_momentum=float(existing.sentiment_momentum) if existing.sentiment_momentum is not None else None,
            article_count=existing.article_count,
            positive_pct=float(existing.positive_pct) if existing.positive_pct is not None else 0.0,
            negative_pct=float(existing.negative_pct) if existing.negative_pct is not None else 0.0,
            anomaly_flag=existing.anomaly_flag,
        )

    # No aggregate exists — return empty
    return SentimentAggregateResponse(
        entity_id=entity_id,
        as_of_date=date.today(),
        timeframe=timeframe,
        avg_sentiment=0.0,
        article_count=0,
    )


@router.get(
    "/analytics/sentiment/{entity_id}/history",
    response_model=SentimentHistoryResponse,
)
async def get_sentiment_history(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    limit: int = Query(50, ge=1, le=200),
):
    """Get sentiment score time series for a company."""
    await _get_entity(session, entity_id)

    result = await session.execute(
        select(SentimentScore)
        .where(SentimentScore.entity_id == entity_id)
        .order_by(SentimentScore.source_date.desc())
        .limit(limit)
    )
    rows = result.scalars().all()

    history = [
        SentimentHistoryPoint(
            date=row.source_date,
            sentiment=row.sentiment,
            score=float(row.sentiment_score),
            source_type=row.source_type,
        )
        for row in rows
    ]

    return SentimentHistoryResponse(
        entity_id=entity_id,
        history=history,
        total_count=len(history),
    )


@router.get(
    "/analytics/sentiment/{entity_id}/earnings-calls",
    response_model=list[EarningsCallSentimentResponse],
)
async def get_earnings_call_sentiment(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get earnings call sentiment history for a company."""
    await _get_entity(session, entity_id)

    result = await session.execute(
        select(EarningsCallSentiment)
        .where(EarningsCallSentiment.entity_id == entity_id)
        .order_by(EarningsCallSentiment.call_date.desc())
        .limit(20)
    )
    rows = result.scalars().all()

    return [
        EarningsCallSentimentResponse(
            entity_id=row.entity_id,
            call_date=row.call_date,
            fiscal_year=row.fiscal_year,
            fiscal_quarter=row.fiscal_quarter,
            overall_tone=float(row.overall_tone),
            management_tone=float(row.management_tone) if row.management_tone is not None else None,
            qa_tone=float(row.qa_tone) if row.qa_tone is not None else None,
            tone_vs_prior=float(row.tone_vs_prior) if row.tone_vs_prior is not None else None,
            hedging_count=row.hedging_count,
            confidence_count=row.confidence_count,
            topic_sentiments=row.topic_sentiments,
            ai_enabled=row.ai_enabled,
        )
        for row in rows
    ]
