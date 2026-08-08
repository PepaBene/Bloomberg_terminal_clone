"""Unit tests for the retrieval (RAG) stack (Phase 0).

Pure functions (chunker, BM25 ranking, RRF fusion) get full coverage without
a DB or API key. ``store.upsert_chunks`` is exercised against the in-memory
SQLite test engine (the vector column round-trips as a JSON list there).
``store.vector_search`` / ``retriever.hybrid_search`` need live Postgres +
pgvector + a configured embedding key and are NOT covered here -- see their
docstrings' FLAG.
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.ai.retrieval.chunker import chunk_text
from src.ai.retrieval.embedder import EmbeddedChunk, embed_documents, embed_query
from src.ai.retrieval.retriever import bm25_rank, reciprocal_rank_fusion
from src.ai.retrieval.store import upsert_chunks, vector_search
from src.models.semantic_search import SearchDocument

# --------------------------------------------------------------------------- #
# chunker
# --------------------------------------------------------------------------- #
def test_chunk_text_empty_and_short():
    assert chunk_text("") == []
    assert chunk_text("   ") == []
    chunks = chunk_text("just one short sentence.")
    assert len(chunks) == 1
    assert chunks[0].text == "just one short sentence."
    assert chunks[0].start_char == 0
    assert chunks[0].index == 0


def test_chunk_text_splits_long_text_and_preserves_offsets():
    text = "\n\n".join(f"Paragraph {i}. It has a couple of sentences in it. Extra filler." for i in range(20))
    chunks = chunk_text(text, max_tokens=30, overlap_tokens=5)
    assert len(chunks) > 1
    for c in chunks:
        assert text[c.start_char:c.end_char] != ""
        assert c.token_count >= 1
    # indices are sequential starting at 0
    assert [c.index for c in chunks] == list(range(len(chunks)))
    # chunks progress forward through the document
    starts = [c.start_char for c in chunks]
    assert starts == sorted(starts)


def test_chunk_text_overlap_actually_duplicates_boundary_content():
    text = " ".join(f"Sentence number {i} here." for i in range(40))
    chunks = chunk_text(text, max_tokens=20, overlap_tokens=8)
    assert len(chunks) >= 2
    # the legacy chunker accepted `overlap` but never applied it -- assert
    # consecutive chunks actually share trailing/leading content.
    tail = chunks[0].text[-15:]
    assert tail in chunks[1].text


def test_chunk_text_hard_splits_a_single_giant_word():
    giant = "x" * 500
    chunks = chunk_text(giant, max_tokens=10, overlap_tokens=0)
    assert len(chunks) > 1
    assert "".join(c.text for c in chunks).count("x") == 500


def test_chunk_text_zero_overlap_has_no_duplication():
    text = " ".join(f"Word{i}" for i in range(200))
    chunks = chunk_text(text, max_tokens=10, overlap_tokens=0)
    assert len(chunks) > 1
    seen: set[str] = set()
    for c in chunks:
        words = c.text.split()
        overlap = seen.intersection(words)
        # zero overlap budget should carry at most the single unavoidable
        # boundary unit forward, never the whole previous chunk
        assert len(overlap) <= 1
        seen = set(words)


# --------------------------------------------------------------------------- #
# BM25 + RRF (pure)
# --------------------------------------------------------------------------- #
def test_bm25_rank_orders_by_relevance():
    corpus = [
        ("a", "Apple reported record iPhone revenue this quarter"),
        ("b", "The Federal Reserve raised interest rates by 25 basis points"),
        ("c", "Apple stock price target raised by analysts after strong earnings"),
        ("d", "completely unrelated text about gardening tips"),
    ]
    ranked = bm25_rank("Apple earnings revenue", corpus)
    assert ranked[0] in ("a", "c")
    assert "d" not in ranked  # zero lexical overlap -> score 0 -> excluded


def test_bm25_rank_empty_inputs():
    assert bm25_rank("query", []) == []
    assert bm25_rank("", [("a", "some text")]) == []
    assert bm25_rank("   ", [("a", "some text")]) == []


def test_reciprocal_rank_fusion_rewards_agreement():
    fused = reciprocal_rank_fusion([["a", "b", "c"], ["b", "a", "d"]])
    # 'a' and 'b' appear in both rankings near the top -> higher fused score
    # than 'c'/'d', which each appear in only one ranking.
    assert fused["a"] > fused["c"]
    assert fused["b"] > fused["d"]


def test_reciprocal_rank_fusion_handles_disjoint_and_empty_rankings():
    fused = reciprocal_rank_fusion([["a"], []])
    assert fused == {"a": pytest.approx(1.0 / (60 + 1))}
    assert reciprocal_rank_fusion([]) == {}
    assert reciprocal_rank_fusion([[], []]) == {}


# --------------------------------------------------------------------------- #
# embedder (disabled path -- no GOOGLE_API_KEY in test env)
# --------------------------------------------------------------------------- #
def test_embed_documents_empty_input():
    assert embed_documents([]) == []


def test_embed_documents_returns_empty_when_unconfigured(monkeypatch):
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    import src.services.ai.embedding_client as ec
    ec._embedding_client = None  # reset the module singleton
    assert embed_documents(["some text"]) == []
    assert embed_query("some query") is None


# --------------------------------------------------------------------------- #
# store (SQLite-compatible: plain ORM insert/delete, vector column -> JSON)
# --------------------------------------------------------------------------- #
async def test_upsert_chunks_writes_and_replaces(engine):
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    chunks = chunk_text("First sentence here. Second sentence follows along nicely.", max_tokens=5, overlap_tokens=0)
    embedded = [
        EmbeddedChunk(text=c.text, embedding=[0.1] * 4, dimensions=4, model="test-model")
        for c in chunks
    ]

    async with factory() as session:
        ids = await upsert_chunks(
            session, source_type="unit_test", source_id="doc-1",
            chunks=chunks, embedded=embedded, title="Test Doc",
        )
        await session.commit()
    assert len(ids) == len(chunks) >= 1

    async with factory() as session:
        rows = (
            await session.execute(
                select(SearchDocument).where(SearchDocument.source_id == "doc-1")
            )
        ).scalars().all()
        assert len(rows) == len(chunks)
        assert {r.chunk_index for r in rows} == {c.index for c in chunks}
        assert all(r.embedding_1536 == [0.1] * 4 for r in rows)

    # Re-upsert with fewer chunks -- old rows for this source must be gone,
    # not left behind as orphans.
    new_chunks = chunk_text("Just one short replacement chunk.")
    new_embedded = [EmbeddedChunk(text=new_chunks[0].text, embedding=[0.2] * 4, dimensions=4, model="test-model")]
    async with factory() as session:
        await upsert_chunks(
            session, source_type="unit_test", source_id="doc-1",
            chunks=new_chunks, embedded=new_embedded,
        )
        await session.commit()

    async with factory() as session:
        rows = (
            await session.execute(
                select(SearchDocument).where(SearchDocument.source_id == "doc-1")
            )
        ).scalars().all()
        assert len(rows) == 1
        assert rows[0].chunk_text == new_chunks[0].text


async def test_upsert_chunks_rejects_length_mismatch(session):
    chunks = chunk_text("one sentence chunk here.")
    with pytest.raises(ValueError):
        await upsert_chunks(
            session, source_type="unit_test", source_id="doc-mismatch",
            chunks=chunks, embedded=[],
        )


async def test_vector_search_requires_postgres_vector_comparator(session):
    # SQLite remaps Vector -> JSON (see tests/conftest.py), which has no
    # cosine_distance comparator -- this documents the real constraint
    # rather than silently skipping coverage of store.vector_search.
    with pytest.raises(Exception):
        await vector_search(session, [0.1, 0.2, 0.3])
