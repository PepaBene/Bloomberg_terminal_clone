"""Layer 2 (AI_THREE_LAYER_REBUILD_PLAN.md §4.1): SEC filings-as-news
bridge -- 8-K material events -> news_articles.

``src/ingestion/edgar_8k.py`` already parses 8-K item-level events (with
item classification, priority, materiality, and the extracted item text)
into ``eight_k_events``, but that table is only ever read by filing-
intelligence surfaces -- it never reaches the news feed, so the same
"Item 5.02 director departure" or "Item 2.01 acquisition completed" event
that would legitimately be a top news story is invisible to every
news_articles consumer (the feed, sentiment scoring, propagation).

This bridges each ``EightKEvent`` row into a ``NewsArticle`` + entity
link, then runs it through the same enrichment pass (§4.2/§4.3) real
ingested news gets. No network fetch needed for body_text -- the 8-K
connector already extracted the item's raw text, which is a better
source than anything trafilatura could pull from a re-fetched filing
page.
"""
from __future__ import annotations

import logging
import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.ingestion.news_enrichment import enrich_new_articles
from src.models.entity import Entity
from src.models.filing_intelligence import EightKEvent
from src.models.news_article import ArticleEntityLink, NewsArticle

logger = logging.getLogger(__name__)

SOURCE_NAME = "SEC EDGAR"
# Cap on how much of an 8-K item's extracted text becomes the article
# summary -- the full text still lands in body_text untruncated.
SUMMARY_MAX_CHARS = 500


def _article_url(event: EightKEvent) -> str | None:
    """One filing can carry several material items (several EightKEvent
    rows sharing one ``filing_url``); NewsArticle.source_url is unique, so
    each item gets its own URL via a fragment identifier -- still opens
    the right filing when clicked, doesn't collide across items."""
    if not event.filing_url:
        return None
    return f"{event.filing_url}#item-{event.item_number}"


def _build_summary(event: EightKEvent) -> str:
    if event.ai_summary:
        return event.ai_summary
    if event.raw_text:
        text = event.raw_text.strip()
        return text if len(text) <= SUMMARY_MAX_CHARS else text[:SUMMARY_MAX_CHARS].rsplit(" ", 1)[0] + "…"
    return event.item_description or f"SEC Form 8-K Item {event.item_number}"


async def bridge_eight_k_events(
    session: AsyncSession, *, limit: int = 200
) -> dict[str, int]:
    """Bridge up to ``limit`` not-yet-bridged EightKEvent rows into
    news_articles, link + enrich each. Commits. Best-effort per row.

    "Not yet bridged" is determined by the constructed URL not already
    existing as a NewsArticle.source_url -- the same idempotency pattern
    ``finnhub_news.py`` uses, no separate progress ledger needed since
    each candidate's existence check is cheap and the batch is naturally
    bounded by ``limit``.
    """
    candidates = (
        await session.execute(
            select(EightKEvent, Entity.legal_name)
            .join(Entity, Entity.entity_id == EightKEvent.entity_id)
            .where(EightKEvent.filing_url.isnot(None))
            .order_by(EightKEvent.filing_date.desc())
            .limit(limit * 2)  # headroom: some will already be bridged
        )
    ).all()

    created_ids: list[uuid.UUID] = []
    entity_by_article: dict[uuid.UUID, uuid.UUID] = {}
    stats = {"candidates": len(candidates), "created": 0, "skipped_no_url": 0, "already_bridged": 0}

    for event, legal_name in candidates:
        if len(created_ids) >= limit:
            break
        url = _article_url(event)
        if url is None:
            stats["skipped_no_url"] += 1
            continue

        existing_id = await session.scalar(select(NewsArticle.id).where(NewsArticle.source_url == url))
        if existing_id is not None:
            stats["already_bridged"] += 1
            continue

        article_id = uuid.uuid4()
        session.add(NewsArticle(
            id=article_id,
            source_url=url,
            title=f"{legal_name}: {event.item_description or f'Form 8-K Item {event.item_number}'}",
            summary=_build_summary(event),
            body_text=event.raw_text,
            source_name=SOURCE_NAME,
            publish_date=event.filing_date,
            ingest_date=date.today(),
            news_type="REGULATORY_ACTION" if event.item_number == "5.07" else None,
            materiality=event.materiality,
            content_hash=None,
        ))
        session.add(ArticleEntityLink(
            id=uuid.uuid4(), article_id=article_id, entity_id=event.entity_id,
            relevance_score=1.0, confidence=1.0, is_primary=True,
            mention_text=legal_name[:200], mention_count=1,
        ))
        created_ids.append(article_id)
        entity_by_article[article_id] = event.entity_id
        stats["created"] += 1

    if created_ids:
        await session.commit()
        # Enrichment is per-entity (propagation needs a single primary
        # entity), so batch by entity rather than one enrich_new_articles
        # call for the whole mixed-entity set.
        by_entity: dict[uuid.UUID, list[uuid.UUID]] = {}
        for aid, eid in entity_by_article.items():
            by_entity.setdefault(eid, []).append(aid)
        for eid, aids in by_entity.items():
            await enrich_new_articles(session, aids, primary_entity_id=eid, fetch_body_text=False)

    logger.info("[sec_filing_news_bridge] %s", stats)
    return stats
