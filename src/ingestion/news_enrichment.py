"""Layer 2 (AI_THREE_LAYER_REBUILD_PLAN.md §4.2/§4.3): wires the
previously-dormant ``news_dedup`` / ``news_entity_linker`` /
``news_propagation`` / ``finbert_sentiment`` engines into the ingestion
path, plus §4.2's trust/corroboration credibility scoring.

Called after a connector (e.g. ``finnhub_news.py``) inserts raw
``NewsArticle`` rows. Nothing here fetches new articles -- it enriches ones
already committed to the session: classification, additional multi-entity
links, corroboration clustering + credibility, sentiment, and propagation.
Best-effort per article, matching ``scripts/interpret_batch.py``'s pattern
of one bad row not sinking the batch.
"""
from __future__ import annotations

import logging
import uuid
from datetime import timedelta
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.engines import news_credibility
from src.engines.finbert_sentiment import score_text
from src.ingestion.article_extraction import fetch_and_extract_body_text
from src.engines.news_entity_linker import (
    assess_materiality,
    classify_news_type,
    classify_topics,
    link_entities,
)
from src.engines.news_propagation import propagate_event
from src.models.entity import Entity, EntityIdentifier, EntityName
from src.models.news_article import ArticleEntityLink, NewsArticle, NewsSource, PropagationEvent
from src.models.relationships import BusinessRelationship
from src.models.security import Security, SecurityIdentifier

logger = logging.getLogger(__name__)

# How far back to look for corroborating coverage when clustering. Keeps
# the window query cheap as news_articles grows -- corroboration is a "did
# anyone else cover this in the last few days" question, not a full scan.
CLUSTER_WINDOW_DAYS = 3

_ALIAS_NAME_TYPES = ("TRADING", "ALIAS", "DBA", "SHORT", "PREVIOUS")


async def build_entity_lookup(session: AsyncSession) -> dict:
    """Build the ``{tickers, ciks, cusips, isins, names, aliases}`` shape
    ``news_entity_linker.link_entities`` needs, from entity/security
    master data actually populated today.

    Tickers/CUSIPs/ISINs live on ``SecurityIdentifier`` (security-level),
    resolved to an issuing entity via ``Security.issuer_entity_id`` -- NOT
    on ``EntityIdentifier``, which only carries entity-level identifiers
    like CIK. First-seen wins on collisions -- acceptable for a
    best-effort linker, not a system of record.
    """
    tickers: dict[str, str] = {}
    cusips: dict[str, str] = {}
    isins: dict[str, str] = {}
    sec_rows = (
        await session.execute(
            select(
                SecurityIdentifier.identifier_type,
                SecurityIdentifier.identifier_value,
                Security.issuer_entity_id,
            )
            .join(Security, Security.security_id == SecurityIdentifier.security_id)
            .where(Security.issuer_entity_id.isnot(None))
            .where(SecurityIdentifier.identifier_type.in_(["TICKER", "CUSIP", "ISIN"]))
        )
    ).all()
    dest_by_type = {"TICKER": tickers, "CUSIP": cusips, "ISIN": isins}
    for id_type, id_value, entity_id in sec_rows:
        dest_by_type[id_type].setdefault(id_value, str(entity_id))

    ciks: dict[str, str] = {}
    cik_rows = (
        await session.execute(
            select(EntityIdentifier.identifier_value, EntityIdentifier.entity_id)
            .where(EntityIdentifier.identifier_type == "CIK")
        )
    ).all()
    for value, entity_id in cik_rows:
        ciks.setdefault(value, str(entity_id))

    names: dict[str, str] = {}
    name_rows = (await session.execute(select(Entity.legal_name, Entity.entity_id))).all()
    for legal_name, entity_id in name_rows:
        if legal_name:
            names.setdefault(legal_name.lower(), str(entity_id))

    aliases: dict[str, str] = {}
    alias_rows = (
        await session.execute(
            select(EntityName.name_value, EntityName.entity_id)
            .where(EntityName.name_type.in_(_ALIAS_NAME_TYPES))
        )
    ).all()
    for value, entity_id in alias_rows:
        if value:
            aliases.setdefault(value.lower(), str(entity_id))

    return {
        "tickers": tickers, "ciks": ciks, "cusips": cusips,
        "isins": isins, "names": names, "aliases": aliases,
    }


def _extract_domain(url: str) -> str | None:
    try:
        netloc = urlparse(url).netloc.lower()
    except ValueError:
        return None
    if not netloc:
        return None
    return netloc[4:] if netloc.startswith("www.") else netloc


