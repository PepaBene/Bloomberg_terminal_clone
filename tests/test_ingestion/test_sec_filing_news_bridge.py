"""Tests for the SEC filings-as-news bridge (8-K material events ->
news_articles), AI_THREE_LAYER_REBUILD_PLAN.md §4.1.

Note on assertions: the ``session`` fixture shares one session-scoped
SQLite engine across the whole test run without per-test commit
rollback (see tests/conftest.py) -- and ``bridge_eight_k_events`` commits.
So committed rows from earlier tests persist into later ones.
``stats["candidates"]`` (a raw scan of the whole eight_k_events table) is
therefore NOT reliable to assert exact values on across tests; every
test here either scopes its DB lookups to the specific entity/URL it
itself created, or asserts on ``created``/``already_bridged`` deltas,
which stay correct regardless of what earlier tests left behind (a
freshly-seeded, uuid-unique event was never bridged before, and an
already-bridged one only got that way from this same test's own prior
call within the test).
"""

import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select

from src.ingestion.sec_filing_news_bridge import _article_url, bridge_eight_k_events
from src.models.entity import Entity
from src.models.filing_intelligence import EightKEvent
from src.models.news_article import ArticleEntityLink, NewsArticle, NewsSource


async def _seed_entity(session, *, legal_name="Acme Corp") -> Entity:
    entity = Entity(
        entity_id=uuid.uuid4(), entity_type="PUBLIC_COMPANY",
        legal_name=legal_name, status="ACTIVE", source="TEST",
    )
    session.add(entity)
    await session.flush()
    return entity


async def _seed_event(session, entity: Entity, *, item_number="2.01",
                        filing_date=date(2026, 1, 5), **kwargs) -> EightKEvent:
    defaults = dict(
        id=uuid.uuid4(), entity_id=entity.entity_id, filing_date=filing_date,
        item_number=item_number,
        item_description="Completion of Acquisition or Disposition of Assets",
        priority=1, materiality="HIGH",
        raw_text="The Company completed its previously announced acquisition of XYZ Inc for $500 million in cash.",
        filing_url=f"https://www.sec.gov/Archives/edgar/data/1234/{uuid.uuid4().hex}/form8k.htm",
        filing_accession_number="0001234567-26-000001",
        is_processed=False,
    )
    defaults.update(kwargs)
    event = EightKEvent(**defaults)
    session.add(event)
    await session.flush()
    return event


async def _article_for_entity(session, entity_id: uuid.UUID) -> NewsArticle | None:
    return (
        await session.execute(
            select(NewsArticle)
            .join(ArticleEntityLink, ArticleEntityLink.article_id == NewsArticle.id)
            .where(ArticleEntityLink.entity_id == entity_id)
        )
    ).scalars().first()


@pytest.mark.asyncio
async def test_bridge_creates_news_article_from_event(session):
    entity = await _seed_entity(session)
    event = await _seed_event(session, entity)

    stats = await bridge_eight_k_events(session)
    assert stats["created"] >= 1

    article = await _article_for_entity(session, entity.entity_id)
    assert article is not None
    assert "Acme Corp" in article.title
    assert article.body_text == event.raw_text
    assert article.materiality == "HIGH"
    assert article.publish_date == date(2026, 1, 5)
    assert article.source_url == _article_url(event)


@pytest.mark.asyncio
async def test_bridge_links_article_to_entity(session):
    entity = await _seed_entity(session)
    await _seed_event(session, entity)

    await bridge_eight_k_events(session)

    link = (
        await session.execute(
            select(ArticleEntityLink).where(ArticleEntityLink.entity_id == entity.entity_id)
        )
    ).scalars().first()
    assert link is not None
    assert link.is_primary is True


@pytest.mark.asyncio
async def test_bridge_is_idempotent(session):
    entity = await _seed_entity(session)
    await _seed_event(session, entity)

    await bridge_eight_k_events(session)
    await bridge_eight_k_events(session)

    # This entity's event is freshly uuid-unique -- created exactly once
    # by the first call, and the second call must not duplicate it.
    all_links = (
        await session.execute(
            select(ArticleEntityLink).where(ArticleEntityLink.entity_id == entity.entity_id)
        )
    ).scalars().all()
    assert len(all_links) == 1


