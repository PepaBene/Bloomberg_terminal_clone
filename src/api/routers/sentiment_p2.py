"""News Sentiment P2 API endpoints (Pillar 3 Phase 2)."""

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_session
from src.models.entity import Entity
from src.models.sentiment import SentimentAggregate, Watchlist
from src.models.news_article import NewsArticle, ArticleEntityLink
from src.schemas.finbert_sentiment_p2 import (
    BulkNewsRequest,
    PeerComparisonResponse,
    SentimentAnomalyResponse,
    SentimentScreenRequest,
    SentimentScreenResponse,
    SentimentSummaryResponse,
)

router = APIRouter(tags=["News Sentiment"])


async def _get_entity(session: AsyncSession, entity_id: uuid.UUID) -> Entity:
    result = await session.execute(
        select(Entity).where(Entity.entity_id == entity_id)
    )
    entity = result.scalar_one_or_none()
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
    return entity


# ── Static routes (MUST be before parametric) ────────────────────────


@router.post(
    "/news/sentiment/screen",
    response_model=SentimentScreenResponse,
)
async def screen_by_sentiment(
    body: SentimentScreenRequest,
    session: AsyncSession = Depends(get_session),
):
    """Screen entities by sentiment criteria."""
    stmt = select(SentimentAggregate).where(
        SentimentAggregate.timeframe == "30D"
    )

    if body.min_sentiment is not None:
        stmt = stmt.where(SentimentAggregate.avg_sentiment >= body.min_sentiment)
    if body.max_sentiment is not None:
        stmt = stmt.where(SentimentAggregate.avg_sentiment <= body.max_sentiment)
    if body.momentum_class is not None:
        stmt = stmt.where(SentimentAggregate.sentiment_momentum_class == body.momentum_class)
    if body.min_anomaly_score is not None:
        stmt = stmt.where(SentimentAggregate.combined_anomaly_score >= body.min_anomaly_score)

    stmt = stmt.order_by(SentimentAggregate.avg_sentiment.desc()).limit(body.limit)
    result = await session.execute(stmt)
    rows = result.scalars().all()

    # R-009: Fetch 7D and 90D sentiment for matched entities
    entity_ids = [r.entity_id for r in rows]
    sent_7d_map: dict[uuid.UUID, float] = {}
    sent_90d_map: dict[uuid.UUID, float] = {}
    if entity_ids:
        for tf, target_map in [("7D", sent_7d_map), ("90D", sent_90d_map)]:
            tf_result = await session.execute(
                select(SentimentAggregate)
                .where(
                    and_(
                        SentimentAggregate.entity_id.in_(entity_ids),
                        SentimentAggregate.timeframe == tf,
                    )
                )
                .order_by(SentimentAggregate.as_of_date.desc())
            )
            for agg in tf_result.scalars().all():
                if agg.entity_id not in target_map and agg.avg_sentiment is not None:
                    target_map[agg.entity_id] = float(agg.avg_sentiment)

    results = [
        SentimentSummaryResponse(
            entity_id=r.entity_id,
            sentiment_7d=sent_7d_map.get(r.entity_id),
            sentiment_30d=float(r.avg_sentiment) if r.avg_sentiment is not None else None,
            sentiment_90d=sent_90d_map.get(r.entity_id),
            momentum=float(r.sentiment_momentum) if r.sentiment_momentum is not None else None,
            momentum_class=r.sentiment_momentum_class,
            article_count=r.article_count,
        )
        for r in rows
    ]
    return SentimentScreenResponse(results=results, total_count=len(results))


