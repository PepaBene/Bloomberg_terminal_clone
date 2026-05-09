"""Semantic Search API endpoints (Pillar 3 Phase 4B)."""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_session
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

router = APIRouter(tags=["Research - Semantic Search"])


# ── Static routes (MUST come before parametric routes) ──────────────


@router.post(
    "/research/search",
    response_model=SearchResultResponse,
)
async def semantic_search(
    body: SearchRequest,
    session: AsyncSession = Depends(get_session),
):
    """Perform semantic search across indexed documents."""
    stmt = select(SearchDocument).order_by(SearchDocument.created_at.desc().nulls_last())

    if body.document_types:
        stmt = stmt.where(SearchDocument.source_type.in_(body.document_types))

    stmt = stmt.limit(body.limit)
    result = await session.execute(stmt)
    rows = result.scalars().all()

    # Record query
    query_record = SearchQuery(
        id=uuid.uuid4(),
        user_id="default_user",
        query_text=body.query,
        result_count=len(rows),
        execution_time_ms=0,
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
                relevance_score=None,
            )
            for row in rows
        ],
        execution_time_ms=0,
    )


@router.get(
    "/research/search/history",
    response_model=list[SearchHistoryResponse],
)
async def get_search_history(
    user_id: str = Query(default="default_user"),
    limit: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
):
    """Get search query history for a user."""
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
    """Index a new document for semantic search."""
    chunk_count = 0
    for i, chunk in enumerate(body.chunks):
        doc = SearchDocument(
            id=uuid.uuid4(),
            source_type=body.source_type,
            source_id=body.source_id,
            title=body.title,
            author=body.author,
            publish_date=body.publish_date,
            entity_id=body.entity_id,
            chunk_index=i,
            chunk_text=chunk.get("text", ""),
            chunk_token_count=chunk.get("token_count"),
            embedding_model=chunk.get("embedding_model"),
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
