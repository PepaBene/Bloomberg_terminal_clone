"""Hybrid retriever: pgvector KNN + BM25 lexical, fused via Reciprocal Rank Fusion.

Two independent rankings, not a rerank-within-vector-hits pass: a query that's
mostly a ticker or exact figure can be a strong lexical match with mediocre
cosine similarity (embeddings are a semantic, not exact-match, signal), so
BM25 runs over its own candidate pool (``store.fetch_candidate_pool``) rather
than only the vector hits, and RRF combines the two rankings without either
one silently dominating.

The RRF fusion (``reciprocal_rank_fusion``) and BM25 ranking (``bm25_rank``)
are pure functions, fully unit-testable without a DB or API key.
``hybrid_search`` is the orchestrator and needs a live embedding API + a
Postgres backend for ``store.vector_search`` -- see that function's FLAG.
"""
from __future__ import annotations

import logging
import re
import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from src.ai.retrieval import store
from src.ai.retrieval.embedder import embed_query

logger = logging.getLogger(__name__)

DEFAULT_TOP_K = 6
DEFAULT_VECTOR_CANDIDATES = 50
DEFAULT_LEXICAL_CANDIDATES = 500
RRF_K = 60  # standard RRF damping constant

_TOKEN_RE = re.compile(r"[A-Za-z0-9]+")


@dataclass(frozen=True)
class RetrievedChunk:
    """One chunk from a hybrid search, with per-signal rank provenance."""

    document_id: str
    chunk_text: str
    score: float  # fused RRF score
    vector_rank: int | None
    bm25_rank: int | None
    source_type: str | None = None
    source_id: str | None = None
    title: str | None = None
    entity_id: uuid.UUID | None = None
    chunk_index: int | None = None


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


def bm25_rank(query: str, corpus: list[tuple[str, str]]) -> list[str]:
    """Rank ``corpus`` (``(doc_id, text)`` pairs) against ``query`` via BM25Okapi.

    Pure function -- no DB, no API. Returns doc_ids best-to-worst; empty
    corpus or empty query yields ``[]``.
    """
    if not corpus or not query.strip():
        return []
    from rank_bm25 import BM25Okapi

    doc_ids = [doc_id for doc_id, _ in corpus]
    tokenized_corpus = [_tokenize(text) for _, text in corpus]
    bm25 = BM25Okapi(tokenized_corpus)
    scores = bm25.get_scores(_tokenize(query))
    ranked = sorted(zip(doc_ids, scores), key=lambda p: p[1], reverse=True)
    return [doc_id for doc_id, score in ranked if score > 0]


def reciprocal_rank_fusion(
    rankings: list[list[str]], k: int = RRF_K
) -> dict[str, float]:
    """Fuse multiple doc_id rankings into one score per doc_id.

    ``score(d) = sum over rankings containing d of 1 / (k + rank)`` (rank is
    1-indexed). A doc absent from a ranking simply contributes nothing from
    it -- this is what lets a lexical-only or vector-only hit still surface
    instead of requiring agreement between both signals.
    """
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, doc_id in enumerate(ranking, start=1):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank)
    return scores


async def hybrid_search(
    session: AsyncSession,
    query: str,
    *,
    k: int = DEFAULT_TOP_K,
    vector_candidates: int = DEFAULT_VECTOR_CANDIDATES,
    lexical_candidates: int = DEFAULT_LEXICAL_CANDIDATES,
    source_type: str | None = None,
    entity_id: uuid.UUID | None = None,
) -> list[RetrievedChunk]:
    """Vector KNN + BM25 lexical, RRF-fused, top-``k`` with provenance.

    Degrades gracefully rather than raising: if the embedding API is
    unavailable, this falls back to lexical-only ranking (empty vector
    ranking contributes nothing to the fusion, per ``reciprocal_rank_fusion``).
    Requires live Postgres+pgvector for the vector half -- untested against
    one in this sandbox, see ``store.vector_search``'s FLAG.
    """
    query_vec = embed_query(query)
    vector_hits: list[store.VectorHit] = []
    if query_vec is not None:
        try:
            vector_hits = await store.vector_search(
                session, query_vec, k=vector_candidates,
                source_type=source_type, entity_id=entity_id,
            )
        except Exception:
            logger.exception("hybrid_search: vector_search failed — falling back to lexical-only")
    else:
        logger.info("hybrid_search: embedding unavailable — lexical-only ranking")

    candidate_pool = await store.fetch_candidate_pool(
        session, limit=lexical_candidates, source_type=source_type, entity_id=entity_id,
    )
    lexical_ranking = bm25_rank(query, candidate_pool)
    vector_ranking = [str(h.document_id) for h in vector_hits]

    fused = reciprocal_rank_fusion([vector_ranking, lexical_ranking])
    if not fused:
        return []

    vector_rank_by_id = {doc_id: i + 1 for i, doc_id in enumerate(vector_ranking)}
    lexical_rank_by_id = {doc_id: i + 1 for i, doc_id in enumerate(lexical_ranking)}
    hit_by_id = {str(h.document_id): h for h in vector_hits}
    text_by_id = dict(candidate_pool)

    top_ids = sorted(fused, key=lambda d: fused[d], reverse=True)[:k]
    results: list[RetrievedChunk] = []
    for doc_id in top_ids:
        hit = hit_by_id.get(doc_id)
        results.append(RetrievedChunk(
            document_id=doc_id,
            chunk_text=hit.chunk_text if hit else text_by_id.get(doc_id, ""),
            score=fused[doc_id],
            vector_rank=vector_rank_by_id.get(doc_id),
            bm25_rank=lexical_rank_by_id.get(doc_id),
            source_type=hit.source_type if hit else source_type,
            source_id=hit.source_id if hit else None,
            title=hit.title if hit else None,
            entity_id=hit.entity_id if hit else entity_id,
            chunk_index=hit.chunk_index if hit else None,
        ))
    return results
