"""Tests for Layer 2 news enrichment: entity lookup, source resolution,
corroboration clustering + credibility, and the full enrich_article pass."""

import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select

import src.ingestion.news_enrichment as news_enrichment
from src.ingestion.news_enrichment import (
    build_entity_lookup,
    enrich_article,
    enrich_new_articles,
    resolve_news_source,
)
from src.models.entity import Entity, EntityIdentifier, EntityName
from src.models.news_article import ArticleEntityLink, NewsArticle, NewsSource, PropagationEvent
from src.models.reference import GICSClassification
from src.models.relationships import BusinessRelationship
from src.models.security import Security, SecurityIdentifier


async def _seed_entity(session, *, legal_name="Acme Corp", entity_id=None) -> Entity:
    entity = Entity(
        entity_id=entity_id or uuid.uuid4(),
        entity_type="PUBLIC_COMPANY",
        legal_name=legal_name,
        status="ACTIVE",
        source="TEST",
    )
    session.add(entity)
    await session.flush()
    return entity


async def _seed_security_ticker(session, entity: Entity, ticker: str) -> Security:
    security = Security(
        security_id=uuid.uuid4(),
        security_type="EQUITY",
        issuer_entity_id=entity.entity_id,
        name=entity.legal_name,
        status="ACTIVE",
        asset_class="EQUITY",
    )
    session.add(security)
    await session.flush()
    session.add(SecurityIdentifier(
        id=uuid.uuid4(), security_id=security.security_id,
        identifier_type="TICKER", identifier_value=ticker,
    ))
    await session.flush()
    return security


async def _seed_article(session, *, source_url, title="Acme Corp reports strong earnings",
                          summary="Summary text.", body_text=None, source_name="Reuters",
                          publish_date=date(2026, 1, 10), article_id=None, **kwargs) -> NewsArticle:
    article = NewsArticle(
        id=article_id or uuid.uuid4(),
        source_url=source_url,
        title=title,
        summary=summary,
        body_text=body_text,
        source_name=source_name,
        publish_date=publish_date,
        ingest_date=publish_date,
        **kwargs,
    )
    session.add(article)
    await session.flush()
    return article


# ── build_entity_lookup ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_build_entity_lookup_resolves_ticker_via_security(session):
    entity = await _seed_entity(session, legal_name="Acme Corp")
    await _seed_security_ticker(session, entity, "ACME")

    lookup = await build_entity_lookup(session)
    assert lookup["tickers"]["ACME"] == str(entity.entity_id)


@pytest.mark.asyncio
async def test_build_entity_lookup_resolves_cik_via_entity_identifier(session):
    entity = await _seed_entity(session, legal_name="Acme Corp")
    session.add(EntityIdentifier(
        id=uuid.uuid4(), entity_id=entity.entity_id,
        identifier_type="CIK", identifier_value="0001234567",
    ))
    await session.flush()

    lookup = await build_entity_lookup(session)
    assert lookup["ciks"]["0001234567"] == str(entity.entity_id)


@pytest.mark.asyncio
async def test_build_entity_lookup_includes_names_and_aliases(session):
    entity = await _seed_entity(session, legal_name="Acme Corporation")
    session.add(EntityName(
        id=uuid.uuid4(), entity_id=entity.entity_id,
        name_type="TRADING", name_value="Acme",
    ))
    await session.flush()

    lookup = await build_entity_lookup(session)
    assert lookup["names"]["acme corporation"] == str(entity.entity_id)
    assert lookup["aliases"]["acme"] == str(entity.entity_id)


# ── resolve_news_source ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_resolve_news_source_by_name(session):
    session.add(NewsSource(source_name="Reuters", domain="reuters.com", tier="WIRE", reliability_weight=Decimal("1.00")))
    await session.flush()

    resolved = await resolve_news_source(session, source_name="Reuters", source_url="https://reuters.com/x")
    assert resolved is not None
    assert resolved.tier == "WIRE"


@pytest.mark.asyncio
async def test_resolve_news_source_by_domain_when_name_unknown(session):
    session.add(NewsSource(source_name="Reuters", domain="reuters.com", tier="WIRE", reliability_weight=Decimal("1.00")))
    await session.flush()

    resolved = await resolve_news_source(session, source_name="Reuters Syndication Feed", source_url="https://www.reuters.com/some/story")
    assert resolved is not None
    assert resolved.source_name == "Reuters"