@router.get(
    "/news/digest",
    response_model=list[dict],
)
async def get_daily_digest(
    session: AsyncSession = Depends(get_session),
    target_date: date | None = Query(None, alias="date", description="Date for digest (defaults to today)"),
):
    """Get daily news digest."""
    d = target_date or date.today()
    stmt = (
        select(NewsArticle)
        .where(NewsArticle.publish_date == d)
        .order_by(NewsArticle.sentiment_score.desc().nulls_last())
        .limit(50)
    )
    result = await session.execute(stmt)
    rows = result.scalars().all()

    return [
        {
            "article_id": str(r.id),
            "title": r.title,
            "source_name": r.source_name,
            "publish_date": r.publish_date.isoformat(),
            "sentiment_label": r.sentiment_label,
            "sentiment_score": float(r.sentiment_score) if r.sentiment_score is not None else None,
            "materiality": r.materiality,
            "topics": r.topics,
        }
        for r in rows
    ]


@router.get(
    "/news/digest/watchlist",
    response_model=list[dict],
)
async def get_watchlist_digest(
    session: AsyncSession = Depends(get_session),
    target_date: date | None = Query(None, alias="date", description="Date for digest (defaults to today)"),
    watchlist_entity_ids: list[str] | None = Query(None, alias="entity_ids", description="Entity IDs to filter by (from watchlist)"),
    user_id: str | None = Query(None, description="User ID to load watchlist entities from DB"),
):
    """Get watchlist-filtered daily news digest.

    Filter articles by watchlist entities. Provide either explicit
    ``entity_ids`` or a ``user_id`` whose Watchlist entries will be used.
    If neither is provided, returns an empty list.
    """
    # R-008: Resolve watchlist entity IDs
    entity_uuids: list[uuid.UUID] = []
    if watchlist_entity_ids:
        entity_uuids = [uuid.UUID(eid) for eid in watchlist_entity_ids]
    elif user_id:
        wl_result = await session.execute(
            select(Watchlist.entity_id).where(Watchlist.user_id == user_id)
        )
        entity_uuids = list(wl_result.scalars().all())

    if not entity_uuids:
        return []

    d = target_date or date.today()

    # Get article IDs linked to watchlist entities
    article_ids_stmt = (
        select(ArticleEntityLink.article_id)
        .where(ArticleEntityLink.entity_id.in_(entity_uuids))
    )

    stmt = (
        select(NewsArticle)
        .where(
            and_(
                NewsArticle.publish_date == d,
                NewsArticle.id.in_(article_ids_stmt),
            )
        )
        .order_by(NewsArticle.sentiment_score.desc().nulls_last())
        .limit(50)
    )
    result = await session.execute(stmt)
    rows = result.scalars().all()

    return [
        {
            "article_id": str(r.id),
            "title": r.title,
            "source_name": r.source_name,
            "publish_date": r.publish_date.isoformat(),
            "sentiment_label": r.sentiment_label,
            "sentiment_score": float(r.sentiment_score) if r.sentiment_score is not None else None,
            "materiality": r.materiality,
        }
        for r in rows
    ]


@router.post(
    "/news/bulk",
    response_model=list[dict],
)
async def bulk_news(
    body: BulkNewsRequest,
    session: AsyncSession = Depends(get_session),
):
    """Bulk fetch news articles by entity IDs or date range."""
    entity_ids = body.entity_ids
    from_date = body.from_date
    to_date = body.to_date
    limit = body.limit

    stmt = select(NewsArticle)

    if entity_ids:
        # Filter through article_entity_links
        article_ids_stmt = (
            select(ArticleEntityLink.article_id)
            .where(ArticleEntityLink.entity_id.in_([uuid.UUID(e) for e in entity_ids]))
        )
        stmt = stmt.where(NewsArticle.id.in_(article_ids_stmt))

    if from_date:
        stmt = stmt.where(NewsArticle.publish_date >= from_date)
    if to_date:
        stmt = stmt.where(NewsArticle.publish_date <= to_date)

    stmt = stmt.order_by(NewsArticle.publish_date.desc()).limit(limit)
    result = await session.execute(stmt)
    rows = result.scalars().all()

    return [
        {
            "article_id": str(r.id),
            "title": r.title,
            "source_name": r.source_name,
            "publish_date": r.publish_date.isoformat(),
            "sentiment_label": r.sentiment_label,
            "sentiment_score": float(r.sentiment_score) if r.sentiment_score is not None else None,
        }
        for r in rows
    ]


