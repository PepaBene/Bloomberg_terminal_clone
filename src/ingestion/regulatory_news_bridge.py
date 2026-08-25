"""Layer 2 (AI_THREE_LAYER_REBUILD_PLAN.md §4.1): Federal Register
regulatory actions -> news_articles.

``src/ingestion/regulatory_actions.py`` already ingests Federal Register
API entries (agency, action type, title, publication date, source URL)
into ``regulatory_actions``, but -- same shape as the GDELT and 8-K gaps
this mirrors -- never reaches ``news_articles``. A new SEC enforcement
action or agency rule is exactly the kind of regulatory/primary-source
item §4.1 calls out wanting in the feed.

No natural primary entity here either (``affected_entity_ids`` is a JSONB
field the connector never actually populates -- Federal Register entries
don't come pre-linked to a specific CIK/entity), so this follows the
GDELT bridge's pattern: no propagation, entity linking (if any) via
free-text title matching only.
"""
from __future__ import annotations

import logging
import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.ingestion.news_enrichment import enrich_new_articles
from src.models.news_article import NewsArticle
from src.models.political_intelligence import RegulatoryAction

logger = logging.getLogger(__name__)

SOURCE_NAME = "Federal Register"


def _summary(action: RegulatoryAction) -> str:
    if action.description:
        return action.description
    if action.agency:
        return f"{action.agency}: {action.title}"
    return action.title


async def bridge_regulatory_actions(
    session: AsyncSession, *, limit: int = 200
) -> dict[str, int]:
    """Bridge up to ``limit`` not-yet-bridged RegulatoryAction rows (those
    with a ``source_url`` not already used by a NewsArticle) into
    news_articles, then enrich each. Commits. Best-effort per row.
    """
    candidates = (
        await session.execute(
            select(RegulatoryAction)
            .where(RegulatoryAction.source_url.isnot(None))
            .order_by(RegulatoryAction.action_date.desc())
            .limit(limit * 2)  # headroom: some will already be bridged
        )
    ).scalars().all()

    created_ids: list[uuid.UUID] = []
    stats = {"candidates": len(candidates), "created": 0, "already_bridged": 0}

    for action in candidates:
        if len(created_ids) >= limit:
            break

        existing_id = await session.scalar(
            select(NewsArticle.id).where(NewsArticle.source_url == action.source_url)
        )
        if existing_id is not None:
            stats["already_bridged"] += 1
            continue

        article_id = uuid.uuid4()
        session.add(NewsArticle(
            id=article_id,
            source_url=action.source_url,
            title=action.title[:500],
            summary=_summary(action),
            source_name=SOURCE_NAME,
            publish_date=action.action_date or date.today(),
            ingest_date=date.today(),
            news_type="REGULATORY_ACTION",
            materiality=action.severity,  # usually None -> enrich_article classifies it
            content_hash=None,
        ))
        created_ids.append(article_id)
        stats["created"] += 1

    if created_ids:
        await session.commit()
        await enrich_new_articles(session, created_ids, primary_entity_id=None, fetch_body_text=False)

    logger.info("[regulatory_news_bridge] %s", stats)
    return stats
