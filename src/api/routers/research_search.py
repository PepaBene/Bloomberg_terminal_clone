"""Semantic Search API endpoints (Pillar 3 Phase 4B)."""

import asyncio
import math
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, or_, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_optional_user, get_session
from src.models.entity import Entity
from src.models.semantic_search import SearchDocument, SearchQuery
from src.schemas.semantic_search_schema import (
    DocumentStatsResponse,
    IndexDocumentRequest,
    IndexDocumentResponse,
    SearchChunkResponse,
    SearchHistoryResponse,
    SearchRequest,
    SearchResultResponse,
    SuggestedQueryResponse,
    TrendingTopicResponse,
)
from src.services.ai.embedding_client import get_embedding_client

router = APIRouter(tags=["Research - Semantic Search"])


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


# ── Static routes (MUST come before parametric routes) ──────────────


@router.post(
    "/research/search",
    response_model=SearchResultResponse,
)
async def semantic_search(
    body: SearchRequest,
    session: AsyncSession = Depends(get_session),
    user_id: str | None = Depends(get_optional_user),
):
    """Perform semantic search across indexed documents.

    Applies the query text as a real filter (substring match on chunk text
    and title). When GOOGLE_API_KEY is configured and matching documents
    carry a stored embedding, results are additionally re-ranked by cosine
    similarity against a fresh query embedding.
    """
    start = datetime.now(timezone.utc)
    stmt = select(SearchDocument)

    if body.document_types:
        stmt = stmt.where(SearchDocument.source_type.in_(body.document_types))

    query_text = (body.query or "").strip()
    if query_text:
        like = f"%{query_text}%"
        stmt = stmt.where(
            or_(
                SearchDocument.chunk_text.ilike(like),
                SearchDocument.title.ilike(like),
            )
        )

    embedding_client = get_embedding_client()
    scores: dict[uuid.UUID, float | None] = {}
    rows: list[SearchDocument]
    query_embedding: list[float] | None = None
    if query_text and embedding_client.is_configured:
        try:
            query_embedding = (
                await asyncio.to_thread(embedding_client.embed_for_query, query_text)
            ).embedding
        except Exception:
            query_embedding = None

    if query_embedding is not None:
        vector_literal = "[" + ",".join(str(float(x)) for x in query_embedding) + "]"
        distance = SearchDocument.embedding_vector.op("<=>")(text(f"'{vector_literal}'::vector"))
        stmt = stmt.where(SearchDocument.embedding_vector.isnot(None)).order_by(distance).limit(body.limit)
        vector_stmt = stmt.add_columns(distance.label("distance"))
        result = await session.execute(vector_stmt)
        pairs = list(result.all())
        rows = [row for row, _distance in pairs]
        for row, dist in pairs:
            scores[row.id] = max(0.0, 1.0 - float(dist or 0.0))
    else:
        stmt = stmt.order_by(SearchDocument.created_at.desc().nulls_last()).limit(body.limit)
        result = await session.execute(stmt)
        rows = list(result.scalars().all())
        scores = {row.id: None for row in rows}

    rows = rows[: body.limit]
    top_score = next((scores[r.id] for r in rows if scores[r.id] is not None), None)
    execution_time_ms = int((datetime.now(timezone.utc) - start).total_seconds() * 1000)

    # Record query
    query_record = SearchQuery(
        id=uuid.uuid4(),
        user_id=user_id,
        query_text=body.query,
        result_count=len(rows),
        top_result_relevance=round(top_score, 4) if top_score is not None else None,
        execution_time_ms=execution_time_ms,
    )
    session.add(query_record)
    await session.commit()

    return SearchResultResponse(
        query=body.query,
        total_results=len(rows),
        results=[
            SearchChunkResponse(
                document_id=row.id,
                source_type=row.source_type,
                source_id=row.source_id,
                title=row.title,
                author=row.author,
                publish_date=row.publish_date,
                entity_id=row.entity_id,
                chunk_index=row.chunk_index,
                chunk_text=row.chunk_text,
                relevance_score=scores[row.id],
            )
            for row in rows
        ],
        execution_time_ms=execution_time_ms,
    )


@router.get(
    "/research/search/history",
    response_model=list[SearchHistoryResponse],
)
async def get_search_history(
    limit: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
    user_id: str | None = Depends(get_optional_user),
):
    """Get search query history for a user."""
    if user_id is None:
        raise HTTPException(status_code=401, detail="Authentication required for search history")
    result = await session.execute(
        select(SearchQuery)
        .where(SearchQuery.user_id == user_id)
        .order_by(SearchQuery.created_at.desc().nulls_last())
        .limit(limit)
    )
    rows = result.scalars().all()

    return [
        SearchHistoryResponse(
            id=row.id,
            user_id=row.user_id,
            query_text=row.query_text,
            result_count=row.result_count,
            execution_time_ms=row.execution_time_ms,
            created_at=row.created_at,
        )
        for row in rows
    ]


@router.get(
    "/research/search/suggested",
    response_model=list[SuggestedQueryResponse],
)
async def get_suggested_queries(
    session: AsyncSession = Depends(get_session),
):
    """Get AI-suggested search queries based on trending topics."""
    # Static suggestions for now (to be replaced by AI engine)
    return [
        SuggestedQueryResponse(query="Q4 earnings surprises", category="earnings", relevance_score=0.95),
        SuggestedQueryResponse(query="Fed rate decision impact", category="macro", relevance_score=0.90),
        SuggestedQueryResponse(query="AI semiconductor demand", category="sector", relevance_score=0.88),
    ]


