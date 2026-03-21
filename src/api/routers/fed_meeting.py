"""Central Bank Monitor (Fed) API endpoints (Pillar 1 Supplement – Part 2)."""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func as sa_func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_pagination, get_session
from src.api.utils.pagination import build_paginated_meta
from src.models.fed_meeting import FedMeeting
from src.schemas.common import PaginatedResponse, PaginationParams
from src.schemas.fed_meeting import FedMeetingResponse

router = APIRouter(tags=["Central Bank"])


@router.get(
    "/macro/central-bank/fed",
    response_model=FedMeetingResponse,
)
async def get_latest_fed_meeting(
    session: AsyncSession = Depends(get_session),
):
    """Return the most recent FOMC meeting."""
    query = (
        select(FedMeeting)
        .order_by(FedMeeting.meeting_date.desc())
        .limit(1)
    )
    result = await session.execute(query)
    meeting = result.scalar_one_or_none()
    if not meeting:
        raise HTTPException(status_code=404, detail="No Fed meeting data found")
    return FedMeetingResponse.model_validate(meeting)


@router.get(
    "/macro/central-bank/fed/meetings",
    response_model=PaginatedResponse,
)
async def list_fed_meetings(
    session: AsyncSession = Depends(get_session),
    pagination: PaginationParams = Depends(get_pagination),
    start: date | None = Query(None, description="Start date"),
    end: date | None = Query(None, description="End date"),
    decision: str | None = Query(None, description="Filter by rate decision (HIKE, CUT, HOLD)"),
):
    """List FOMC meetings with optional date/decision filters."""
    query = select(FedMeeting)
    count_query = select(FedMeeting)

    if start:
        query = query.where(FedMeeting.meeting_date >= start)
        count_query = count_query.where(FedMeeting.meeting_date >= start)
    if end:
        query = query.where(FedMeeting.meeting_date <= end)
        count_query = count_query.where(FedMeeting.meeting_date <= end)
    if decision:
        query = query.where(FedMeeting.rate_decision == decision.upper())
        count_query = count_query.where(FedMeeting.rate_decision == decision.upper())

    total_result = await session.execute(
        select(sa_func.count()).select_from(count_query.subquery())
    )
    total_count = total_result.scalar_one()

    offset = (pagination.page - 1) * pagination.page_size
    query = (
        query.order_by(FedMeeting.meeting_date.desc())
        .offset(offset)
        .limit(pagination.page_size)
    )
    result = await session.execute(query)
    meetings = result.scalars().all()

    return PaginatedResponse(
        data=[FedMeetingResponse.model_validate(m) for m in meetings],
        meta=build_paginated_meta(total_count, pagination),
    )
