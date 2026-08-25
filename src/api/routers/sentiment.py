"""Sentiment Analysis API endpoints (Pillar 2 Supplement – Part 8)."""

import uuid
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.ai.client import get_ai_client
from src.ai.prompts import load_prompt
from src.api.deps import get_session
from src.engines.sentiment_analysis import (
    SentimentResult,
    keyword_sentiment,
    compute_aggregate_sentiment,
    analyze_earnings_call,
)
from src.models.entity import Entity
from src.models.news_article import ArticleEntityLink, NewsArticle
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

_TIMEFRAME_DAYS = {"ROLLING_7D": 7, "ROLLING_30D": 30, "ROLLING_90D": 90}


async def _get_entity(session: AsyncSession, entity_id: uuid.UUID) -> Entity:
    result = await session.execute(
        select(Entity).where(Entity.entity_id == entity_id)
    )
    entity = result.scalar_one_or_none()
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
    return entity


class SentimentClassification(BaseModel):
    """Structured output shape for the ``sentiment_score`` prompt.

    Replaces the old ``LABEL|SCORE|CONFIDENCE`` delimited-line parser
    (``_parse_llm_sentiment``, now removed) -- ``complete_structured``
    validates this shape via a tool-forced JSON call, so a malformed model
    response is a validation error the caller catches, not a silent parse
    failure to detect by hand.
    """

    label: str = Field(description="POSITIVE, NEGATIVE, or NEUTRAL")
    score: float = Field(ge=-1.0, le=1.0, description="-1.0 (bearish) to 1.0 (bullish)")
    confidence: float = Field(ge=0.0, le=1.0)


async def _score_entity_news(session: AsyncSession, entity_id: uuid.UUID) -> int:
    """Score any of the entity's linked news articles that don't yet have a
    SentimentScore row, using the keyword sentiment engine. Returns the
    number of newly-scored articles.

    This is the missing link that turns ingested news_articles (Finnhub)
    into sentiment_scores — the table the whole sentiment surface reads.
    """
    article_rows = (
        await session.execute(
            select(NewsArticle)
            .join(ArticleEntityLink, ArticleEntityLink.article_id == NewsArticle.id)
            .where(ArticleEntityLink.entity_id == entity_id)
            .order_by(NewsArticle.publish_date.desc())
            .limit(500)
        )
    ).scalars().all()
    if not article_rows:
        return 0

    already = (
        await session.execute(
            select(SentimentScore.source_reference).where(
                SentimentScore.entity_id == entity_id,
                SentimentScore.source_type == "NEWS",
            )
        )
    ).scalars().all()
    scored_refs = {r for r in already if r}

    created = 0
    for art in article_rows:
        ref = str(art.id)
        if ref in scored_refs:
            continue
        text = f"{art.title or ''}. {art.summary or ''}".strip()
        result = keyword_sentiment(text)
        session.add(SentimentScore(
            score_id=uuid.uuid4(),
            entity_id=entity_id,
            source_type="NEWS",
            source_reference=ref,
            source_date=(
                datetime.combine(art.publish_date, datetime.min.time()).replace(tzinfo=timezone.utc)
                if art.publish_date else None
            ),
            sentiment=result.sentiment,
            sentiment_score=result.score,
            confidence=result.confidence,
            ai_enabled=False,
        ))
        created += 1

    if created:
        await session.commit()
    return created


