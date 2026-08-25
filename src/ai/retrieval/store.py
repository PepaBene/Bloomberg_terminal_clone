"""pgvector-backed storage for the retrieval stack.

Writes/reads ``search_documents.embedding_1536`` (migration 094) via the ORM
-- ``pgvector.sqlalchemy.Vector`` provides ``.cosine_distance()`` /
``.l2_distance()`` comparators that compile to the real ``<=>``/``<->``
operators, so this doesn't hand-roll raw SQL for the similarity query.

FLAG -- ``vector_search()`` requires live Postgres with the ``vector``
extension: the test suite's SQLite engine remaps ``Vector`` columns to plain
``JSON`` (see ``tests/conftest.py``'s ``_remap_jsonb``), which has no
``cosine_distance`` comparator at all, so this function cannot be exercised
in this sandbox and has not been run against a live payload. ``upsert_chunks``
*is* covered -- it's a plain ORM insert/delete that works under either
dialect (the vector column just round-trips as a JSON list under SQLite).
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.ai.retrieval.chunker import Chunk
from src.ai.retrieval.embedder import EmbeddedChunk
from src.models.semantic_search import SearchDocument


@dataclass(frozen=True)
class VectorHit:
    """One chunk returned by a vector similarity query."""

    document_id: uuid.UUID
    chunk_text: str
    similarity: float  # 1 - cosine_distance; ~[0, 1] for normalized embeddings
    source_type: str
    source_id: str | None
    title: str | None
    entity_id: uuid.UUID | None
    chunk_index: int
    metadata: dict | None


async def upsert_chunks(
    session: AsyncSession,
    *,
    source_type: str,
    source_id: str | None,
    chunks: list[Chunk],
    embedded: list[EmbeddedChunk],
    title: str | None = None,
    author: str | None = None,
    publish_date: date | None = None,
    entity_id: uuid.UUID | None = None,
    metadata: dict | None = None,
) -> list[uuid.UUID]:
    """Replace all stored chunks for ``(source_type, source_id)`` with new ones.

    Full-replace, not per-chunk upsert: ``search_documents`` has no unique
    constraint on ``(source_type, source_id, chunk_index)`` to key an upsert
    against, and a re-embedded document's chunk boundaries can shift
    entirely (chunker change, edited source text) -- partial per-chunk
    merging would risk orphaned stale rows for no real benefit.
    """
    if len(chunks) != len(embedded):
        raise ValueError(
            f"chunks/embedded length mismatch: {len(chunks)} vs {len(embedded)}"
        )

    await session.execute(
        delete(SearchDocument).where(
            SearchDocument.source_type == source_type,
            SearchDocument.source_id == source_id,
        )
    )

    ids: list[uuid.UUID] = []
    for chunk, emb in zip(chunks, embedded):
        doc_id = uuid.uuid4()
        session.add(SearchDocument(
            id=doc_id,
            source_type=source_type,
            source_id=source_id,
            title=title,
            author=author,
            publish_date=publish_date,
            entity_id=entity_id,
            chunk_index=chunk.index,
            chunk_text=chunk.text,
            chunk_token_count=chunk.token_count,
            embedding_model=emb.model,
            embedding_1536=emb.embedding,
            metadata_=metadata,
        ))
        ids.append(doc_id)
    await session.flush()
    return ids


async def vector_search(
    session: AsyncSession,
    query_embedding: list[float],
    *,
    k: int = 20,
    source_type: str | None = None,
    entity_id: uuid.UUID | None = None,
) -> list[VectorHit]:
    """Top-``k`` chunks by cosine similarity against ``embedding_1536``.

    Requires a Postgres backend with the ``vector`` extension and the HNSW
    index from migration 094 -- see module FLAG above.
    """
    distance = SearchDocument.embedding_1536.cosine_distance(query_embedding)
    query = (
        select(SearchDocument, distance.label("distance"))
        .where(SearchDocument.embedding_1536.is_not(None))
        .order_by(distance)
        .limit(k)
    )
    if source_type:
        query = query.where(SearchDocument.source_type == source_type)
    if entity_id:
        query = query.where(SearchDocument.entity_id == entity_id)

    rows = (await session.execute(query)).all()
    return [
        VectorHit(
            document_id=doc.id,
            chunk_text=doc.chunk_text,
            similarity=1.0 - float(dist),
            source_type=doc.source_type,
            source_id=doc.source_id,
            title=doc.title,
            entity_id=doc.entity_id,
            chunk_index=doc.chunk_index,
            metadata=doc.metadata_,
        )
        for doc, dist in rows
    ]


async def fetch_candidate_pool(
    session: AsyncSession,
    *,
    limit: int,
    source_type: str | None = None,
    entity_id: uuid.UUID | None = None,
) -> list[tuple[str, str]]:
    """Plain ``(id, chunk_text)`` pairs for the lexical/BM25 half of hybrid
    search. Works on any dialect (no vector column touched).

    A bare filtered LIMIT scan, not a real full-text prefilter -- fine for
    Phase 0 / small corpora since BM25 does the actual relevance sorting
    over whatever this returns, but at real scale this should be backed by
    a Postgres ``tsvector``/GIN index instead of an arbitrary row LIMIT.
    """
    query = select(SearchDocument.id, SearchDocument.chunk_text).limit(limit)
    if source_type:
        query = query.where(SearchDocument.source_type == source_type)
    if entity_id:
        query = query.where(SearchDocument.entity_id == entity_id)
    rows = (await session.execute(query)).all()
    return [(str(doc_id), text) for doc_id, text in rows]