@router.get(
    "/research/search/documents/stats",
    response_model=DocumentStatsResponse,
)
async def get_document_stats(
    session: AsyncSession = Depends(get_session),
):
    """Get index statistics for the document store."""
    total_result = await session.execute(
        select(func.count()).select_from(SearchDocument)
    )
    total_chunks = total_result.scalar() or 0

    type_result = await session.execute(
        select(SearchDocument.source_type, func.count())
        .group_by(SearchDocument.source_type)
    )
    type_counts = {row[0]: row[1] for row in type_result.all()}

    # Distinct document count by source_id
    distinct_result = await session.execute(
        select(func.count(func.distinct(SearchDocument.source_id)))
        .select_from(SearchDocument)
    )
    total_documents = distinct_result.scalar() or 0

    return DocumentStatsResponse(
        total_documents=total_documents,
        total_chunks=total_chunks,
        source_type_counts=type_counts,
        last_indexed_at=None,
    )


@router.post(
    "/research/search/index",
    response_model=IndexDocumentResponse,
)
async def index_document(
    body: IndexDocumentRequest,
    session: AsyncSession = Depends(get_session),
):
    """Index a new document for semantic search.

    If a chunk doesn't already carry an ``embedding``, one is generated
    server-side (when GOOGLE_API_KEY is configured) so semantic_search()
    has something real to rank against.
    """
    embedding_client = get_embedding_client()
    chunk_count = 0
    for i, chunk in enumerate(body.chunks):
        text = chunk.get("text", "")
        embedding_vector = chunk.get("embedding")
        embedding_model = chunk.get("embedding_model")
        if embedding_vector is None and text and embedding_client.is_configured:
            try:
                embedded = await asyncio.to_thread(embedding_client.embed_text, text)
                embedding_vector = embedded.embedding
                embedding_model = embedded.model
            except Exception:
                embedding_vector = None

        doc = SearchDocument(
            id=uuid.uuid4(),
            source_type=body.source_type,
            source_id=body.source_id,
            title=body.title,
            author=body.author,
            publish_date=body.publish_date,
            entity_id=body.entity_id,
            chunk_index=i,
            chunk_text=text,
            chunk_token_count=chunk.get("token_count"),
            embedding_model=embedding_model,
            embedding_vector=embedding_vector,
            metadata_=chunk.get("metadata"),
        )
        session.add(doc)
        chunk_count += 1

    await session.commit()

    return IndexDocumentResponse(
        document_count=1,
        chunk_count=chunk_count,
        source_type=body.source_type,
        status="INDEXED",
    )


@router.get(
    "/research/search/trending",
    response_model=list[TrendingTopicResponse],
)
async def get_trending_topics(
    limit: int = Query(default=10, ge=1, le=50),
    session: AsyncSession = Depends(get_session),
):
    """Get trending search topics based on recent query volume."""
    # Aggregate by query_text
    result = await session.execute(
        select(SearchQuery.query_text, func.count().label("cnt"))
        .group_by(SearchQuery.query_text)
        .order_by(func.count().desc())
        .limit(limit)
    )
    rows = result.all()

    return [
        TrendingTopicResponse(
            topic=row[0],
            query_count=row[1],
            trend_direction="UP",
        )
        for row in rows
    ]


# ── Parametric routes ───────────────────────────────────────────────


@router.get(
    "/research/search/documents/{source_id}",
    response_model=list[SearchChunkResponse],
)
async def get_document_chunks(
    source_id: str,
    session: AsyncSession = Depends(get_session),
):
    """Get all chunks for a specific source document."""
    result = await session.execute(
        select(SearchDocument)
        .where(SearchDocument.source_id == source_id)
        .order_by(SearchDocument.chunk_index)
    )
    rows = result.scalars().all()

    return [
        SearchChunkResponse(
            document_id=row.id,
            source_type=row.source_type,
            source_id=row.source_id,
            title=row.title,
            author=row.author,
            publish_date=row.publish_date,
            entity_id=row.entity_id,
            chunk_index=row.chunk_index,
            chunk_text=row.chunk_text,
            relevance_score=None,
        )
        for row in rows
    ]


@router.get(
    "/research/search/entities/{entity_id}",
    response_model=list[SearchChunkResponse],
)
async def get_entity_documents(
    entity_id: uuid.UUID,
    limit: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
):
    """Get documents indexed for a specific entity."""
    result = await session.execute(
        select(SearchDocument)
        .where(SearchDocument.entity_id == entity_id)
        .order_by(SearchDocument.created_at.desc().nulls_last())
        .limit(limit)
    )
    rows = result.scalars().all()

    return [
        SearchChunkResponse(
            document_id=row.id,
            source_type=row.source_type,
            source_id=row.source_id,
            title=row.title,
            author=row.author,
            publish_date=row.publish_date,
            entity_id=row.entity_id,
            chunk_index=row.chunk_index,
            chunk_text=row.chunk_text,
            relevance_score=None,
        )
        for row in rows
    ]