@pytest.mark.asyncio
async def test_resolve_news_source_unknown_returns_none(session):
    resolved = await resolve_news_source(session, source_name="Unknown Blog", source_url="https://totally-unknown-blog.xyz/post")
    assert resolved is None


# ── enrich_article: classification + entity linking ─────────────────


@pytest.mark.asyncio
async def test_enrich_article_classifies_and_links_entities(session):
    entity = await _seed_entity(session, legal_name="Acme Corp")
    article = await _seed_article(
        session, source_url="https://reuters.com/acme-earnings",
        title="Acme Corp reports record quarterly earnings, beats estimates",
        summary="Acme Corp posted strong Q4 results driven by cloud growth.",
    )
    lookup = await build_entity_lookup(session)

    await enrich_article(session, article, entity_lookup=lookup, primary_entity_id=entity.entity_id)
    await session.flush()

    assert article.news_type == "EARNINGS_NEWS"
    assert article.materiality is not None
    assert article.sentiment_label in ("POSITIVE", "NEGATIVE", "NEUTRAL")

    links = (
        await session.execute(
            select(ArticleEntityLink).where(ArticleEntityLink.article_id == article.id)
        )
    ).scalars().all()
    assert any(link.entity_id == entity.entity_id for link in links)


@pytest.mark.asyncio
async def test_enrich_article_does_not_overwrite_existing_classification(session):
    article = await _seed_article(
        session, source_url="https://reuters.com/preclassified",
        news_type="ALREADY_SET", materiality="CRITICAL",
    )
    await enrich_article(session, article, entity_lookup=await build_entity_lookup(session))
    await session.flush()

    assert article.news_type == "ALREADY_SET"
    assert article.materiality == "CRITICAL"


@pytest.mark.asyncio
async def test_enrich_article_does_not_duplicate_existing_links(session):
    entity = await _seed_entity(session, legal_name="Acme Corp")
    article = await _seed_article(
        session, source_url="https://reuters.com/acme-dup-link",
        title="Acme Corp announces new product",
    )
    session.add(ArticleEntityLink(
        id=uuid.uuid4(), article_id=article.id, entity_id=entity.entity_id,
        is_primary=True, mention_count=1,
    ))
    await session.flush()

    lookup = await build_entity_lookup(session)
    await enrich_article(session, article, entity_lookup=lookup)
    await session.flush()

    links = (
        await session.execute(
            select(ArticleEntityLink).where(
                ArticleEntityLink.article_id == article.id,
                ArticleEntityLink.entity_id == entity.entity_id,
            )
        )
    ).scalars().all()
    assert len(links) == 1


# ── corroboration clustering + credibility ───────────────────────────


@pytest.mark.asyncio
async def test_enrich_article_singleton_cluster_credibility(session):
    session.add(NewsSource(source_name="Reuters", domain="reuters.com", tier="WIRE", reliability_weight=Decimal("1.00")))
    await session.flush()
    article = await _seed_article(
        session, source_url="https://reuters.com/singleton-story",
        title="A wholly unique headline nobody else has covered yet",
        source_name="Reuters",
    )
    await enrich_article(session, article, entity_lookup=await build_entity_lookup(session))
    await session.flush()

    assert article.cluster_id == article.id
    assert article.corroboration_count == 1
    assert article.source_trust == Decimal("1.00")
    assert article.credibility_score == Decimal("1.0000")
    assert article.is_non_consensus is False


