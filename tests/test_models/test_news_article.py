"""Tests for Pillar 3 Phase 1: News Article models."""

import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from src.models.entity import Entity
from src.models.news_article import ArticleEntityLink, NewsArticle, NewsSource


# ── Helpers ──────────────────────────────────────────────────────────


async def _seed_entity(session, entity_id: uuid.UUID | None = None) -> Entity:
    eid = entity_id or uuid.uuid4()
    entity = Entity(
        entity_id=eid,
        entity_type="PUBLIC_COMPANY",
        legal_name="News Test Corp",
        status="ACTIVE",
        source="SEC_EDGAR",
    )
    session.add(entity)
    await session.flush()
    return entity


async def _seed_article(
    session,
    source_url: str = "https://news.example.com/article-1",
    article_id: uuid.UUID | None = None,
    **kwargs,
) -> NewsArticle:
    aid = article_id or uuid.uuid4()
    defaults = dict(
        id=aid,
        source_url=source_url,
        title="Test Article Title",
        summary="Test article summary.",
        source_name="Reuters",
        publish_date=date(2025, 10, 1),
        ingest_date=date(2025, 10, 1),
    )
    defaults.update(kwargs)
    article = NewsArticle(**defaults)
    session.add(article)
    await session.flush()
    return article


# ── Tests ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_news_article(session):
    """Create a news article with all fields including Decimal sentiment_score."""
    aid = uuid.uuid4()
    article = NewsArticle(
        id=aid,
        source_url="https://reuters.com/news/article-full",
        title="Major Tech Company Reports Strong Q3 Earnings",
        summary="Revenue and EPS beat consensus estimates.",
        body_text="Full article body text goes here...",
        source_name="Reuters",
        publish_date=date(2025, 10, 15),
        ingest_date=date(2025, 10, 15),
        news_type="EARNINGS",
        topics=["earnings", "technology", "Q3_2025"],
        materiality="HIGH",
        sentiment_score=Decimal("0.75"),
        sentiment_confidence=Decimal("0.92"),
        sentiment_label="POSITIVE",
        content_hash="a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
        is_propagated=False,
        propagation_source=None,
    )
    session.add(article)
    await session.flush()

    result = await session.execute(
        select(NewsArticle).where(NewsArticle.id == aid)
    )
    fetched = result.scalar_one()
    assert fetched.title == "Major Tech Company Reports Strong Q3 Earnings"
    assert fetched.source_name == "Reuters"
    assert fetched.publish_date == date(2025, 10, 15)
    assert fetched.news_type == "EARNINGS"
    assert fetched.materiality == "HIGH"
    assert fetched.sentiment_score == Decimal("0.75")
    assert fetched.sentiment_confidence == Decimal("0.92")
    assert fetched.sentiment_label == "POSITIVE"
    assert fetched.is_propagated is False


@pytest.mark.asyncio
async def test_news_article_unique_source_url(session):
    """Duplicate source_url should raise IntegrityError."""
    url = "https://reuters.com/news/unique-test-article"
    await _seed_article(session, source_url=url)

    session.add(NewsArticle(
        source_url=url,
        title="Duplicate Article",
        source_name="Reuters",
        publish_date=date(2025, 10, 16),
        ingest_date=date(2025, 10, 16),
    ))
    with pytest.raises(IntegrityError):
        await session.flush()
    await session.rollback()


@pytest.mark.asyncio
async def test_create_article_entity_link(session):
    """Create an article-entity link with relevance_score, confidence, is_primary."""
    entity = await _seed_entity(session)
    article = await _seed_article(session, source_url="https://news.example.com/link-test")
    lid = uuid.uuid4()

    link = ArticleEntityLink(
        id=lid,
        article_id=article.id,
        entity_id=entity.entity_id,
        relevance_score=Decimal("0.95"),
        confidence=Decimal("0.88"),
        is_primary=True,
        mention_text="News Test Corp",
        mention_count=5,
    )
    session.add(link)
    await session.flush()

    result = await session.execute(
        select(ArticleEntityLink).where(ArticleEntityLink.id == lid)
    )
    fetched = result.scalar_one()
    assert fetched.article_id == article.id
    assert fetched.entity_id == entity.entity_id
    assert fetched.relevance_score == Decimal("0.95")
    assert fetched.confidence == Decimal("0.88")
    assert fetched.is_primary is True
    assert fetched.mention_text == "News Test Corp"
    assert fetched.mention_count == 5


