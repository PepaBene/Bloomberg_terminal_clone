"""Layer 2 (AI_THREE_LAYER_REBUILD_PLAN.md §4.1): GDELT articles -> news_articles.

``src/ingestion/gdelt_geopolitical.py`` already pulls real geopolitical
coverage (military conflict, sanctions, trade war, coup, election,
terrorism) from the GDELT 2.0 DOC API, but writes exclusively to
``geopolitical_events`` -- the plan's own gap analysis (§4.1) calls this
out by name: "GDELT articles into news_articles (today it only writes
geopolitical_events)".

This bridges each ``GeopoliticalEvent`` row into a ``NewsArticle``. No
entity is naturally implied the way an 8-K filing implies its filer
(these are macro/geopolitical, not company events) -- entity linking (if
any) comes from ``news_entity_linker`` free-text matching the title, and
propagation is skipped (``primary_entity_id=None``): there is no natural
"source entity" for a macro event to propagate outward from.
"""
from __future__ import annotations

import logging
import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.ingestion.news_enrichment import enrich_new_articles
from src.models.country_risk import GeopoliticalEvent
from src.models.news_article import NewsArticle

logger = logging.getLogger(__name__)

SOURCE_NAME = "GDELT"

# event_type -> a materiality floor. GDELT's own severity (already computed
# per-topic by the connector, HIGH/MEDIUM/LOW) is used directly as
# materiality; this only backstops the rare row with no severity at all.
DEFAULT_MATERIALITY = "MEDIUM"


def _summary(event: GeopoliticalEvent) -> str:
    return event.description or event.title


async def bridge_geopolitical_events(
    session: AsyncSession, *, limit: int = 200
) -> dict[str, int]:
    """Bridge up to ``limit`` not-yet-bridged GeopoliticalEvent rows (those
    with a ``source_url`` not already used by a NewsArticle) into
    news_articles, then enrich each. Commits. Best-effort per row.
    """
    candidates = (
        await session.execute(
            select(GeopoliticalEvent)
            .where(GeopoliticalEvent.source_url.isnot(None))
            .order_by(GeopoliticalEvent.start_date.desc())
            .limit(limit * 2)  # headroom: some will already be bridged
        )
    ).scalars().all()

    created_ids: list[uuid.UUID] = []
    stats = {"candidates": len(candidates), "created": 0, "already_bridged": 0}

    for event in candidates:
        if len(created_ids) >= limit:
            break

        existing_id = await session.scalar(
            select(NewsArticle.id).where(NewsArticle.source_url == event.source_url)
        )
        if existing_id is not None:
            stats["already_bridged"] += 1
            continue

        article_id = uuid.uuid4()
        session.add(NewsArticle(
            id=article_id,
            source_url=event.source_url,
            title=event.title[:500],
            summary=_summary(event),
            source_name=SOURCE_NAME,
            publish_date=event.start_date or date.today(),
            ingest_date=date.today(),
            news_type="MACRO_RELEASE" if event.event_type in ("SANCTIONS", "TRADE_WAR") else None,
            materiality=event.severity or DEFAULT_MATERIALITY,
            content_hash=None,
        ))
        created_ids.append(article_id)
        stats["created"] += 1

    if created_ids:
        await session.commit()
        await enrich_new_articles(session, created_ids, primary_entity_id=None, fetch_body_text=False)

    logger.info("[gdelt_news_bridge] %s", stats)
    return stats