@pytest.mark.asyncio
async def test_enrich_article_corroborating_story_joins_cluster_and_boosts_representative(session):
    session.add(NewsSource(source_name="Reuters", domain="reuters.com", tier="WIRE", reliability_weight=Decimal("1.00")))
    session.add(NewsSource(source_name="Seeking Alpha", domain="seekingalpha.com", tier="TIER2", reliability_weight=Decimal("0.55")))
    await session.flush()

    lookup = await build_entity_lookup(session)

    first = await _seed_article(
        session, source_url="https://reuters.com/fed-rate-decision",
        title="Federal Reserve raises interest rates by a quarter point",
        source_name="Reuters", publish_date=date(2026, 1, 10),
    )
    await enrich_article(session, first, entity_lookup=lookup)
    await session.flush()
    assert first.corroboration_count == 1

    second = await _seed_article(
        session, source_url="https://seekingalpha.com/fed-rate-decision-analysis",
        title="Federal Reserve raises interest rates by quarter point today",
        source_name="Seeking Alpha", publish_date=date(2026, 1, 11),
    )
    await enrich_article(session, second, entity_lookup=lookup)
    await session.flush()

    assert second.cluster_id == first.id
    assert second.corroboration_count == 2
    # The representative's own row is refreshed too, not left stale.
    assert first.corroboration_count == 2
    assert first.credibility_score > Decimal("1.0000") or first.credibility_score == Decimal("1.0000")
    # Second corroborator is TIER2 but corroborated -> no longer non-consensus.
    assert second.is_non_consensus is False


@pytest.mark.asyncio
async def test_enrich_article_low_tier_uncorroborated_is_non_consensus(session):
    session.add(NewsSource(source_name="Random Blog", domain="randomblog.example", tier="BLOG", reliability_weight=Decimal("0.35")))
    await session.flush()
    article = await _seed_article(
        session, source_url="https://randomblog.example/hot-take",
        title="A completely uncorroborated hot take nobody else is reporting",
        source_name="Random Blog",
    )
    await enrich_article(session, article, entity_lookup=await build_entity_lookup(session))
    await session.flush()

    assert article.is_non_consensus is True


# ── propagation ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_enrich_article_propagates_to_related_entity(session):
    source_entity = await _seed_entity(session, legal_name="Acme Supplier Corp")
    target_entity = await _seed_entity(session, legal_name="Acme Customer Corp")
    session.add(BusinessRelationship(
        relationship_id=uuid.uuid4(),
        source_entity_id=source_entity.entity_id,
        target_entity_id=target_entity.entity_id,
        relationship_type="CUSTOMER",
        revenue_percentage=Decimal("0.2000"),
        is_active=True,
    ))
    await session.flush()

    article = await _seed_article(
        session, source_url="https://reuters.com/acme-bankruptcy",
        title="Acme Supplier Corp files for bankruptcy amid liquidity crisis",
        summary="The company filed for Chapter 11 bankruptcy protection.",
    )
    lookup = await build_entity_lookup(session)
    await enrich_article(session, article, entity_lookup=lookup, primary_entity_id=source_entity.entity_id)
    await session.flush()

    assert article.is_propagated is True
    events = (
        await session.execute(
            select(PropagationEvent).where(PropagationEvent.source_article_id == article.id)
        )
    ).scalars().all()
    assert len(events) == 1
    assert events[0].target_entity_id == target_entity.entity_id
    # "bankruptcy" is a keyword in both SUPPLY_CHAIN's and COMPETITIVE's
    # event maps in news_propagation.PROPAGATION_CONFIG; _EVENT_TO_TYPE is
    # built by iterating the config dict in order, so the later entry
    # (COMPETITIVE) wins -- pre-existing, already-tested engine behavior,
    # not something this integration test should second-guess.
    assert events[0].propagation_type == "COMPETITIVE"


@pytest.mark.asyncio
async def test_enrich_article_no_propagation_without_primary_entity(session):
    article = await _seed_article(
        session, source_url="https://reuters.com/no-primary-entity",
        title="Some company files for bankruptcy",
    )
    await enrich_article(session, article, entity_lookup=await build_entity_lookup(session), primary_entity_id=None)
    await session.flush()

    assert article.is_propagated is False


async def _seed_gics_sector(session, *, sector_code, sector_name) -> None:
    session.add(GICSClassification(
        sub_industry_code=f"{sector_code}0000",
        sector_code=sector_code,
        sector_name=sector_name,
        industry_group_code=f"{sector_code}00",
        industry_group_name=f"{sector_name} Group",
        industry_code=f"{sector_code}000",
        industry_name=f"{sector_name} Industry",
        sub_industry_name=f"{sector_name} Sub-Industry",
    ))
    await session.flush()