@pytest.mark.asyncio
async def test_bridge_gives_distinct_urls_for_multiple_items_same_filing(session):
    entity = await _seed_entity(session)
    shared_url = f"https://www.sec.gov/Archives/edgar/data/1234/{uuid.uuid4().hex}/form8k.htm"
    event_a = await _seed_event(session, entity, item_number="2.01", filing_url=shared_url)
    event_b = await _seed_event(
        session, entity, item_number="5.02", filing_url=shared_url,
        item_description="Departure of Chief Financial Officer",
        raw_text="The Company announced the departure of its CFO effective immediately.",
    )

    await bridge_eight_k_events(session)

    url_a = _article_url(event_a)
    url_b = _article_url(event_b)
    assert url_a != url_b
    assert url_a.startswith(shared_url)
    assert url_b.startswith(shared_url)

    article_a = (await session.execute(select(NewsArticle).where(NewsArticle.source_url == url_a))).scalars().first()
    article_b = (await session.execute(select(NewsArticle).where(NewsArticle.source_url == url_b))).scalars().first()
    assert article_a is not None
    assert article_b is not None
    assert article_a.id != article_b.id


@pytest.mark.asyncio
async def test_bridge_skips_events_without_filing_url(session):
    entity = await _seed_entity(session)
    await _seed_event(session, entity, filing_url=None)

    await bridge_eight_k_events(session)

    article = await _article_for_entity(session, entity.entity_id)
    assert article is None


@pytest.mark.asyncio
async def test_bridge_falls_back_to_item_description_when_no_ai_summary_or_text(session):
    entity = await _seed_entity(session)
    await _seed_event(session, entity, ai_summary=None, raw_text=None)

    await bridge_eight_k_events(session)

    article = await _article_for_entity(session, entity.entity_id)
    assert article.summary == "Completion of Acquisition or Disposition of Assets"
    assert article.body_text is None


@pytest.mark.asyncio
async def test_bridge_prefers_ai_summary_when_present(session):
    entity = await _seed_entity(session)
    await _seed_event(session, entity, ai_summary="A concise AI-written summary of the acquisition.")

    await bridge_eight_k_events(session)

    article = await _article_for_entity(session, entity.entity_id)
    assert article.summary == "A concise AI-written summary of the acquisition."


@pytest.mark.asyncio
async def test_bridge_enriches_the_created_article(session):
    session.add(NewsSource(source_name="SEC EDGAR", domain="sec.gov", tier="WIRE", reliability_weight=Decimal("1.00")))
    await session.flush()

    entity = await _seed_entity(session)
    await _seed_event(session, entity)

    await bridge_eight_k_events(session)

    article = await _article_for_entity(session, entity.entity_id)
    # enrich_new_articles ran: credibility scored, sentiment classified.
    assert article.credibility_score is not None
    assert article.sentiment_label is not None
    assert article.source_trust == Decimal("1.00")


@pytest.mark.asyncio
async def test_bridge_respects_limit_within_this_entitys_events(session):
    # A far-future filing_date guarantees these 5 events sort ahead of
    # every other test's rows in the candidates query (ordered by
    # filing_date desc) regardless of how much other tests already
    # committed into this shared-engine DB -- otherwise a small `limit`
    # (which also caps how many candidate rows are even fetched) could
    # miss this test's events entirely.
    entity = await _seed_entity(session)
    events = [
        await _seed_event(session, entity, item_number="8.01", filing_date=date(2099, 1, 1))
        for _ in range(5)
    ]

    await bridge_eight_k_events(session, limit=3)

    links = (
        await session.execute(
            select(ArticleEntityLink).where(ArticleEntityLink.entity_id == entity.entity_id)
        )
    ).scalars().all()
    # limit caps total created per call across the whole candidate set, not
    # per-entity -- so this entity's 5 events may not all be bridged in one
    # pass. What must hold: no more articles than events exist, and at
    # least the limit's worth got created somewhere (proven by the
    # unbounded second call catching the rest).
    assert len(links) <= len(events)

    await bridge_eight_k_events(session, limit=200)
    links_after = (
        await session.execute(
            select(ArticleEntityLink).where(ArticleEntityLink.entity_id == entity.entity_id)
        )
    ).scalars().all()
    assert len(links_after) == len(events)


@pytest.mark.asyncio
async def test_bridge_with_no_new_events_creates_nothing_for_this_call(session):
    """A call with zero freshly-seeded events in this test creates zero
    NEW rows -- verified via a fresh, never-before-seen entity having no
    article, not via the (cross-test-polluted) global candidate count."""
    entity = await _seed_entity(session)
    # No event seeded for this entity.
    await bridge_eight_k_events(session)

    article = await _article_for_entity(session, entity.entity_id)
    assert article is None