async def resolve_news_source(
    session: AsyncSession, *, source_name: str | None, source_url: str
) -> NewsSource | None:
    """Trust/credibility record for an article's source: exact
    ``source_name`` match first (what connectors already report), then the
    article URL's domain."""
    if source_name:
        row = await session.get(NewsSource, source_name)
        if row is not None:
            return row
    domain = _extract_domain(source_url)
    if not domain:
        return None
    return (
        await session.execute(select(NewsSource).where(NewsSource.domain == domain))
    ).scalars().first()


async def _recent_cluster_candidates(
    session: AsyncSession, article: NewsArticle
) -> list[news_credibility.ClusterCandidate]:
    since = article.publish_date - timedelta(days=CLUSTER_WINDOW_DAYS)
    rows = (
        await session.execute(
            select(NewsArticle).where(
                NewsArticle.publish_date >= since,
                NewsArticle.publish_date <= article.publish_date,
                NewsArticle.id != article.id,
            )
        )
    ).scalars().all()
    return [
        news_credibility.ClusterCandidate(
            id=str(r.id), source_url=r.source_url, title=r.title, body_text=r.body_text,
        )
        for r in rows
    ]


async def _cluster_and_score_credibility(session: AsyncSession, article: NewsArticle) -> None:
    """Assigns cluster_id / corroboration_count / is_non_consensus /
    source_trust / credibility_score on ``article`` in place.

    A cluster's corroboration count lives on its representative row (the
    first article seen); joining a cluster increments the representative's
    count -- and refreshes ITS credibility score too, since a fresh
    corroboration changes what the representative's own score should be --
    and this article inherits the representative's cluster_id.
    """
    source = await resolve_news_source(
        session, source_name=article.source_name, source_url=article.source_url
    )
    tier = source.tier if source else None
    article.source_trust = source.reliability_weight if source else None

    candidates = await _recent_cluster_candidates(session, article)
    self_candidate = news_credibility.ClusterCandidate(
        id=str(article.id), source_url=article.source_url,
        title=article.title, body_text=article.body_text,
    )
    match = news_credibility.find_cluster_match(self_candidate, candidates)

    if match is None:
        article.cluster_id = article.id
        article.corroboration_count = 1
    else:
        representative = await session.get(NewsArticle, uuid.UUID(match.id))
        rep_cluster_id = representative.cluster_id or representative.id
        if rep_cluster_id != representative.id:
            representative = await session.get(NewsArticle, rep_cluster_id)

        representative.corroboration_count += 1
        rep_source = await resolve_news_source(
            session, source_name=representative.source_name, source_url=representative.source_url
        )
        rep_tier = rep_source.tier if rep_source else None
        representative.credibility_score = news_credibility.compute_credibility_score(
            tier=rep_tier, corroboration_count=representative.corroboration_count,
        )
        representative.is_non_consensus = news_credibility.classify_non_consensus(
            tier=rep_tier, corroboration_count=representative.corroboration_count,
        )

        article.cluster_id = representative.id
        article.corroboration_count = representative.corroboration_count

    article.credibility_score = news_credibility.compute_credibility_score(
        tier=tier, corroboration_count=article.corroboration_count,
    )
    article.is_non_consensus = news_credibility.classify_non_consensus(
        tier=tier, corroboration_count=article.corroboration_count,
    )


async def _propagate(
    session: AsyncSession, article: NewsArticle, *, primary_entity_id: uuid.UUID | None
) -> None:
    """Entity-to-entity propagation only (SUPPLY_CHAIN/CUSTOMER/COMPETITIVE
    hop-1, via real ``BusinessRelationship`` rows). SECTOR/MACRO
    propagation needs a full GICS-sector entity roster this pass doesn't
    build (querying/grouping the entire entity universe per article) -- a
    real, mechanical follow-up, not scoped out for a design reason.
    """
    if primary_entity_id is None or article.is_propagated:
        return

    rel_rows = (
        await session.execute(
            select(BusinessRelationship).where(
                BusinessRelationship.source_entity_id == primary_entity_id,
                BusinessRelationship.is_active.is_(True),
            )
        )
    ).scalars().all()
    if not rel_rows:
        return

    relationships = [
        {
            "source_id": str(r.source_entity_id),
            "target_id": str(r.target_entity_id),
            "relationship_type": r.relationship_type,
            "revenue_pct": float(r.revenue_percentage) if r.revenue_percentage is not None else 1.0,
        }
        for r in rel_rows
    ]
    result = propagate_event(
        source_entity_id=str(primary_entity_id),
        article_data={
            "title": article.title,
            "text": article.body_text or article.summary or "",
            "topics": article.topics or [],
            "materiality": article.materiality,
        },
        relationships=relationships,
        sector_entities={},
    )
    if result is None or not result.targets:
        return

    for target in result.targets:
        try:
            target_entity_id = uuid.UUID(target.target_entity_id)
        except ValueError:
            continue
        session.add(PropagationEvent(
            id=uuid.uuid4(),
            source_article_id=article.id,
            source_entity_id=primary_entity_id,
            target_entity_id=target_entity_id,
            propagation_type=target.propagation_type,
            hop_number=target.hop_number,
            relevance_score=target.relevance_score,
            event_summary=target.event_summary[:500],
            severity=target.severity,
        ))
    article.is_propagated = True
    article.propagation_source = result.event_category[:30]