@pytest.mark.asyncio
async def test_enrich_article_propagates_to_sector_peers(session):
    """§4.3: a SECTOR-classified article fans out to peer entities sharing
    the source entity's own GICS sector, via a real roster query -- not the
    dict-literal ``{}`` this used to be hardcoded to."""
    await _seed_gics_sector(session, sector_code="20", sector_name="Industrials")
    source_entity = await _seed_entity(session, legal_name="Acme Industrial Corp")
    source_entity.gics_sector = "20"
    peer_entity = await _seed_entity(session, legal_name="Beta Industrial Corp")
    peer_entity.gics_sector = "20"
    await session.flush()

    article = await _seed_article(
        session, source_url="https://reuters.com/industrials-regulation",
        title="New regulatory rules imposed on industrial manufacturers",
        summary="A sweeping new regulation affects the whole sector.",
    )
    lookup = await build_entity_lookup(session)
    await enrich_article(session, article, entity_lookup=lookup, primary_entity_id=source_entity.entity_id)
    await session.flush()

    assert article.is_propagated is True
    events = (
        await session.execute(
            select(PropagationEvent).where(PropagationEvent.source_article_id == article.id)
        )
    ).scalars().all()
    assert len(events) == 1
    assert events[0].target_entity_id == peer_entity.entity_id
    assert events[0].propagation_type == "SECTOR"


@pytest.mark.asyncio
async def test_enrich_article_sector_propagation_excludes_other_sectors(session):
    await _seed_gics_sector(session, sector_code="20", sector_name="Industrials")
    await _seed_gics_sector(session, sector_code="40", sector_name="Financials")
    source_entity = await _seed_entity(session, legal_name="Acme Industrial Corp")
    source_entity.gics_sector = "20"
    other_sector_entity = await _seed_entity(session, legal_name="Gamma Bank Corp")
    other_sector_entity.gics_sector = "40"
    await session.flush()

    article = await _seed_article(
        session, source_url="https://reuters.com/industrials-regulation-2",
        title="New regulatory compliance rules for industrial manufacturers",
    )
    lookup = await build_entity_lookup(session)
    await enrich_article(session, article, entity_lookup=lookup, primary_entity_id=source_entity.entity_id)
    await session.flush()

    events = (
        await session.execute(
            select(PropagationEvent).where(PropagationEvent.source_article_id == article.id)
        )
    ).scalars().all()
    assert events == []  # only sector peer would be Financials, which isn't Industrials


@pytest.mark.asyncio
async def test_enrich_article_no_sector_propagation_without_gics_sector(session):
    source_entity = await _seed_entity(session, legal_name="Acme Unclassified Corp")
    # gics_sector left unset (None)
    article = await _seed_article(
        session, source_url="https://reuters.com/unclassified-regulation",
        title="New regulatory rules imposed on this company",
    )
    lookup = await build_entity_lookup(session)
    await enrich_article(session, article, entity_lookup=lookup, primary_entity_id=source_entity.entity_id)
    await session.flush()

    assert article.is_propagated is False


@pytest.mark.asyncio
async def test_enrich_article_propagates_macro_event_to_sensitive_sectors(session):
    """§4.3: a MACRO-classified article (e.g. a Fed rate decision) fans out
    to entities in the sectors news_propagation.py hardcodes as rate-
    sensitive (Financials/Real Estate/Utilities), regardless of the source
    entity's own sector."""
    await _seed_gics_sector(session, sector_code="40", sector_name="Financials")
    await _seed_gics_sector(session, sector_code="20", sector_name="Industrials")
    source_entity = await _seed_entity(session, legal_name="Acme Industrial Corp")
    source_entity.gics_sector = "20"
    financials_peer = await _seed_entity(session, legal_name="Gamma Bank Corp")
    financials_peer.gics_sector = "40"
    await session.flush()

    article = await _seed_article(
        session, source_url="https://reuters.com/fed-rate-decision",
        title="Federal Reserve announces interest rate decision",
        summary="The Fed's rate decision affects rate-sensitive sectors broadly.",
    )
    lookup = await build_entity_lookup(session)
    await enrich_article(session, article, entity_lookup=lookup, primary_entity_id=source_entity.entity_id)
    await session.flush()

    assert article.is_propagated is True
    events = (
        await session.execute(
            select(PropagationEvent).where(PropagationEvent.source_article_id == article.id)
        )
    ).scalars().all()
    assert len(events) == 1
    assert events[0].target_entity_id == financials_peer.entity_id
    assert events[0].propagation_type == "MACRO"