@router.post(
    "/news/bulk/sentiment",
    response_model=list[SentimentSummaryResponse],
)
async def bulk_sentiment(
    body: dict,
    session: AsyncSession = Depends(get_session),
):
    """Bulk sentiment scoring for multiple entities."""
    entity_ids = body.get("entity_ids", [])
    if not entity_ids:
        return []

    uuids = [uuid.UUID(e) for e in entity_ids]
    stmt = (
        select(SentimentAggregate)
        .where(
            and_(
                SentimentAggregate.entity_id.in_(uuids),
                SentimentAggregate.timeframe == "30D",
            )
        )
    )
    result = await session.execute(stmt)
    rows = result.scalars().all()

    # R-009: Fetch 7D and 90D sentiment for the requested entities
    sent_7d_map: dict[uuid.UUID, float] = {}
    sent_90d_map: dict[uuid.UUID, float] = {}
    for tf, target_map in [("7D", sent_7d_map), ("90D", sent_90d_map)]:
        tf_result = await session.execute(
            select(SentimentAggregate)
            .where(
                and_(
                    SentimentAggregate.entity_id.in_(uuids),
                    SentimentAggregate.timeframe == tf,
                )
            )
            .order_by(SentimentAggregate.as_of_date.desc())
        )
        for agg in tf_result.scalars().all():
            if agg.entity_id not in target_map and agg.avg_sentiment is not None:
                target_map[agg.entity_id] = float(agg.avg_sentiment)

    return [
        SentimentSummaryResponse(
            entity_id=r.entity_id,
            sentiment_7d=sent_7d_map.get(r.entity_id),
            sentiment_30d=float(r.avg_sentiment) if r.avg_sentiment is not None else None,
            sentiment_90d=sent_90d_map.get(r.entity_id),
            momentum=float(r.sentiment_momentum) if r.sentiment_momentum is not None else None,
            momentum_class=r.sentiment_momentum_class,
            article_count=r.article_count,
        )
        for r in rows
    ]


# ── Parametric routes ─────────────────────────────────────────────────


