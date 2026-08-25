"""Retrieval (RAG) stack: chunk -> embed -> store -> hybrid retrieve.

Public surface:
    from src.ai.retrieval import chunk_text, embed_documents, embed_query
    from src.ai.retrieval import upsert_chunks, vector_search
    from src.ai.retrieval import hybrid_search, bm25_rank, reciprocal_rank_fusion
"""
from src.ai.retrieval.chunker import Chunk, chunk_text
from src.ai.retrieval.embedder import (
    INDEXED_DIMENSIONS,
    EmbeddedChunk,
    embed_documents,
    embed_query,
)
from src.ai.retrieval.retriever import (
    RetrievedChunk,
    bm25_rank,
    hybrid_search,
    reciprocal_rank_fusion,
)
from src.ai.retrieval.store import VectorHit, fetch_candidate_pool, upsert_chunks, vector_search

__all__ = [
    "Chunk",
    "chunk_text",
    "EmbeddedChunk",
    "INDEXED_DIMENSIONS",
    "embed_documents",
    "embed_query",
    "VectorHit",
    "upsert_chunks",
    "vector_search",
    "fetch_candidate_pool",
    "RetrievedChunk",
    "bm25_rank",
    "reciprocal_rank_fusion",
    "hybrid_search",
]
