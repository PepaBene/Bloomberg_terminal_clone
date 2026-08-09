"""Tests for the Federal Register regulatory-actions-as-news bridge
(AI_THREE_LAYER_REBUILD_PLAN.md §4.1).

See test_sec_filing_news_bridge.py's module docstring for why every
assertion here is scoped to a specific, uuid-unique source_url rather
than global table counts (bridge_regulatory_actions commits, and the
session fixture's engine is shared across the whole test run).
"""

import uuid
from datetime import date

import pytest
from sqlalchemy import select

from src.ingestion.regulatory_news_bridge import bridge_regulatory_actions
from src.models.news_article import NewsArticle
from src.models.political_intelligence import RegulatoryAction

_UNSET = object()


def _unique_url() -> str:
    return f"https://www.federalregister.gov/documents/test-{uuid.uuid4().hex}"


async def _seed_action(session, *, url=_UNSET, **kwargs) -> RegulatoryAction:
    defaults = dict(
        id=uuid.uuid4(),
        agency="SEC",
        action_type="RULE",
        title="Final Rule: Amendments to Regulation S-K Disclosure Requirements",
        description="The Commission is adopting amendments to modernize disclosure requirements.",
        severity=None,
        action_date=date(2026, 1, 15),
        source_url=_unique_url() if url is _UNSET else url,
    )
    defaults.update(kwargs)
    action = RegulatoryAction(**defaults)
    session.add(action)
    await session.flush()
    return action


@pytest.mark.asyncio
async def test_bridge_creates_news_article_from_action(session):
    action = await _seed_action(session)

    stats = await bridge_regulatory_actions(session)
    assert stats["created"] >= 1

    article = (
        await session.execute(select(NewsArticle).where(NewsArticle.source_url == action.source_url))
    ).scalars().first()
    assert article is not None
    assert article.title == action.title
    assert article.source_name == "Federal Register"
    assert article.news_type == "REGULATORY_ACTION"
    assert article.publish_date == date(2026, 1, 15)


@pytest.mark.asyncio
async def test_bridge_is_idempotent(session):
    action = await _seed_action(session)

    await bridge_regulatory_actions(session)
    await bridge_regulatory_actions(session)

    articles = (
        await session.execute(select(NewsArticle).where(NewsArticle.source_url == action.source_url))
    ).scalars().all()
    assert len(articles) == 1


@pytest.mark.asyncio
async def test_bridge_skips_actions_without_source_url(session):
    unique_title = f"Untitled action {uuid.uuid4().hex}"
    await _seed_action(session, url=None, title=unique_title)

    await bridge_regulatory_actions(session)

    article = (
        await session.execute(select(NewsArticle).where(NewsArticle.title == unique_title))
    ).scalars().first()
    assert article is None


@pytest.mark.asyncio
async def test_bridge_uses_agency_prefixed_summary_when_no_description(session):
    action = await _seed_action(session, description=None, agency="FTC")

    await bridge_regulatory_actions(session)

    article = (
        await session.execute(select(NewsArticle).where(NewsArticle.source_url == action.source_url))
    ).scalars().first()
    assert article.summary.startswith("FTC:")


@pytest.mark.asyncio
async def test_bridge_classifies_missing_materiality_via_enrichment(session):
    """severity is always None from this connector -- enrich_article's
    classification (news_type == REGULATORY_ACTION -> MEDIUM) fills it in."""
    action = await _seed_action(session)

    await bridge_regulatory_actions(session)

    article = (
        await session.execute(select(NewsArticle).where(NewsArticle.source_url == action.source_url))
    ).scalars().first()
    assert article.materiality == "MEDIUM"


@pytest.mark.asyncio
async def test_bridge_enriches_the_created_article(session):
    action = await _seed_action(session)

    await bridge_regulatory_actions(session)

    article = (
        await session.execute(select(NewsArticle).where(NewsArticle.source_url == action.source_url))
    ).scalars().first()
    assert article.credibility_score is not None
    assert article.sentiment_label is not None
    assert article.is_propagated is False
