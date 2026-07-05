"""News Intelligence API endpoints (Pillar 3 Phase 1)."""

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, and_, desc, literal_column
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_session
from src.models.entity import Entity
from src.models.news_article import NewsArticle, ArticleEntityLink
from src.schemas.news_article import (
    ArticleEntityLinkResponse,
    NewsArticleResponse,
    NewsSearchRequest,
    NewsSearchResponse,
    NewsStatsResponse,
)

router = APIRouter(tags=["News Intelligence"])


async def _get_entity(session: AsyncSession, entity_id: uuid.UUID) -> Entity:
    result = await session.execute(
        select(Entity).where(Entity.entity_id == entity_id)
    )
    entity = result.scalar_one_or_none()
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
    return entity


async def _enrich_articles(
    session: AsyncSession, articles: list[NewsArticle],
) -> list[NewsArticleResponse]:
    """Convert ORM article rows to response models with entity links."""
    if not articles:
        return []

    article_ids = [a.id for a in articles]
    link_result = await session.execute(
        select(ArticleEntityLink).where(ArticleEntityLink.article_id.in_(article_ids))
    )
    link_rows = link_result.scalars().all()

    # Group links by article_id
    links_by_article: dict[uuid.UUID, list[ArticleEntityLink]] = {}
    for link in link_rows:
        links_by_article.setdefault(link.article_id, []).append(link)

    responses = []
    for article in articles:
        entity_links = [
            ArticleEntityLinkResponse(
                entity_id=link.entity_id,
                relevance_score=float(link.relevance_score) if link.relevance_score is not None else None,
                confidence=float(link.confidence) if link.confidence is not None else None,
                is_primary=link.is_primary,
                mention_text=link.mention_text,
            )
            for link in links_by_article.get(article.id, [])
        ]

        responses.append(
            NewsArticleResponse(
                id=article.id,
                title=article.title,
                summary=article.summary,
                source_name=article.source_name,
                publish_date=article.publish_date,
                ingest_date=article.ingest_date,
                news_type=article.news_type,
                topics=article.topics,
                materiality=article.materiality,
                sentiment_score=float(article.sentiment_score) if article.sentiment_score is not None else None,
                sentiment_label=article.sentiment_label,
                source_url=article.source_url,
                entities=entity_links,
            )
        )

    return responses


# ── Static routes (defined BEFORE parametric /{entity_id}) ─────────────


@router.get(
    "/news/latest",
    response_model=list[NewsArticleResponse],
)
async def get_latest_news(
    session: AsyncSession = Depends(get_session),
    limit: int = Query(20, ge=1, le=100),
):
    """Get the latest news articles across all entities."""
    result = await session.execute(
        select(NewsArticle)
        .order_by(NewsArticle.publish_date.desc())
        .limit(limit)
    )
    rows = result.scalars().all()
    return await _enrich_articles(session, list(rows))


@router.get(
    "/news/market-moving",
    response_model=list[NewsArticleResponse],
)
async def get_market_moving_news(
    session: AsyncSession = Depends(get_session),
):
    """Get high-materiality news articles (market-moving)."""
    result = await session.execute(
        select(NewsArticle)
        .where(NewsArticle.materiality == "HIGH")
        .order_by(NewsArticle.publish_date.desc())
        .limit(50)
    )
    rows = result.scalars().all()
    return await _enrich_articles(session, list(rows))


@router.get(
    "/news/most-mentioned",
    response_model=list[dict],
)
async def get_most_mentioned_entities(
    session: AsyncSession = Depends(get_session),
):
    """Get entities with the most news mentions in the last 30 days."""
    from datetime import timedelta

    cutoff = date.today() - timedelta(days=30)

    result = await session.execute(
        select(
            ArticleEntityLink.entity_id,
            func.count(ArticleEntityLink.id).label("mention_count"),
        )
        .join(NewsArticle, NewsArticle.id == ArticleEntityLink.article_id)
        .where(NewsArticle.publish_date >= cutoff)
        .group_by(ArticleEntityLink.entity_id)
        .order_by(desc(literal_column("mention_count")))
        .limit(20)
    )
    rows = result.all()

    return [
        {"entity_id": str(row.entity_id), "mention_count": row.mention_count}
        for row in rows
    ]


