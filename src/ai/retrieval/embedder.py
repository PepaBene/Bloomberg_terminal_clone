"""Embedding wrapper for the retrieval stack.

Wraps ``src/services/ai/embedding_client.py`` (Gemini ``gemini-embedding-002``)
rather than replacing it -- that client already handles batching, task types,
and graceful degradation correctly.

Dimensionality: the legacy ``search_documents.embedding`` column stores the
model's native 3072-dim output, which pgvector cannot index (HNSW/IVFFlat
both cap at 2000 dims -- see migration 087's comment). Gemini's embedding API
natively supports requesting a smaller ``output_dimensionality`` server-side
(already threaded through as ``EmbeddingClient.embed_text(..., dimensions=)``)
rather than truncating client-side, so this module standardizes the whole new
retrieval stack on a single indexable dimension instead of double-embedding
every chunk at both sizes.

1536 was chosen as a safe margin under the 2000-dim cap that still retains
strong retrieval quality for this model per Google's Matryoshka-trained
embedding documentation -- the same "sweet spot" dimensionality OpenAI's
text-embedding-3-small defaults to. Not validated against a live Gemini
response in this sandbox (no network access); the choice is a documented,
adjustable constant (``INDEXED_DIMENSIONS``), not a hardcoded assumption
buried in SQL.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from src.services.ai.embedding_client import (
    EmbeddingResult,
    get_embedding_client,
)
from src.services.ai.embedding_client import (
    TASK_RETRIEVAL_DOCUMENT as _TASK_DOCUMENT,
)
from src.services.ai.embedding_client import (
    TASK_RETRIEVAL_QUERY as _TASK_QUERY,
)

logger = logging.getLogger(__name__)

# The dimensionality every new retrieval write/query standardizes on --
# indexable (< pgvector's 2000-dim HNSW/IVFFlat cap) while the legacy 3072-dim
# `embedding`/`embedding_vector` columns are left untouched for backward
# compatibility with the pre-existing brute-force `vector_search.py` path.
INDEXED_DIMENSIONS = 1536


@dataclass(frozen=True)
class EmbeddedChunk:
    """A chunk's text paired with its indexed-dimension embedding."""

    text: str
    embedding: list[float]
    dimensions: int
    model: str


def is_configured() -> bool:
    return get_embedding_client().is_configured


def embed_documents(texts: list[str]) -> list[EmbeddedChunk]:
    """Embed a batch of chunk texts for storage (RETRIEVAL_DOCUMENT task type).

    Returns ``[]`` when the embedding client isn't configured (no
    ``GOOGLE_API_KEY`` / ``google-genai`` not installed) rather than raising
    -- callers should check ``is_configured()`` first if they need to
    distinguish "nothing to embed" from "embedding unavailable."
    """
    if not texts:
        return []
    client = get_embedding_client()
    if not client.is_configured:
        logger.warning("embed_documents: embedding client not configured — skipping")
        return []
    results: list[EmbeddingResult] = client.embed_batch(
        texts, dimensions=INDEXED_DIMENSIONS, task_type=_TASK_DOCUMENT
    )
    return [
        EmbeddedChunk(text=t, embedding=r.embedding, dimensions=r.dimensions, model=r.model)
        for t, r in zip(texts, results)
    ]


def embed_query(query: str) -> list[float] | None:
    """Embed a search query (RETRIEVAL_QUERY task type). ``None`` if unavailable."""
    client = get_embedding_client()
    if not client.is_configured or not query.strip():
        return None
    result = client.embed_text(query, dimensions=INDEXED_DIMENSIONS, task_type=_TASK_QUERY)
    return result.embedding
