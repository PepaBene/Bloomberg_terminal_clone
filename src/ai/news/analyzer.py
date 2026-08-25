"""Layer 2 (AI_THREE_LAYER_REBUILD_PLAN.md §4.4): per-article AI analysis.

LIGHT tier, structured output. Trust-weighted (uses the article's own
source_trust/credibility_score/corroboration_count -- Phase 2.1/2.2 —
as grounding context, not just the raw text) and grounded in the
article's already-computed propagation targets (Phase 2.2's
``PropagationEvent`` rows) for the "connections" field, rather than
re-deriving entity/sector links from scratch.

Cluster-level (SYNTHESIS tier, corroboration-cluster synthesis) and
digest-level analysis are NOT built here -- a distinct unit of work
(a cluster has no single owning row the way an article does), tracked
as a follow-up.
"""
from __future__ import annotations

import uuid

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.ai.prompts import load_prompt
from src.models.entity import Entity
from src.models.news_article import NewsArticle, PropagationEvent

# Body text is truncated for the prompt -- LIGHT tier is meant to be cheap
# and fast; a multi-thousand-word wire story doesn't need to be sent in
# full for a summary+interpretation pass.
MAX_BODY_CHARS = 4000


class ArticleAnalysisOutput(BaseModel):
    """Structured output for the ``news_article_summary`` prompt."""

    summary: str
    interpretation: str
    non_consensus_angle: str | None = None
    connections: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)


def _non_consensus_note(article: NewsArticle) -> str:
    return " (flagged as needing corroboration)" if article.is_non_consensus else ""


def _body_for_prompt(article: NewsArticle) -> str:
    text = article.body_text or article.summary or article.title
    return text if len(text) <= MAX_BODY_CHARS else text[:MAX_BODY_CHARS].rsplit(" ", 1)[0] + "…"


async def _render_connections(session: AsyncSession, article: NewsArticle) -> str:
    rows = (
        await session.execute(
            select(PropagationEvent, Entity.legal_name)
            .join(Entity, Entity.entity_id == PropagationEvent.target_entity_id)
            .where(PropagationEvent.source_article_id == article.id)
        )
    ).all()
    if not rows:
        return "(no propagation connections computed for this article)"
    lines = []
    for event, legal_name in rows:
        lines.append(
            f"- {legal_name} ({event.propagation_type}, hop {event.hop_number}, "
            f"severity={event.severity}): {event.event_summary}"
        )
    return "\n".join(lines)


async def analyze_article(
    client, session: AsyncSession, article: NewsArticle
) -> ArticleAnalysisOutput:
    """Analyze one article. Raises if the client is disabled -- callers
    that want best-effort batching should catch and skip, matching
    ``src.ai.interpret.interpreter``'s convention."""
    if not client.enabled:
        raise RuntimeError("AI disabled: set ANTHROPIC_API_KEY and install 'anthropic'.")
    prompt = load_prompt("news_article_summary")
    connections = await _render_connections(session, article)
    return await client.complete_structured(
        response_model=ArticleAnalysisOutput,
        user=prompt.render(
            title=article.title,
            source_name=article.source_name,
            source_trust=float(article.source_trust) if article.source_trust is not None else "unknown",
            credibility_score=float(article.credibility_score) if article.credibility_score is not None else "unknown",
            corroboration_count=article.corroboration_count,
            non_consensus_note=_non_consensus_note(article),
            publish_date=article.publish_date.isoformat(),
            body=_body_for_prompt(article),
            connections=connections,
        ),
        system=prompt.system,
        tier=prompt.tier,
        max_tokens=prompt.max_tokens,
        feature=prompt.feature,
    )
