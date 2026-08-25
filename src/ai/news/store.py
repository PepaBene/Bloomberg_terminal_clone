"""Compute-on-miss persistence for per-article AI analysis (§4.4).

Simpler than Layer 1's interpretations cache (``src/ai/interpret/store.py``):
articles are immutable once enrichment (Phase 2.1-2.3) has run, so there's
no separate freshness/version check to make -- ``ai_analysis is None`` is
the entire cache-miss condition. ``force_refresh`` bypasses it for a
manual re-run.
"""
from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from src.ai.models import model_for_tier
from src.ai.news.analyzer import ArticleAnalysisOutput, analyze_article
from src.ai.news.cluster_analyzer import ClusterSynthesisOutput, resolve_representative, synthesize_cluster
from src.ai.prompts import load_prompt
from src.models.news_article import NewsArticle

logger = logging.getLogger(__name__)


def _from_stored(blob: dict) -> ArticleAnalysisOutput:
    return ArticleAnalysisOutput(
        summary=blob.get("summary", ""),
        interpretation=blob.get("interpretation", ""),
        non_consensus_angle=blob.get("non_consensus_angle"),
        connections=blob.get("connections") or [],
        confidence=blob.get("confidence", 0.0),
    )


def _cluster_from_stored(blob: dict) -> ClusterSynthesisOutput:
    return ClusterSynthesisOutput(
        consensus_summary=blob.get("consensus_summary", ""),
        divergent_views=blob.get("divergent_views") or [],
        materiality_assessment=blob.get("materiality_assessment", ""),
        confidence=blob.get("confidence", 0.0),
    )


async def get_or_compute_article_analysis(
    session: AsyncSession,
    client,
    article: NewsArticle,
    *,
    force_refresh: bool = False,
) -> ArticleAnalysisOutput | None:
    """Return the article's AI analysis, computing and persisting it on a
    cache miss. Returns ``None`` when there's nothing cached and no way to
    compute a fresh read (AI disabled, or the call failed) -- never raises,
    matching ``src.ai.interpret.store``'s "omit rather than fail" contract.
    """
    if not force_refresh and article.ai_analysis is not None:
        return _from_stored(article.ai_analysis)
    if not client.enabled:
        return None

    try:
        output = await analyze_article(client, session, article)
    except Exception:  # noqa: BLE001
        logger.warning("analyze_article failed for article %s", article.id, exc_info=True)
        return None

    prompt = load_prompt("news_article_summary")
    article.ai_analysis = {
        "summary": output.summary,
        "interpretation": output.interpretation,
        "non_consensus_angle": output.non_consensus_angle,
        "connections": output.connections,
        "confidence": output.confidence,
        "model": model_for_tier(prompt.tier),
        "prompt_id": prompt.id,
        "prompt_version": prompt.version,
    }
    await session.flush()
    return output


async def get_or_compute_cluster_analysis(
    session: AsyncSession,
    client,
    article: NewsArticle,
    *,
    force_refresh: bool = False,
) -> tuple[NewsArticle, ClusterSynthesisOutput | None]:
    """Return the cluster's synthesis for whatever cluster ``article``
    belongs to, computing and persisting it (on the representative row) on
    a cache miss. Returns ``(representative, None)`` when there's nothing
    cached and no way to compute a fresh read -- same "omit rather than
    fail" contract as ``get_or_compute_article_analysis``. Callers get the
    resolved representative back since that's the row the analysis lives
    on, not necessarily the article they passed in.
    """
    representative = await resolve_representative(session, article)

    if not force_refresh and representative.cluster_analysis is not None:
        return representative, _cluster_from_stored(representative.cluster_analysis)
    if not client.enabled:
        return representative, None

    try:
        output = await synthesize_cluster(client, session, representative)
    except Exception:  # noqa: BLE001
        logger.warning(
            "synthesize_cluster failed for cluster %s", representative.id, exc_info=True
        )
        return representative, None

    prompt = load_prompt("news_cluster_analysis")
    representative.cluster_analysis = {
        "consensus_summary": output.consensus_summary,
        "divergent_views": output.divergent_views,
        "materiality_assessment": output.materiality_assessment,
        "confidence": output.confidence,
        "model": model_for_tier(prompt.tier),
        "prompt_id": prompt.id,
        "prompt_version": prompt.version,
    }
    await session.flush()
    return representative, output
