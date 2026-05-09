"""Investment Thesis API endpoints (Pillar 3 Phase 4B)."""

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_session
from src.models.entity import Entity
from src.models.investment_thesis import InvestmentThesis, ThesisVersion
from src.schemas.investment_thesis_schema import (
    ThesisCreateRequest,
    ThesisDiffResponse,
    ThesisElevatorPitchResponse,
    ThesisListResponse,
    ThesisQualityReportResponse,
    ThesisResponse,
    ThesisSlideOutlineResponse,
    ThesisUpdateRequest,
    ThesisVersionResponse,
)

router = APIRouter(tags=["Research - Investment Thesis"])


def _float(val):
    return float(val) if val is not None else None


async def _get_entity(session: AsyncSession, entity_id: uuid.UUID) -> Entity:
    result = await session.execute(
        select(Entity).where(Entity.entity_id == entity_id)
    )
    entity = result.scalar_one_or_none()
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
    return entity


def _thesis_response(row: InvestmentThesis) -> ThesisResponse:
    return ThesisResponse(
        id=row.id,
        entity_id=row.entity_id,
        analyst_id=row.analyst_id,
        version=row.version,
        thesis_title=row.thesis_title,
        investment_horizon=row.investment_horizon,
        conviction_level=row.conviction_level,
        executive_summary=row.executive_summary,
        key_drivers=row.key_drivers,
        primary_risks=row.primary_risks,
        valuation_scenarios=row.valuation_scenarios,
        catalysts=row.catalysts,
        quality_metrics=row.quality_metrics,
        elevator_pitch=row.elevator_pitch,
        slide_outline=row.slide_outline,
        ai_enabled=row.ai_enabled,
        created_at=getattr(row, "created_at", None),
        updated_at=getattr(row, "updated_at", None),
    )


def _thesis_list_response(row: InvestmentThesis) -> ThesisListResponse:
    return ThesisListResponse(
        id=row.id,
        entity_id=row.entity_id,
        analyst_id=row.analyst_id,
        version=row.version,
        thesis_title=row.thesis_title,
        conviction_level=row.conviction_level,
        executive_summary=row.executive_summary,
        created_at=getattr(row, "created_at", None),
        updated_at=getattr(row, "updated_at", None),
    )


# ── Static routes (MUST come before parametric routes) ──────────────


@router.get(
    "/research/thesis/recent",
    response_model=list[ThesisListResponse],
)
async def get_recent_theses(
    limit: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
):
    """Recently generated theses across all entities."""
    result = await session.execute(
        select(InvestmentThesis)
        .order_by(InvestmentThesis.created_at.desc().nulls_last())
        .limit(limit)
    )
    rows = result.scalars().all()
    return [_thesis_list_response(row) for row in rows]


@router.get(
    "/research/thesis/quality-report",
    response_model=ThesisQualityReportResponse,
)
async def get_quality_report(
    session: AsyncSession = Depends(get_session),
):
    """Get overall thesis quality report."""
    total_result = await session.execute(
        select(func.count()).select_from(InvestmentThesis)
    )
    total = total_result.scalar() or 0

    conviction_result = await session.execute(
        select(InvestmentThesis.conviction_level, func.count())
        .group_by(InvestmentThesis.conviction_level)
    )
    by_conviction = {row[0] or "UNSET": row[1] for row in conviction_result.all()}

    horizon_result = await session.execute(
        select(InvestmentThesis.investment_horizon, func.count())
        .group_by(InvestmentThesis.investment_horizon)
    )
    by_horizon = {row[0] or "UNSET": row[1] for row in horizon_result.all()}

    return ThesisQualityReportResponse(
        total_theses=total,
        avg_quality_score=None,
        by_conviction=by_conviction,
        by_horizon=by_horizon,
    )


@router.get(
    "/research/thesis/by-conviction/{level}",
    response_model=list[ThesisListResponse],
)
async def get_theses_by_conviction(
    level: str,
    limit: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
):
    """Get theses filtered by conviction level."""
    result = await session.execute(
        select(InvestmentThesis)
        .where(InvestmentThesis.conviction_level == level)
        .order_by(InvestmentThesis.created_at.desc().nulls_last())
        .limit(limit)
    )
    rows = result.scalars().all()
    return [_thesis_list_response(row) for row in rows]


@router.get(
    "/research/thesis/by-analyst/{analyst_id}",
    response_model=list[ThesisListResponse],
)
async def get_theses_by_analyst(
    analyst_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
):
    """Get theses written by a specific analyst."""
    result = await session.execute(
        select(InvestmentThesis)
        .where(InvestmentThesis.analyst_id == analyst_id)
        .order_by(InvestmentThesis.created_at.desc().nulls_last())
        .limit(limit)
    )
    rows = result.scalars().all()
    return [_thesis_list_response(row) for row in rows]


# ── Entity-scoped routes ────────────────────────────────────────────


@router.post(
    "/research/thesis/{entity_id}",
    response_model=ThesisResponse,
)
async def generate_thesis(
    entity_id: uuid.UUID,
    body: ThesisCreateRequest,
    session: AsyncSession = Depends(get_session),
):
    """Generate a new investment thesis for an entity."""
    await _get_entity(session, entity_id)

    # Determine next version
    version_result = await session.execute(
        select(func.max(InvestmentThesis.version))
        .where(InvestmentThesis.entity_id == entity_id)
    )
    max_version = version_result.scalar() or 0

    thesis = InvestmentThesis(
        id=uuid.uuid4(),
        entity_id=entity_id,
        analyst_id=body.analyst_id,
        version=max_version + 1,
        thesis_title=body.thesis_title,
        investment_horizon=body.investment_horizon,
        conviction_level=body.conviction_level,
        executive_summary=body.executive_summary,
        key_drivers=body.key_drivers,
        primary_risks=body.primary_risks,
        valuation_scenarios=body.valuation_scenarios,
        catalysts=body.catalysts,
        ai_enabled=False,
    )
    session.add(thesis)
    await session.commit()

    return _thesis_response(thesis)


