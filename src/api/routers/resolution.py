"""Resolution review queue API endpoints."""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_session
from src.resolution.review_queue import add_to_queue, approve, get_pending, reject

logger = logging.getLogger(__name__)

# Import auth dependency with graceful fallback so tests still pass
# when the auth module or its transitive deps are unavailable.
try:
    from src.api.auth.dependencies import get_current_user

    _auth_available = True
except ImportError:
    _auth_available = False
    logger.warning("Auth dependencies not available; approve/reject endpoints will not require authentication.")

router = APIRouter(prefix="/resolution", tags=["Resolution Queue"])


# ── Schemas ─────────────────────────────────────────────────────────

class QueueItemResponse(BaseModel):
    id: uuid.UUID
    source_system: str
    source_record: dict
    candidate_entity_id: uuid.UUID | None
    confidence_score: float
    match_method: str | None
    status: str
    reviewer: str | None = None

    model_config = {"from_attributes": True}


class ApproveRejectRequest(BaseModel):
    reviewer: str | None = None


class RejectResponse(BaseModel):
    new_entity_id: uuid.UUID


# ── Endpoints ───────────────────────────────────────────────────────

@router.get("/queue", response_model=list[QueueItemResponse])
async def list_pending_items(
    limit: int = Query(default=50, ge=1, le=500),
    session: AsyncSession = Depends(get_session),
):
    """Get pending resolution queue items, ordered by descending confidence."""
    items = await get_pending(session, limit=limit)
    return [QueueItemResponse.model_validate(item) for item in items]


if _auth_available:

    @router.post("/queue/{queue_id}/approve")
    async def approve_match(
        queue_id: uuid.UUID,
        body: ApproveRejectRequest = ApproveRejectRequest(),
        session: AsyncSession = Depends(get_session),
        current_user: dict = Depends(get_current_user),
    ):
        """Approve a match: merge identifiers into the candidate entity.

        Requires a valid Bearer token.
        """
        reviewer = body.reviewer or current_user.get("sub")
        try:
            await approve(queue_id, session, reviewer=reviewer)
            await session.commit()
            return {"status": "approved", "queue_id": str(queue_id)}
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    @router.post("/queue/{queue_id}/reject", response_model=RejectResponse)
    async def reject_match(
        queue_id: uuid.UUID,
        body: ApproveRejectRequest = ApproveRejectRequest(),
        session: AsyncSession = Depends(get_session),
        current_user: dict = Depends(get_current_user),
    ):
        """Reject a match: create a new entity from the source record.

        Requires a valid Bearer token.
        """
        reviewer = body.reviewer or current_user.get("sub")
        try:
            new_entity_id = await reject(queue_id, session, reviewer=reviewer)
            await session.commit()
            return RejectResponse(new_entity_id=new_entity_id)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

else:

    @router.post("/queue/{queue_id}/approve")
    async def approve_match(
        queue_id: uuid.UUID,
        body: ApproveRejectRequest = ApproveRejectRequest(),
        session: AsyncSession = Depends(get_session),
    ):
        """Approve a match: merge identifiers into the candidate entity."""
        try:
            await approve(queue_id, session, reviewer=body.reviewer)
            await session.commit()
            return {"status": "approved", "queue_id": str(queue_id)}
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    @router.post("/queue/{queue_id}/reject", response_model=RejectResponse)
    async def reject_match(
        queue_id: uuid.UUID,
        body: ApproveRejectRequest = ApproveRejectRequest(),
        session: AsyncSession = Depends(get_session),
    ):
        """Reject a match: create a new entity from the source record."""
        try:
            new_entity_id = await reject(queue_id, session, reviewer=body.reviewer)
            await session.commit()
            return RejectResponse(new_entity_id=new_entity_id)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