@router.get(
    "/news/{entity_id}/sentiment",
    response_model=SentimentSummaryResponse,
)
async def get_entity_sentiment(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get rolling sentiment summary for an entity."""
    await _get_entity(session, entity_id)

    stmt = (
        select(SentimentAggregate)
        .where(SentimentAggregate.entity_id == entity_id)
        .order_by(SentimentAggregate.as_of_date.desc())
    )
    result = await session.execute(stmt)
    rows = result.scalars().all()

    # Build summary from different timeframes
    sent_7d = sent_30d = sent_90d = None
    momentum = None
    momentum_class = None
    article_count = 0

    for r in rows:
        if r.timeframe == "7D" and sent_7d is None:
            sent_7d = float(r.avg_sentiment) if r.avg_sentiment is not None else None
        elif r.timeframe == "30D" and sent_30d is None:
            sent_30d = float(r.avg_sentiment) if r.avg_sentiment is not None else None
            momentum = float(r.sentiment_momentum) if r.sentiment_momentum is not None else None
            momentum_class = r.sentiment_momentum_class
            article_count = r.article_count
        elif r.timeframe == "90D" and sent_90d is None:
            sent_90d = float(r.avg_sentiment) if r.avg_sentiment is not None else None

    return SentimentSummaryResponse(
        entity_id=entity_id,
        sentiment_7d=sent_7d,
        sentiment_30d=sent_30d,
        sentiment_90d=sent_90d,
        momentum=momentum,
        momentum_class=momentum_class,
        article_count=article_count,
    )


@router.get(
    "/news/{entity_id}/sentiment/history",
    response_model=list[dict],
)
async def get_sentiment_time_series(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    timeframe: str = Query("30D", description="Timeframe: 7D, 30D, 90D"),
    limit: int = Query(90, ge=1, le=365),
):
    """Get sentiment time series for an entity."""
    await _get_entity(session, entity_id)

    stmt = (
        select(SentimentAggregate)
        .where(
            and_(
                SentimentAggregate.entity_id == entity_id,
                SentimentAggregate.timeframe == timeframe,
            )
        )
        .order_by(SentimentAggregate.as_of_date.desc())
        .limit(limit)
    )
    result = await session.execute(stmt)
    rows = result.scalars().all()

    return [
        {
            "as_of_date": r.as_of_date.isoformat(),
            "avg_sentiment": float(r.avg_sentiment) if r.avg_sentiment is not None else None,
            "momentum": float(r.sentiment_momentum) if r.sentiment_momentum is not None else None,
            "article_count": r.article_count,
            "anomaly_flag": r.anomaly_flag,
        }
        for r in rows
    ]


@router.get(
    "/news/{entity_id}/sentiment/vs-peers",
    response_model=PeerComparisonResponse,
)
async def get_sentiment_vs_peers(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get entity sentiment relative to peer group (Z-score)."""
    await _get_entity(session, entity_id)

    stmt = (
        select(SentimentAggregate)
        .where(
            and_(
                SentimentAggregate.entity_id == entity_id,
                SentimentAggregate.timeframe == "30D",
            )
        )
        .order_by(SentimentAggregate.as_of_date.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    r = result.scalar_one_or_none()

    if not r:
        return PeerComparisonResponse(entity_id=entity_id)

    # R-010: Compute peer_median from peer group sentiment data.
    # peer_rank_pct is a percentile (0-1), NOT the peer median sentiment value.
    # Query the median avg_sentiment across all entities for the same timeframe
    # and as_of_date to derive the actual peer median.
    peer_median_val = None
    median_result = await session.execute(
        select(func.percentile_cont(0.5).within_group(SentimentAggregate.avg_sentiment))
        .where(
            and_(
                SentimentAggregate.timeframe == "30D",
                SentimentAggregate.as_of_date == r.as_of_date,
            )
        )
    )
    raw_median = median_result.scalar_one_or_none()
    if raw_median is not None:
        peer_median_val = float(raw_median)

    return PeerComparisonResponse(
        entity_id=entity_id,
        sentiment_30d=float(r.avg_sentiment) if r.avg_sentiment is not None else None,
        peer_median=peer_median_val,
        z_score=float(r.peer_z_score) if r.peer_z_score is not None else None,
        is_significant=abs(float(r.peer_z_score)) > 1.96 if r.peer_z_score is not None else False,
    )


@router.get(
    "/news/{entity_id}/sentiment/anomalies",
    response_model=SentimentAnomalyResponse,
)
async def get_sentiment_anomalies(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get sentiment anomaly flags for an entity."""
    await _get_entity(session, entity_id)

    stmt = (
        select(SentimentAggregate)
        .where(
            and_(
                SentimentAggregate.entity_id == entity_id,
                SentimentAggregate.timeframe == "30D",
            )
        )
        .order_by(SentimentAggregate.as_of_date.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    r = result.scalar_one_or_none()

    if not r:
        return SentimentAnomalyResponse(
            entity_id=entity_id,
            volume_anomaly=False,
            sentiment_shift_anomaly=False,
            price_divergence_anomaly=False,
        )

    anomalies = []
    if r.volume_anomaly:
        anomalies.append({"type": "VOLUME_SPIKE", "description": "Unusual article volume detected"})
    if r.sentiment_shift_anomaly:
        anomalies.append({"type": "SENTIMENT_SHIFT", "description": "Significant sentiment shift detected"})
    if r.price_divergence_anomaly:
        anomalies.append({"type": "PRICE_DIVERGENCE", "description": "Sentiment-price divergence detected"})

    return SentimentAnomalyResponse(
        entity_id=entity_id,
        combined_score=float(r.combined_anomaly_score) if r.combined_anomaly_score is not None else None,
        volume_anomaly=r.volume_anomaly,
        sentiment_shift_anomaly=r.sentiment_shift_anomaly,
        price_divergence_anomaly=r.price_divergence_anomaly,
        anomalies=anomalies,
    )