async def enrich_article(
    session: AsyncSession,
    article: NewsArticle,
    *,
    entity_lookup: dict,
    primary_entity_id: uuid.UUID | None = None,
    fetch_body_text: bool = False,
) -> None:
    """Full Layer 2 enrichment pass on one already-persisted article:
    optional body_text extraction, classification, multi-entity linking,
    corroboration clustering + credibility, sentiment, propagation.
    Mutates ``article`` and adds any new ``ArticleEntityLink``/
    ``PropagationEvent`` rows -- caller commits.

    ``fetch_body_text`` defaults to ``False`` -- it's the only network I/O
    in this whole pass (everything else is DB + pure computation), so
    tests and any other caller that doesn't want live HTTP calls get that
    for free; ``enrich_new_articles`` (the production entry point) opts
    it back in.
    """
    if fetch_body_text and article.body_text is None:
        fetched = await fetch_and_extract_body_text(article.source_url)
        if fetched:
            article.body_text = fetched

    text_for_nlp = article.body_text or article.summary or ""

    if article.news_type is None:
        article.news_type = classify_news_type(article.title, text_for_nlp)
    if not article.topics:
        article.topics = classify_topics(article.title, text_for_nlp)

    mentions = link_entities(text_for_nlp, article.title, entity_lookup)
    if mentions:
        existing_links = set(
            (
                await session.execute(
                    select(ArticleEntityLink.entity_id).where(
                        ArticleEntityLink.article_id == article.id
                    )
                )
            ).scalars().all()
        )
        for m in mentions:
            try:
                mention_entity_id = uuid.UUID(m.entity_id)
            except ValueError:
                continue
            if mention_entity_id in existing_links:
                continue
            session.add(ArticleEntityLink(
                id=uuid.uuid4(), article_id=article.id, entity_id=mention_entity_id,
                relevance_score=m.relevance_score, confidence=m.confidence,
                is_primary=m.is_primary, mention_text=m.mention_text[:200], mention_count=1,
            ))
            existing_links.add(mention_entity_id)

    if article.materiality is None:
        article.materiality = assess_materiality(
            article.news_type or "OTHER", len(mentions), article.topics or [], text_for_nlp,
        )

    await _cluster_and_score_credibility(session, article)

    result = score_text(article.body_text or f"{article.title}. {article.summary or ''}")
    article.sentiment_score = round(result.composite_score, 2)
    article.sentiment_confidence = round(result.confidence, 2)
    article.sentiment_label = result.sentiment

    await _propagate(session, article, primary_entity_id=primary_entity_id)


async def enrich_new_articles(
    session: AsyncSession,
    article_ids: list[uuid.UUID],
    *,
    primary_entity_id: uuid.UUID | None = None,
    fetch_body_text: bool = True,
) -> int:
    """Enrich a batch of newly-inserted articles (e.g. from one connector
    call) and commit. Returns the number successfully enriched.

    This is the production entry point (called by ``finnhub_news.py``
    after each fetch), so ``fetch_body_text`` defaults to ``True`` here --
    opposite of ``enrich_article``'s own default -- opting into the one
    piece of network I/O in the pipeline. Pass ``False`` to skip it (e.g.
    a caller that already has full text, or wants a fast/offline pass).
    """
    if not article_ids:
        return 0
    entity_lookup = await build_entity_lookup(session)
    enriched = 0
    for aid in article_ids:
        article = await session.get(NewsArticle, aid)
        if article is None:
            continue
        try:
            await enrich_article(
                session, article, entity_lookup=entity_lookup,
                primary_entity_id=primary_entity_id, fetch_body_text=fetch_body_text,
            )
            enriched += 1
        except Exception:  # noqa: BLE001
            logger.warning("news enrichment failed for article %s", aid, exc_info=True)
    await session.commit()
    return enriched