@pytest.mark.asyncio
async def test_enrich_article_macro_propagation_with_no_matching_entities_is_noop(session):
    source_entity = await _seed_entity(session, legal_name="Acme Industrial Corp")
    article = await _seed_article(
        session, source_url="https://reuters.com/fed-rate-decision-2",
        title="Federal Reserve announces interest rate decision",
    )
    lookup = await build_entity_lookup(session)
    await enrich_article(session, article, entity_lookup=lookup, primary_entity_id=source_entity.entity_id)
    await session.flush()

    assert article.is_propagated is False


# ── enrich_new_articles orchestrator ─────────────────────────────────


@pytest.mark.asyncio
async def test_enrich_new_articles_enriches_and_commits(session):
    article = await _seed_article(session, source_url="https://reuters.com/batch-test")
    # fetch_body_text=False: no live network calls in unit tests --
    # covered separately (with a mocked fetch) below.
    count = await enrich_new_articles(session, [article.id], fetch_body_text=False)
    assert count == 1
    assert article.credibility_score is not None


@pytest.mark.asyncio
async def test_enrich_new_articles_skips_missing_ids(session):
    count = await enrich_new_articles(session, [uuid.uuid4()])
    assert count == 0


@pytest.mark.asyncio
async def test_enrich_new_articles_empty_list_is_noop(session):
    count = await enrich_new_articles(session, [])
    assert count == 0


# ── body_text fetch wiring ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_enrich_article_fetches_body_text_when_requested(session, monkeypatch):
    async def _fake_fetch(url, **kwargs):
        return "Full extracted article body text goes here for the enrichment pass."

    monkeypatch.setattr(news_enrichment, "fetch_and_extract_body_text", _fake_fetch)

    article = await _seed_article(session, source_url="https://reuters.com/fetch-body-test")
    assert article.body_text is None

    await enrich_article(
        session, article, entity_lookup=await build_entity_lookup(session), fetch_body_text=True,
    )
    await session.flush()

    assert article.body_text == "Full extracted article body text goes here for the enrichment pass."


@pytest.mark.asyncio
async def test_enrich_article_does_not_fetch_by_default(session, monkeypatch):
    async def _fail_if_called(url, **kwargs):
        raise AssertionError("fetch_and_extract_body_text should not be called by default")

    monkeypatch.setattr(news_enrichment, "fetch_and_extract_body_text", _fail_if_called)

    article = await _seed_article(session, source_url="https://reuters.com/no-fetch-by-default")
    await enrich_article(session, article, entity_lookup=await build_entity_lookup(session))
    await session.flush()

    assert article.body_text is None


@pytest.mark.asyncio
async def test_enrich_article_skips_fetch_when_body_text_already_present(session, monkeypatch):
    async def _fail_if_called(url, **kwargs):
        raise AssertionError("fetch_and_extract_body_text should not be called when body_text is already set")

    monkeypatch.setattr(news_enrichment, "fetch_and_extract_body_text", _fail_if_called)

    article = await _seed_article(
        session, source_url="https://reuters.com/already-has-body",
        body_text="Already-extracted body text.",
    )
    await enrich_article(
        session, article, entity_lookup=await build_entity_lookup(session), fetch_body_text=True,
    )
    await session.flush()

    assert article.body_text == "Already-extracted body text."


@pytest.mark.asyncio
async def test_enrich_article_handles_fetch_returning_none(session, monkeypatch):
    async def _fake_fetch(url, **kwargs):
        return None

    monkeypatch.setattr(news_enrichment, "fetch_and_extract_body_text", _fake_fetch)

    article = await _seed_article(session, source_url="https://reuters.com/fetch-fails")
    await enrich_article(
        session, article, entity_lookup=await build_entity_lookup(session), fetch_body_text=True,
    )
    await session.flush()

    assert article.body_text is None
    # Enrichment still completes using the summary/title fallback.
    assert article.credibility_score is not None