@router.get(
    "/research/thesis/{entity_id}/latest",
    response_model=ThesisResponse,
)
async def get_latest_thesis(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get the latest investment thesis for an entity."""
    await _get_entity(session, entity_id)

    result = await session.execute(
        select(InvestmentThesis)
        .where(InvestmentThesis.entity_id == entity_id)
        .order_by(InvestmentThesis.version.desc())
        .limit(1)
    )
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="No thesis found for this entity")

    return _thesis_response(row)


@router.get(
    "/research/thesis/{entity_id}/versions",
    response_model=list[ThesisListResponse],
)
async def get_thesis_versions(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get version history of theses for an entity."""
    await _get_entity(session, entity_id)

    result = await session.execute(
        select(InvestmentThesis)
        .where(InvestmentThesis.entity_id == entity_id)
        .order_by(InvestmentThesis.version.desc())
    )
    rows = result.scalars().all()
    return [_thesis_list_response(row) for row in rows]


# ── Thesis-ID-scoped routes ─────────────────────────────────────────


@router.get(
    "/research/thesis/{thesis_id}/detail",
    response_model=ThesisResponse,
)
async def get_thesis_detail(
    thesis_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get a specific thesis by ID (use /detail to avoid path collision)."""
    result = await session.execute(
        select(InvestmentThesis)
        .where(InvestmentThesis.id == thesis_id)
    )
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Thesis not found")

    return _thesis_response(row)


@router.put(
    "/research/thesis/{thesis_id}/update",
    response_model=ThesisResponse,
)
async def update_thesis(
    thesis_id: uuid.UUID,
    body: ThesisUpdateRequest,
    session: AsyncSession = Depends(get_session),
):
    """Update an existing thesis and create a version snapshot."""
    result = await session.execute(
        select(InvestmentThesis)
        .where(InvestmentThesis.id == thesis_id)
    )
    thesis = result.scalar_one_or_none()
    if not thesis:
        raise HTTPException(status_code=404, detail="Thesis not found")

    # Snapshot for diff
    version_snapshot = ThesisVersion(
        id=uuid.uuid4(),
        thesis_id=thesis.id,
        version=thesis.version,
        updated_drivers=body.key_drivers,
        analyst_note=body.analyst_note,
    )
    session.add(version_snapshot)

    # Apply updates
    if body.conviction_level is not None:
        thesis.conviction_level = body.conviction_level
    if body.executive_summary is not None:
        thesis.executive_summary = body.executive_summary
    if body.key_drivers is not None:
        thesis.key_drivers = body.key_drivers
    if body.primary_risks is not None:
        thesis.primary_risks = body.primary_risks
    if body.valuation_scenarios is not None:
        thesis.valuation_scenarios = body.valuation_scenarios
    if body.catalysts is not None:
        thesis.catalysts = body.catalysts

    thesis.version = thesis.version + 1
    await session.commit()
    await session.refresh(thesis)

    return _thesis_response(thesis)


@router.get(
    "/research/thesis/{thesis_id}/diff",
    response_model=ThesisDiffResponse,
)
async def get_thesis_diff(
    thesis_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get diff between current thesis and previous version."""
    result = await session.execute(
        select(InvestmentThesis)
        .where(InvestmentThesis.id == thesis_id)
    )
    thesis = result.scalar_one_or_none()
    if not thesis:
        raise HTTPException(status_code=404, detail="Thesis not found")

    version_result = await session.execute(
        select(ThesisVersion)
        .where(ThesisVersion.thesis_id == thesis_id)
        .order_by(ThesisVersion.version.desc())
        .limit(1)
    )
    version = version_result.scalar_one_or_none()

    return ThesisDiffResponse(
        thesis_id=thesis.id,
        current_version=thesis.version,
        previous_version=version.version if version else None,
        conviction_change=_float(version.conviction_change) if version else None,
        updated_drivers=version.updated_drivers if version else None,
        analyst_note=version.analyst_note if version else None,
    )


@router.get(
    "/research/thesis/{thesis_id}/slides",
    response_model=ThesisSlideOutlineResponse,
)
async def get_thesis_slides(
    thesis_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get slide outline for a thesis presentation."""
    result = await session.execute(
        select(InvestmentThesis)
        .where(InvestmentThesis.id == thesis_id)
    )
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Thesis not found")

    return ThesisSlideOutlineResponse(
        thesis_id=row.id,
        thesis_title=row.thesis_title,
        slide_outline=row.slide_outline,
    )


@router.get(
    "/research/thesis/{thesis_id}/elevator",
    response_model=ThesisElevatorPitchResponse,
)
async def get_thesis_elevator_pitch(
    thesis_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get elevator pitch for a thesis."""
    result = await session.execute(
        select(InvestmentThesis)
        .where(InvestmentThesis.id == thesis_id)
    )
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Thesis not found")

    return ThesisElevatorPitchResponse(
        thesis_id=row.id,
        thesis_title=row.thesis_title,
        elevator_pitch=row.elevator_pitch,
    )