@router.get(
    "/news/stats",
    response_model=NewsStatsResponse,
)
async def get_news_stats(
    session: AsyncSession = Depends(get_session),
):
    """Get aggregate news statistics."""
    today = date.today()

    # Combine total + today counts into a single query
    counts_result = await session.execute(
        select(
            func.count(NewsArticle.id).label("total"),
            func.count(NewsArticle.id).filter(
                NewsArticle.publish_date == today
            ).label("today"),
        )
    )
    counts_row = counts_result.one()
    total_articles = counts_row.total or 0
    articles_today = counts_row.today or 0

    # Combine source, type, and materiality breakdowns into parallel queries
    source_result, type_result, mat_result = await session.execute(
        select(NewsArticle.source_name, func.count(NewsArticle.id))
        .group_by(NewsArticle.source_name)
        .order_by(desc(func.count(NewsArticle.id)))
        .limit(20)
    ), await session.execute(
        select(NewsArticle.news_type, func.count(NewsArticle.id))
        .where(NewsArticle.news_type.isnot(None))
        .group_by(NewsArticle.news_type)
    ), await session.execute(
        select(NewsArticle.materiality, func.count(NewsArticle.id))
        .where(NewsArticle.materiality.isnot(None))
        .group_by(NewsArticle.materiality)
    )
    by_source = {row[0]: row[1] for row in source_result.all()}
    by_type = {row[0]: row[1] for row in type_result.all()}
    by_materiality = {row[0]: row[1] for row in mat_result.all()}

    return NewsStatsResponse(
        total_articles=total_articles,
        articles_today=articles_today,
        by_source=by_source,
        by_type=by_type,
        by_materiality=by_materiality,
    )


@router.get(
    "/news/stats/coverage",
    response_model=dict,
)
async def get_news_coverage_stats(
    session: AsyncSession = Depends(get_session),
):
    """Get entity coverage statistics — how many entities have news articles."""
    total_entities_result = await session.execute(
        select(func.count(func.distinct(ArticleEntityLink.entity_id)))
    )
    entities_with_news = total_entities_result.scalar_one() or 0

    total_links_result = await session.execute(
        select(func.count(ArticleEntityLink.id))
    )
    total_links = total_links_result.scalar_one() or 0

    return {
        "entities_with_news": entities_with_news,
        "total_entity_article_links": total_links,
    }


@router.get(
    "/news/sector/{gics_sector}",
    response_model=list[NewsArticleResponse],
)
async def get_news_by_sector(
    gics_sector: str,
    session: AsyncSession = Depends(get_session),
):
    """Get recent news for all entities in a GICS sector."""
    # Find entities in this sector
    entity_result = await session.execute(
        select(Entity.entity_id).where(Entity.gics_sector == gics_sector)
    )
    entity_ids = [row[0] for row in entity_result.all()]

    if not entity_ids:
        raise HTTPException(status_code=404, detail="No entities found for this GICS sector")

    # Find articles linked to those entities
    article_id_result = await session.execute(
        select(func.distinct(ArticleEntityLink.article_id))
        .where(ArticleEntityLink.entity_id.in_(entity_ids))
    )
    article_ids = [row[0] for row in article_id_result.all()]

    if not article_ids:
        return []

    result = await session.execute(
        select(NewsArticle)
        .where(NewsArticle.id.in_(article_ids))
        .order_by(NewsArticle.publish_date.desc())
        .limit(50)
    )
    rows = result.scalars().all()
    return await _enrich_articles(session, list(rows))


