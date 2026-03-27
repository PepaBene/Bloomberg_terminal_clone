"""Analyst Q&A API endpoints (Pillar 3 Phase 4B)."""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_session
from src.models.analyst_qa import QASession, QAFeedback
from src.schemas.analyst_qa_schema import (
    QAFeedbackRequest,
    QAFeedbackResponse,
    QAHistoryResponse,
    QAPopularResponse,
    QARequest,
    QAResponse,
    QAStatsResponse,
)

router = APIRouter(tags=["Research - Analyst Q&A"])


def _float(val):
    return float(val) if val is not None else None


def _qa_response(row: QASession) -> QAResponse:
    return QAResponse(
        id=row.id,
        user_id=row.user_id,
        entity_id=row.entity_id,
        question=row.question,
        answer_text=row.answer_text,
        answer_type=row.answer_type,
        confidence_level=_float(row.confidence_level),
        confidence_narrative=row.confidence_narrative,
        sources=row.sources,
        supporting_data=row.supporting_data,
        follow_up_suggestions=row.follow_up_suggestions,
        data_completeness=row.data_completeness,
        execution_time_ms=row.execution_time_ms,
        created_at=row.created_at,
    )


# ── Static routes (MUST come before parametric routes) ──────────────


@router.post(
    "/research/qa/ask",
    response_model=QAResponse,
)
async def ask_question(
    body: QARequest,
    session: AsyncSession = Depends(get_session),
):
    """Ask a question to the AI analyst Q&A engine."""
    qa = QASession(
        id=uuid.uuid4(),
        user_id=body.user_id,
        entity_id=body.entity_id,
        question=body.question,
        answer_text="AI-generated answer placeholder.",
        answer_type="AI_GENERATED",
        sources=body.context,
        follow_up_suggestions={"suggestions": ["What are the key risks?", "Compare with peers"]},
        execution_time_ms=0,
    )
    session.add(qa)
    await session.flush()

    return _qa_response(qa)


@router.get(
    "/research/qa/history",
    response_model=list[QAHistoryResponse],
)
async def get_qa_history(
    user_id: str = Query(default="default_user"),
    limit: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
):
    """Get Q&A history for a user."""
    result = await session.execute(
        select(QASession)
        .where(QASession.user_id == user_id)
        .order_by(QASession.created_at.desc().nullslast())
        .limit(limit)
    )
    rows = result.scalars().all()

    return [
        QAHistoryResponse(
            id=row.id,
            user_id=row.user_id,
            entity_id=row.entity_id,
            question=row.question,
            answer_type=row.answer_type,
            confidence_level=_float(row.confidence_level),
            user_rating=row.user_rating,
            created_at=row.created_at,
        )
        for row in rows
    ]


@router.get(
    "/research/qa/popular",
    response_model=list[QAPopularResponse],
)
async def get_popular_questions(
    limit: int = Query(default=10, ge=1, le=50),
    session: AsyncSession = Depends(get_session),
):
    """Get most popular questions."""
    result = await session.execute(
        select(QASession.question, func.count().label("cnt"))
        .group_by(QASession.question)
        .order_by(func.count().desc())
        .limit(limit)
    )
    rows = result.all()

    return [
        QAPopularResponse(
            question=row[0],
            ask_count=row[1],
            avg_confidence=None,
        )
        for row in rows
    ]


@router.get(
    "/research/qa/stats",
    response_model=QAStatsResponse,
)
async def get_qa_stats(
    session: AsyncSession = Depends(get_session),
):
    """Get Q&A usage statistics."""
    total_result = await session.execute(
        select(func.count()).select_from(QASession)
    )
    total = total_result.scalar() or 0

    feedback_result = await session.execute(
        select(func.count()).select_from(QAFeedback)
    )
    total_feedback = feedback_result.scalar() or 0

    type_result = await session.execute(
        select(QASession.answer_type, func.count())
        .group_by(QASession.answer_type)
    )
    type_counts = {row[0] or "UNKNOWN": row[1] for row in type_result.all()}

    return QAStatsResponse(
        total_questions=total,
        total_with_feedback=total_feedback,
        avg_confidence=None,
        avg_rating=None,
        answer_type_counts=type_counts,
    )


# ── Entity-scoped route ─────────────────────────────────────────────


@router.get(
    "/research/qa/by-entity/{entity_id}",
    response_model=list[QAHistoryResponse],
)
async def get_qa_by_entity(
    entity_id: uuid.UUID,
    limit: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
):
    """Get Q&A sessions related to a specific entity."""
    result = await session.execute(
        select(QASession)
        .where(QASession.entity_id == entity_id)
        .order_by(QASession.created_at.desc().nullslast())
        .limit(limit)
    )
    rows = result.scalars().all()

    return [
        QAHistoryResponse(
            id=row.id,
            user_id=row.user_id,
            entity_id=row.entity_id,
            question=row.question,
            answer_type=row.answer_type,
            confidence_level=_float(row.confidence_level),
            user_rating=row.user_rating,
            created_at=row.created_at,
        )
        for row in rows
    ]


# ── Session-scoped parametric routes ────────────────────────────────


@router.get(
    "/research/qa/{session_id}",
    response_model=QAResponse,
)
async def get_qa_session(
    session_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get a specific Q&A session by ID."""
    result = await session.execute(
        select(QASession).where(QASession.id == session_id)
    )
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Q&A session not found")

    return _qa_response(row)


@router.post(
    "/research/qa/{session_id}/feedback",
    response_model=QAFeedbackResponse,
)
async def submit_feedback(
    session_id: uuid.UUID,
    body: QAFeedbackRequest,
    session: AsyncSession = Depends(get_session),
):
    """Submit feedback for a Q&A session answer."""
    # Verify session exists
    qa_result = await session.execute(
        select(QASession).where(QASession.id == session_id)
    )
    qa_row = qa_result.scalar_one_or_none()
    if not qa_row:
        raise HTTPException(status_code=404, detail="Q&A session not found")

    feedback = QAFeedback(
        id=uuid.uuid4(),
        session_id=session_id,
        rating=body.rating,
        feedback_text=body.feedback_text,
        is_accurate=body.is_accurate,
    )
    session.add(feedback)

    # Also update user_rating on the session
    if body.rating is not None:
        qa_row.user_rating = body.rating

    await session.flush()

    return QAFeedbackResponse(
        id=feedback.id,
        session_id=feedback.session_id,
        rating=feedback.rating,
        feedback_text=feedback.feedback_text,
        is_accurate=feedback.is_accurate,
        created_at=feedback.created_at,
    )


@router.get(
    "/research/qa/{session_id}/follow-ups",
    response_model=dict,
)
async def get_follow_ups(
    session_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get suggested follow-up questions for a Q&A session."""
    result = await session.execute(
        select(QASession).where(QASession.id == session_id)
    )
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Q&A session not found")

    return {
        "session_id": str(row.id),
        "follow_up_suggestions": row.follow_up_suggestions,
    }