@pytest.mark.asyncio
async def test_article_entity_link_unique(session):
    """article_id + entity_id should be unique."""
    entity = await _seed_entity(session)
    article = await _seed_article(session, source_url="https://news.example.com/link-unique")

    session.add(ArticleEntityLink(
        article_id=article.id,
        entity_id=entity.entity_id,
        is_primary=True,
    ))
    await session.flush()

    session.add(ArticleEntityLink(
        article_id=article.id,
        entity_id=entity.entity_id,
        is_primary=False,
    ))
    with pytest.raises(IntegrityError):
        await session.flush()
    await session.rollback()


@pytest.mark.asyncio
async def test_news_article_topics_jsonb(session):
    """Round-trip JSONB topics list."""
    aid = uuid.uuid4()
    topics = ["M&A", "antitrust", "technology", "regulation", "cross_border"]
    session.add(NewsArticle(
        id=aid,
        source_url="https://news.example.com/topics-jsonb-test",
        title="Tech Merger Faces Regulatory Scrutiny",
        summary="Test article summary.",
        source_name="Bloomberg",
        publish_date=date(2025, 11, 1),
        ingest_date=date(2025, 11, 1),
        topics=topics,
    ))
    await session.flush()

    result = await session.execute(
        select(NewsArticle).where(NewsArticle.id == aid)
    )
    fetched = result.scalar_one()
    assert fetched.topics == topics
    assert len(fetched.topics) == 5
    assert "M&A" in fetched.topics
    assert "regulation" in fetched.topics


@pytest.mark.asyncio
async def test_query_news_by_ingest_date(session):
    """Point-in-time retrieval: filter by ingest_date <= X."""
    for day in (1, 5, 10, 15, 20):
        session.add(NewsArticle(
            source_url=f"https://news.example.com/ingest-date-test-{day}",
            title=f"Article from day {day}",
            summary="Test article summary.",
            source_name="Reuters",
            publish_date=date(2025, 12, day),
            ingest_date=date(2025, 12, day),
        ))
    await session.flush()

    # Query articles ingested on or before Dec 12
    result = await session.execute(
        select(NewsArticle)
        .where(NewsArticle.source_url.like("%ingest-date-test-%"))
        .where(NewsArticle.ingest_date <= date(2025, 12, 12))
    )
    articles = result.scalars().all()
    assert len(articles) == 3
    days = sorted(a.ingest_date.day for a in articles)
    assert days == [1, 5, 10]


# ── Layer 2 §4.2: news_sources + credibility columns ───────────────────


@pytest.mark.asyncio
async def test_create_news_source(session):
    session.add(NewsSource(
        source_name="Reuters",
        domain="reuters.com",
        tier="WIRE",
        reliability_weight=Decimal("1.00"),
        region="GLOBAL",
        is_paywalled=False,
    ))
    await session.flush()

    fetched = await session.get(NewsSource, "Reuters")
    assert fetched.domain == "reuters.com"
    assert fetched.tier == "WIRE"
    assert fetched.reliability_weight == Decimal("1.00")
    assert fetched.is_paywalled is False


@pytest.mark.asyncio
async def test_news_source_domain_unique(session):
    session.add(NewsSource(source_name="Reuters", domain="reuters.com", tier="WIRE", reliability_weight=Decimal("1.00")))
    await session.flush()

    session.add(NewsSource(source_name="Reuters Impostor", domain="reuters.com", tier="BLOG", reliability_weight=Decimal("0.35")))
    with pytest.raises(IntegrityError):
        await session.flush()
    await session.rollback()


@pytest.mark.asyncio
async def test_news_article_credibility_columns_default(session):
    """New rows default to a singleton cluster shape without explicit values."""
    article = await _seed_article(session, source_url="https://news.example.com/credibility-defaults")
    assert article.is_non_consensus is False
    assert article.corroboration_count == 1
    assert article.cluster_id is None
    assert article.source_trust is None
    assert article.credibility_score is None


@pytest.mark.asyncio
async def test_news_article_cluster_self_reference(session):
    """A representative article's cluster_id points at itself; a
    corroborating article's cluster_id points at the representative."""
    rep = await _seed_article(
        session, source_url="https://reuters.com/story-a", corroboration_count=2,
    )
    rep.cluster_id = rep.id
    await session.flush()

    corroborator = await _seed_article(
        session,
        source_url="https://apnews.com/story-a-corroborating",
        cluster_id=rep.id,
        source_trust=Decimal("1.00"),
        credibility_score=Decimal("1.000"),
    )
    await session.flush()

    assert rep.cluster_id == rep.id
    assert corroborator.cluster_id == rep.id
