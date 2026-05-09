"""Research Notes API endpoints (Pillar 4 Phase 4)."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
import sqlalchemy as sa
from sqlalchemy import select, func, desc, or_
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_optional_user, get_session
from src.models.research_notes import ResearchNote
from src.schemas.research_notes import (
    ResearchNoteCreateRequest,
    ResearchNoteListResponse,
    ResearchNoteResponse,
    ResearchNoteUpdateRequest,
)

router = APIRouter(tags=["Research Notes"])

# Anonymous fallback when no Bearer token is present and REQUIRE_AUTH is off.
ANONYMOUS_USER = "anonymous"


def _resolve_user(user: str | None) -> str:
    return user or ANONYMOUS_USER


def _note_to_response(note: ResearchNote) -> ResearchNoteResponse:
    return ResearchNoteResponse(
        id=note.id,
        user_id=note.user_id,
        title=note.title,
        content=note.content,
        note_type=note.note_type,
        entity_id=note.entity_id,
        portfolio_id=note.portfolio_id,
        security_id=note.security_id,
        ticker=note.ticker,
        tags=note.tags,
        sentiment=note.sentiment,
        priority=note.priority,
        is_pinned=note.is_pinned,
        is_archived=note.is_archived,
        attachments=note.attachments,
        created_at=note.created_at,
        updated_at=note.updated_at,
    )


@router.post("/research/notes", response_model=ResearchNoteResponse, status_code=201)
async def create_note(
    body: ResearchNoteCreateRequest,
    session: AsyncSession = Depends(get_session),
    user: str | None = Depends(get_optional_user),
):
    """Create a new research note."""
    user_id = _resolve_user(user)
    note = ResearchNote(
        id=uuid.uuid4(),
        user_id=user_id,
        title=body.title,
        content=body.content,
        note_type=body.note_type,
        entity_id=body.entity_id,
        portfolio_id=body.portfolio_id,
        security_id=body.security_id,
        ticker=body.ticker,
        tags=body.tags,
        sentiment=body.sentiment,
        priority=body.priority,
    )
    session.add(note)
    await session.commit()
    await session.refresh(note)
    return _note_to_response(note)


@router.get("/research/notes", response_model=ResearchNoteListResponse)
async def list_notes(
    entity_id: str | None = Query(default=None),
    portfolio_id: uuid.UUID | None = Query(default=None),
    ticker: str | None = Query(default=None),
    note_type: str | None = Query(default=None),
    tag: str | None = Query(default=None),
    sentiment: str | None = Query(default=None),
    pinned_only: bool = Query(default=False),
    archived: bool = Query(default=False),
    search: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
    user: str | None = Depends(get_optional_user),
):
    """List research notes with filtering and full-text search."""
    user_id = _resolve_user(user)
    stmt = select(ResearchNote).where(
        ResearchNote.user_id == user_id,
        ResearchNote.is_archived == archived,
    )

    if entity_id:
        stmt = stmt.where(ResearchNote.entity_id == entity_id)
    if portfolio_id:
        stmt = stmt.where(ResearchNote.portfolio_id == portfolio_id)
    if ticker:
        stmt = stmt.where(ResearchNote.ticker == ticker.upper())
    if note_type:
        stmt = stmt.where(ResearchNote.note_type == note_type.upper())
    if tag:
        # JSONB contains check — works on PostgreSQL; on SQLite falls back to LIKE
        try:
            stmt = stmt.where(ResearchNote.tags.contains([tag]))
        except Exception:
            stmt = stmt.where(ResearchNote.tags.cast(sa.Text).contains(tag))
    if sentiment:
        stmt = stmt.where(ResearchNote.sentiment == sentiment.upper())
    if pinned_only:
        stmt = stmt.where(ResearchNote.is_pinned == True)
    if search:
        # Full-text search on PostgreSQL; simple LIKE fallback otherwise
        stmt = stmt.where(
            or_(
                ResearchNote.title.ilike(f"%{search}%"),
                ResearchNote.content.ilike(f"%{search}%"),
            )
        )

    # Count
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await session.execute(count_stmt)).scalar() or 0

    # Order: pinned first, then by updated_at desc
    stmt = stmt.order_by(
        desc(ResearchNote.is_pinned),
        desc(ResearchNote.updated_at),
    ).offset(offset).limit(limit)

    result = await session.execute(stmt)
    notes = result.scalars().all()

    return ResearchNoteListResponse(
        notes=[_note_to_response(n) for n in notes],
        total=total,
    )


@router.get("/research/notes/{note_id}", response_model=ResearchNoteResponse)
async def get_note(
    note_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get a research note by ID."""
    result = await session.execute(
        select(ResearchNote).where(ResearchNote.id == note_id)
    )
    note = result.scalar_one_or_none()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    return _note_to_response(note)


@router.put("/research/notes/{note_id}", response_model=ResearchNoteResponse)
async def update_note(
    note_id: uuid.UUID,
    body: ResearchNoteUpdateRequest,
    session: AsyncSession = Depends(get_session),
):
    """Update a research note."""
    result = await session.execute(
        select(ResearchNote).where(ResearchNote.id == note_id)
    )
    note = result.scalar_one_or_none()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")

    for field_name in (
        "title", "content", "note_type", "entity_id", "portfolio_id",
        "security_id", "ticker", "tags", "sentiment", "priority",
        "is_pinned", "is_archived",
    ):
        value = getattr(body, field_name, None)
        if value is not None:
            setattr(note, field_name, value)

    await session.commit()
    await session.refresh(note)
    return _note_to_response(note)


@router.delete("/research/notes/{note_id}", response_model=ResearchNoteResponse)
async def delete_note(
    note_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Soft-delete (archive) a research note."""
    result = await session.execute(
        select(ResearchNote).where(ResearchNote.id == note_id)
    )
    note = result.scalar_one_or_none()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    note.is_archived = True
    await session.commit()
    await session.refresh(note)
    return _note_to_response(note)


@router.get("/research/notes/entity/{entity_id}", response_model=ResearchNoteListResponse)
async def list_notes_by_entity(
    entity_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
    user: str | None = Depends(get_optional_user),
):
    """List all notes for a specific entity."""
    user_id = _resolve_user(user)
    stmt = (
        select(ResearchNote)
        .where(
            ResearchNote.user_id == user_id,
            ResearchNote.entity_id == entity_id,
            ResearchNote.is_archived == False,
        )
        .order_by(desc(ResearchNote.is_pinned), desc(ResearchNote.updated_at))
        .limit(limit)
    )
    count_result = await session.execute(
        select(func.count(ResearchNote.id)).where(
            ResearchNote.user_id == user_id,
            ResearchNote.entity_id == entity_id,
            ResearchNote.is_archived == False,
        )
    )
    total = count_result.scalar() or 0

    result = await session.execute(stmt)
    notes = result.scalars().all()
    return ResearchNoteListResponse(
        notes=[_note_to_response(n) for n in notes],
        total=total,
    )


@router.get("/research/notes/tags", response_model=list[str])
async def list_tags(
    session: AsyncSession = Depends(get_session),
    user: str | None = Depends(get_optional_user),
):
    """List all unique tags used in research notes."""
    user_id = _resolve_user(user)
    result = await session.execute(
        select(ResearchNote.tags)
        .where(
            ResearchNote.user_id == user_id,
            ResearchNote.is_archived == False,
            ResearchNote.tags.is_not(None),
        )
    )
    # Flatten tag lists from all notes and deduplicate
    all_tags: set[str] = set()
    for row in result.scalars().all():
        if isinstance(row, list):
            all_tags.update(row)
    return sorted(all_tags)