@router.post(
    "/news/search",
    response_model=NewsSearchResponse,
)
async def search_news(
    body: NewsSearchRequest,
    session: AsyncSession = Depends(get_session),
):
    """Search news articles with filters."""
    stmt = select(NewsArticle)

    # Text search on title / summary
    if body.query:
        search_pattern = f"%{body.query}%"
        stmt = stmt.where(
            (NewsArticle.title.ilike(search_pattern))
            | (NewsArticle.summary.ilike(search_pattern))
        )

    if body.date_from:
        stmt = stmt.where(NewsArticle.publish_date >= body.date_from)
    if body.date_to:
        stmt = stmt.where(NewsArticle.publish_date <= body.date_to)
    if body.news_types:
        stmt = stmt.where(NewsArticle.news_type.in_(body.news_types))
    if body.materiality_min:
        materiality_order = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}
        min_level = materiality_order.get(body.materiality_min, 0)
        allowed = [k for k, v in materiality_order.items() if v >= min_level]
        stmt = stmt.where(NewsArticle.materiality.in_(allowed))

    # If filtering by entity, join through ArticleEntityLink
    if body.entities:
        stmt = stmt.join(
            ArticleEntityLink, ArticleEntityLink.article_id == NewsArticle.id
        ).where(ArticleEntityLink.entity_id.in_(body.entities))

    # Count total
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_result = await session.execute(count_stmt)
    total_count = total_result.scalar_one() or 0

    # Paginate
    stmt = stmt.order_by(NewsArticle.publish_date.desc())
    stmt = stmt.offset(body.offset).limit(body.limit)

    result = await session.execute(stmt)
    rows = result.scalars().all()

    articles = await _enrich_articles(session, list(rows))
    return NewsSearchResponse(articles=articles, total_count=total_count)


# ── Parametric routes (AFTER static routes) ────────────────────────────


@router.get(
    "/news/{entity_id}",
    response_model=list[NewsArticleResponse],
)
async def get_entity_news(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    type: str | None = Query(None, description="News type filter"),
    topic: str | None = Query(None, description="Topic filter"),
    materiality: str | None = Query(None, description="Materiality filter (HIGH, MEDIUM, LOW)"),
    from_date: date | None = Query(None, description="Start date"),
    to_date: date | None = Query(None, description="End date"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """Get news articles for a specific entity."""
    await _get_entity(session, entity_id)

    # Find article IDs linked to this entity
    link_stmt = select(ArticleEntityLink.article_id).where(
        ArticleEntityLink.entity_id == entity_id
    )
    link_result = await session.execute(link_stmt)
    article_ids = [row[0] for row in link_result.all()]

    if not article_ids:
        return []

    stmt = select(NewsArticle).where(NewsArticle.id.in_(article_ids))

    if type:
        stmt = stmt.where(NewsArticle.news_type == type)
    if materiality:
        stmt = stmt.where(NewsArticle.materiality == materiality)
    if from_date:
        stmt = stmt.where(NewsArticle.publish_date >= from_date)
    if to_date:
        stmt = stmt.where(NewsArticle.publish_date <= to_date)

    stmt = stmt.order_by(NewsArticle.publish_date.desc()).offset(offset).limit(limit)
    result = await session.execute(stmt)
    rows = result.scalars().all()

    return await _enrich_articles(session, list(rows))


@router.get(
    "/news/{entity_id}/timeline",
    response_model=list[dict],
)
async def get_entity_news_timeline(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get a news frequency timeline for an entity (articles per day)."""
    await _get_entity(session, entity_id)

    result = await session.execute(
        select(
            NewsArticle.publish_date,
            func.count(NewsArticle.id).label("article_count"),
        )
        .join(ArticleEntityLink, ArticleEntityLink.article_id == NewsArticle.id)
        .where(ArticleEntityLink.entity_id == entity_id)
        .group_by(NewsArticle.publish_date)
        .order_by(NewsArticle.publish_date.desc())
        .limit(90)
    )
    rows = result.all()

    return [
        {"date": str(row.publish_date), "article_count": row.article_count}
        for row in rows
    ]
