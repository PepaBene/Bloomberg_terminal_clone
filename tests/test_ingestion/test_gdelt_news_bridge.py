"""Tests for the GDELT-articles-as-news bridge (AI_THREE_LAYER_REBUILD_PLAN.md
§4.1: "GDELT articles into news_articles (today it only writes
geopolitical_events)").

See test_sec_filing_news_bridge.py's module docstring for why every
assertion here is scoped to a specific, uuid-unique source_url rather than
global table counts -- the same session-scoped-engine test-isolation
caveat applies (bridge_geopolitical_events commits).
"""

import uuid
from datetime import date

import pytest
from sqlalchemy import select

from src.ingestion.gdelt_news_bridge import bridge_geopolitical_events
from src.models.country_risk import GeopoliticalEvent
from src.models.news_article import NewsArticle


_UNSET = object()


def _unique_url() -> str:
    return f"https://example-news.test/gdelt-{uuid.uuid4().hex}"


async def _seed_event(session, *, url=_UNSET, **kwargs) -> GeopoliticalEvent:
    """``url`` unset -> a fresh unique URL (the common case). Pass
    ``url=None`` explicitly to test the no-source_url path."""
    defaults = dict(
        id=uuid.uuid4(),
        event_type="SANCTIONS",
        title="Country X imposes new sanctions on Country Y",
        description="Source: example-news.test — full coverage of the new sanctions regime.",
        countries_involved={"source_country": "US"},
        severity="MEDIUM",
        status="REPORTED",
        start_date=date(2026, 1, 10),
        source_url=_unique_url() if url is _UNSET else url,
    )
    defaults.update(kwargs)
    event = GeopoliticalEvent(**defaults)
    session.add(event)
    await session.flush()
    return event


@pytest.mark.asyncio
async def test_bridge_creates_news_article_from_event(session):
    event = await _seed_event(session)

    stats = await bridge_geopolitical_events(session)
    assert stats["created"] >= 1

    article = (
        await session.execute(select(NewsArticle).where(NewsArticle.source_url == event.source_url))
    ).scalars().first()
    assert article is not None
    assert article.title == event.title
    assert article.source_name == "GDELT"
    assert article.materiality == "MEDIUM"
    assert article.publish_date == date(2026, 1, 10)


@pytest.mark.asyncio
async def test_bridge_is_idempotent(session):
    event = await _seed_event(session)

    await bridge_geopolitical_events(session)
    await bridge_geopolitical_events(session)

    articles = (
        await session.execute(select(NewsArticle).where(NewsArticle.source_url == event.source_url))
    ).scalars().all()
    assert len(articles) == 1


@pytest.mark.asyncio
async def test_bridge_skips_events_without_source_url(session):
    unique_title = f"Untitled event {uuid.uuid4().hex}"
    await _seed_event(session, url=None, title=unique_title)

    await bridge_geopolitical_events(session)

    article = (
        await session.execute(select(NewsArticle).where(NewsArticle.title == unique_title))
    ).scalars().first()
    assert article is None


@pytest.mark.asyncio
async def test_bridge_uses_severity_as_materiality(session):
    event = await _seed_event(session, severity="HIGH")

    await bridge_geopolitical_events(session)

    article = (
        await session.execute(select(NewsArticle).where(NewsArticle.source_url == event.source_url))
    ).scalars().first()
    assert article.materiality == "HIGH"


@pytest.mark.asyncio
async def test_bridge_falls_back_to_default_materiality_when_no_severity(session):
    event = await _seed_event(session, severity=None)

    await bridge_geopolitical_events(session)

    article = (
        await session.execute(select(NewsArticle).where(NewsArticle.source_url == event.source_url))
    ).scalars().first()
    assert article.materiality == "MEDIUM"


@pytest.mark.asyncio
async def test_bridge_enriches_the_created_article(session):
    event = await _seed_event(session)

    await bridge_geopolitical_events(session)

    article = (
        await session.execute(select(NewsArticle).where(NewsArticle.source_url == event.source_url))
    ).scalars().first()
    assert article.credibility_score is not None
    assert article.sentiment_label is not None
    # No natural primary entity for a macro event -> no propagation attempted.
    assert article.is_propagated is False


@pytest.mark.asyncio
async def test_bridge_falls_back_to_title_when_no_description(session):
    event = await _seed_event(session, description=None)

    await bridge_geopolitical_events(session)

    article = (
        await session.execute(select(NewsArticle).where(NewsArticle.source_url == event.source_url))
    ).scalars().first()
    assert article.summary == event.title


@pytest.mark.asyncio
async def test_geopolitical_event_source_url_unique(session):
    from sqlalchemy.exc import IntegrityError

    url = _unique_url()
    await _seed_event(session, url=url)

    session.add(GeopoliticalEvent(
        id=uuid.uuid4(), event_type="COUP", title="Different event, same url by accident",
        severity="HIGH", status="REPORTED", start_date=date(2026, 1, 11), source_url=url,
    ))
    with pytest.raises(IntegrityError):
        await session.flush()
    await session.rollback()
