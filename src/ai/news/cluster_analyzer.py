"""Layer 2 (AI_THREE_LAYER_REBUILD_PLAN.md §4.4): per-cluster AI analysis.

SYNTHESIS tier -- follow-up to per-article analysis (analyzer.py), which
this module was always meant to complement (see that module's docstring).
A cluster has no owning row of its own: ``NewsArticle.cluster_id`` is a
self-reference on the cluster's first-seen ("representative") article, so
synthesis output rides on that representative row's
``cluster_analysis`` column rather than a separate table.
"""
from __future__ import annotations

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.ai.prompts import load_prompt
from src.models.news_article import NewsArticle

# Per-member articles are summarized compactly (not full body_text) -- a
# cluster prompt already fans out over N articles, so each one needs to
# stay cheap or the combined prompt balloons with member count.
MAX_MEMBER_SUMMARY_CHARS = 500


class ClusterSynthesisOutput(BaseModel):
    """Structured output for the ``news_cluster_analysis`` prompt."""

    consensus_summary: str
    divergent_views: list[str] = Field(default_factory=list)
    materiality_assessment: str
    confidence: float = Field(ge=0.0, le=1.0)


async def cluster_members(session: AsyncSession, representative: NewsArticle) -> list[NewsArticle]:
    """Every article (including the representative itself) whose
    ``cluster_id`` points at ``representative``."""
    rows = (
        await session.execute(
            select(NewsArticle)
            .where(NewsArticle.cluster_id == representative.id)
            .order_by(NewsArticle.publish_date.asc())
        )
    ).scalars().all()
    # A representative enriched before any corroborator joined its cluster
    # has cluster_id set to itself already; this covers that row even if
    # for some reason it wasn't returned by the query above (defensive,
    # not expected to trigger given _cluster_and_score_credibility's
    # invariant that a representative's cluster_id == its own id).
    if not any(r.id == representative.id for r in rows):
        rows = [representative, *rows]
    return rows


async def resolve_representative(session: AsyncSession, article: NewsArticle) -> NewsArticle:
    """The cluster's representative row for ``article`` -- itself if it
    already is one, else the row its ``cluster_id`` points at."""
    if article.cluster_id is None or article.cluster_id == article.id:
        return article
    representative = await session.get(NewsArticle, article.cluster_id)
    return representative or article


def _member_block(members: list[NewsArticle]) -> str:
    lines = []
    for m in members:
        text = m.body_text or m.summary or m.title
        if len(text) > MAX_MEMBER_SUMMARY_CHARS:
            text = text[:MAX_MEMBER_SUMMARY_CHARS].rsplit(" ", 1)[0] + "…"
        analysis_note = ""
        if m.ai_analysis and m.ai_analysis.get("interpretation"):
            analysis_note = f"\n  Interpretation: {m.ai_analysis['interpretation']}"
        lines.append(
            f"- [{m.source_name}] {m.title}\n  {text}{analysis_note}"
        )
    return "\n".join(lines)


async def synthesize_cluster(
    client, session: AsyncSession, representative: NewsArticle
) -> ClusterSynthesisOutput:
    """Synthesize a cluster's corroborating coverage. ``representative``
    must already be a cluster representative (``cluster_id == id``) --
    callers should resolve via ``resolve_representative`` first. Raises if
    the client is disabled, matching ``analyzer.analyze_article``'s
    convention."""
    if not client.enabled:
        raise RuntimeError("AI disabled: set ANTHROPIC_API_KEY and install 'anthropic'.")
    members = await cluster_members(session, representative)
    prompt = load_prompt("news_cluster_analysis")
    return await client.complete_structured(
        response_model=ClusterSynthesisOutput,
        user=prompt.render(
            representative_title=representative.title,
            corroboration_count=representative.corroboration_count,
            member_articles=_member_block(members),
        ),
        system=prompt.system,
        tier=prompt.tier,
        max_tokens=prompt.max_tokens,
        feature=prompt.feature,
    )