async def _rebuild_aggregate(
    session: AsyncSession, entity_id: uuid.UUID, timeframe: str
) -> SentimentAggregate | None:
    """Roll the entity's sentiment_scores in the timeframe window into a
    persisted SentimentAggregate via compute_aggregate_sentiment. Returns the
    upserted row, or None when there are no scores to aggregate."""
    days = _TIMEFRAME_DAYS.get(timeframe, 30)
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    score_rows = (
        await session.execute(
            select(SentimentScore)
            .where(
                SentimentScore.entity_id == entity_id,
                (SentimentScore.source_date.is_(None)) | (SentimentScore.source_date >= cutoff),
            )
        )
    ).scalars().all()
    if not score_rows:
        return None

    scores = [
        {"sentiment_score": float(s.sentiment_score), "sentiment": s.sentiment}
        for s in score_rows
    ]

    # Prior-period average for momentum.
    prior_row = (
        await session.execute(
            select(SentimentAggregate)
            .where(SentimentAggregate.entity_id == entity_id, SentimentAggregate.timeframe == timeframe)
            .order_by(SentimentAggregate.as_of_date.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    prior_avg = float(prior_row.avg_sentiment) if prior_row and prior_row.avg_sentiment is not None else None

    agg = compute_aggregate_sentiment(scores, prior_avg=prior_avg)

    today = date.today()
    existing_today = (
        await session.execute(
            select(SentimentAggregate).where(
                SentimentAggregate.entity_id == entity_id,
                SentimentAggregate.timeframe == timeframe,
                SentimentAggregate.as_of_date == today,
            )
        )
    ).scalar_one_or_none()

    target = existing_today or SentimentAggregate(
        id=uuid.uuid4(), entity_id=entity_id, timeframe=timeframe, as_of_date=today,
    )
    target.avg_sentiment = agg.avg_sentiment
    target.sentiment_momentum = agg.sentiment_momentum
    target.article_count = agg.article_count
    target.positive_pct = agg.positive_pct
    target.negative_pct = agg.negative_pct
    target.anomaly_flag = agg.anomaly_flag
    if existing_today is None:
        session.add(target)
    await session.commit()
    await session.refresh(target)
    return target


# NOTE: /score and /anomalies are static paths — define BEFORE /{entity_id}
@router.post(
    "/analytics/sentiment/score",
    response_model=SentimentScoreResponse,
)
async def score_text(
    body: ScoreTextRequest,
):
    """Score arbitrary text for sentiment (no DB needed).

    Uses the real LLM client for classification when configured; otherwise
    falls back to the keyword-based heuristic (also used as a safety net
    if the LLM response can't be parsed).
    """
    client = get_ai_client()
    result = keyword_sentiment(body.text)
    ai_enabled = False

    if client.enabled:
        prompt = load_prompt("sentiment_score")
        try:
            classification = await client.complete_structured(
                response_model=SentimentClassification,
                user=prompt.render(text=body.text),
                system=prompt.system,
                tier=prompt.tier,
                max_tokens=prompt.max_tokens,
                feature=prompt.feature,
            )
            label = classification.label.strip().upper()
            if label in ("POSITIVE", "NEGATIVE", "NEUTRAL"):
                result = SentimentResult(
                    sentiment=label,
                    score=round(classification.score, 4),
                    confidence=round(classification.confidence, 4),
                )
                ai_enabled = True
        except Exception:
            # API failure or an out-of-enum label -- keep the keyword
            # fallback already computed above, same safety-net contract
            # the old delimited-line parser provided.
            pass

    return SentimentScoreResponse(
        sentiment=result.sentiment,
        sentiment_score=result.score,
        confidence=result.confidence,
        ai_enabled=ai_enabled,
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


@router.post(
    "/analytics/sentiment/{entity_id}/refresh",
    response_model=SentimentAggregateResponse,
)
async def refresh_sentiment(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    timeframe: str = Query("ROLLING_30D"),
):
    """Score the entity's ingested news into sentiment_scores and rebuild the
    rolling SentimentAggregate.

    This is the producer the sentiment surface was missing: news_articles
    (Finnhub-ingested) are scored via the keyword engine into
    sentiment_scores, then compute_aggregate_sentiment rolls them into a
    persisted sentiment_aggregates row that every /sentiment read consumes.
    """
    await _get_entity(session, entity_id)
    await _score_entity_news(session, entity_id)
    agg = await _rebuild_aggregate(session, entity_id, timeframe)
    if agg is None:
        # No news/scores available to aggregate — honest empty result.
        return SentimentAggregateResponse(
            entity_id=entity_id,
            as_of_date=date.today(),
            timeframe=timeframe,
            avg_sentiment=None,
            article_count=0,
        )
    return SentimentAggregateResponse(
        entity_id=agg.entity_id,
        as_of_date=agg.as_of_date,
        timeframe=agg.timeframe,
        avg_sentiment=float(agg.avg_sentiment),
        sentiment_momentum=float(agg.sentiment_momentum) if agg.sentiment_momentum is not None else None,
        article_count=agg.article_count,
        positive_pct=float(agg.positive_pct) if agg.positive_pct is not None else 0.0,
        negative_pct=float(agg.negative_pct) if agg.negative_pct is not None else 0.0,
        anomaly_flag=agg.anomaly_flag,
    )


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

    # No aggregate exists — avg_sentiment stays None so this is
    # distinguishable from a real neutral (0.0) score.
    return SentimentAggregateResponse(
        entity_id=entity_id,
        as_of_date=date.today(),
        timeframe=timeframe,
        avg_sentiment=None,
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
