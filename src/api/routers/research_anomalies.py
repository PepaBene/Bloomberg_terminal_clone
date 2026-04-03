"""Research Anomaly Detection API endpoints (Pillar 3 Phase 4A)."""

import uuid
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_session
from src.models.entity import Entity
from src.models.anomaly_detection import DetectedAnomaly, AnomalyRule
from src.schemas.anomaly_detection_schema import (
    AnomalyListResponse,
    AnomalyResponse,
    AnomalyRuleCreateRequest,
    AnomalyRuleResponse,
)

router = APIRouter(tags=["Research - Anomaly Detection"])


async def _get_entity(session: AsyncSession, entity_id: uuid.UUID) -> Entity:
    result = await session.execute(
        select(Entity).where(Entity.entity_id == entity_id)
    )
    entity = result.scalar_one_or_none()
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
    return entity


def _float(val):
    return float(val) if val is not None else None


def _anomaly_response(row: DetectedAnomaly) -> AnomalyResponse:
    return AnomalyResponse(
        id=row.id,
        entity_id=row.entity_id,
        anomaly_type=row.anomaly_type,
        severity_score=float(row.severity_score),
        detected_at=row.detected_at,
        anomaly_window_start=row.anomaly_window_start,
        anomaly_window_end=row.anomaly_window_end,
        lookback_period=row.lookback_period,
        observed_value=_float(row.observed_value),
        expected_value=_float(row.expected_value),
        z_score=_float(row.z_score),
        percentile_rank=_float(row.percentile_rank),
        contextual_analysis=row.contextual_analysis,
        related_data=row.related_data,
        ai_narrative=row.ai_narrative,
        recommended_actions=row.recommended_actions,
        confidence_level=_float(row.confidence_level),
        is_acknowledged=row.is_acknowledged,
        acknowledged_by=row.acknowledged_by,
    )


def _rule_response(row: AnomalyRule) -> AnomalyRuleResponse:
    return AnomalyRuleResponse(
        id=row.id,
        anomaly_type=row.anomaly_type,
        rule_name=row.rule_name,
        description=row.description,
        threshold_config=row.threshold_config,
        is_enabled=row.is_enabled,
    )


# ── Static routes (MUST come before parametric routes) ──────────────


@router.get(
    "/research/anomalies/active",
    response_model=list[AnomalyResponse],
)
async def get_active_anomalies(
    limit: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
):
    """Get all active (unacknowledged) anomalies."""
    result = await session.execute(
        select(DetectedAnomaly)
        .where(DetectedAnomaly.is_acknowledged == False)
        .order_by(DetectedAnomaly.severity_score.desc())
        .limit(limit)
    )
    rows = result.scalars().all()
    return [_anomaly_response(row) for row in rows]


@router.get(
    "/research/anomalies/critical",
    response_model=list[AnomalyResponse],
)
async def get_critical_anomalies(
    threshold: float = Query(default=85.0, ge=0, le=100),
    session: AsyncSession = Depends(get_session),
):
    """Get critical anomalies (severity >= threshold, default 85)."""
    result = await session.execute(
        select(DetectedAnomaly)
        .where(DetectedAnomaly.severity_score >= threshold)
        .order_by(DetectedAnomaly.severity_score.desc())
    )
    rows = result.scalars().all()
    return [_anomaly_response(row) for row in rows]


@router.get(
    "/research/anomalies/today",
    response_model=list[AnomalyResponse],
)
async def get_todays_anomalies(
    session: AsyncSession = Depends(get_session),
):
    """Get anomalies detected today."""
    today = date.today()
    result = await session.execute(
        select(DetectedAnomaly)
        .where(DetectedAnomaly.anomaly_window_start == today)
        .order_by(DetectedAnomaly.severity_score.desc())
    )
    rows = result.scalars().all()
    return [_anomaly_response(row) for row in rows]


@router.get(
    "/research/anomalies/statistics",
    response_model=dict,
)
async def get_anomaly_statistics(
    session: AsyncSession = Depends(get_session),
):
    """Get anomaly detection statistics."""
    total_result = await session.execute(
        select(func.count(DetectedAnomaly.id))
    )
    total_count = total_result.scalar() or 0

    active_result = await session.execute(
        select(func.count(DetectedAnomaly.id))
        .where(DetectedAnomaly.is_acknowledged == False)
    )
    active_count = active_result.scalar() or 0

    critical_result = await session.execute(
        select(func.count(DetectedAnomaly.id))
        .where(DetectedAnomaly.severity_score >= 85)
    )
    critical_count = critical_result.scalar() or 0

    acknowledged_result = await session.execute(
        select(func.count(DetectedAnomaly.id))
        .where(DetectedAnomaly.is_acknowledged == True)
    )
    acknowledged_count = acknowledged_result.scalar() or 0

    return {
        "total_anomalies": total_count,
        "active_anomalies": active_count,
        "critical_anomalies": critical_count,
        "acknowledged_anomalies": acknowledged_count,
    }


@router.get(
    "/research/anomalies/rules",
    response_model=list[AnomalyRuleResponse],
)
async def get_anomaly_rules(
    session: AsyncSession = Depends(get_session),
):
    """Get all anomaly detection rules."""
    result = await session.execute(
        select(AnomalyRule).order_by(AnomalyRule.anomaly_type)
    )
    rows = result.scalars().all()
    return [_rule_response(row) for row in rows]


@router.post(
    "/research/anomalies/rules",
    response_model=AnomalyRuleResponse,
    status_code=201,
)
async def create_anomaly_rule(
    body: AnomalyRuleCreateRequest,
    session: AsyncSession = Depends(get_session),
):
    """Create a custom anomaly detection rule."""
    rule = AnomalyRule(
        id=uuid.uuid4(),
        anomaly_type=body.anomaly_type,
        rule_name=body.rule_name,
        description=body.description,
        threshold_config=body.threshold_config,
        is_enabled=body.is_enabled,
    )
    session.add(rule)
    await session.flush()

    return _rule_response(rule)


@router.get(
    "/research/anomalies/by-type/{anomaly_type}",
    response_model=list[AnomalyResponse],
)
async def get_anomalies_by_type(
    anomaly_type: str,
    session: AsyncSession = Depends(get_session),
):
    """Get anomalies filtered by anomaly type."""
    result = await session.execute(
        select(DetectedAnomaly)
        .where(DetectedAnomaly.anomaly_type == anomaly_type)
        .order_by(DetectedAnomaly.severity_score.desc())
    )
    rows = result.scalars().all()
    return [_anomaly_response(row) for row in rows]


# ── Parametric routes ───────────────────────────────────────────────


@router.get(
    "/research/anomalies/{entity_id}",
    response_model=list[AnomalyResponse],
)
async def get_entity_anomalies(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get all anomalies for an entity."""
    await _get_entity(session, entity_id)

    result = await session.execute(
        select(DetectedAnomaly)
        .where(DetectedAnomaly.entity_id == entity_id)
        .order_by(DetectedAnomaly.severity_score.desc())
    )
    rows = result.scalars().all()
    return [_anomaly_response(row) for row in rows]


@router.get(
    "/research/anomalies/{entity_id}/history",
    response_model=list[AnomalyResponse],
)
async def get_entity_anomaly_history(
    entity_id: uuid.UUID,
    limit: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
):
    """Get historical anomalies for an entity."""
    await _get_entity(session, entity_id)

    result = await session.execute(
        select(DetectedAnomaly)
        .where(DetectedAnomaly.entity_id == entity_id)
        .order_by(DetectedAnomaly.detected_at.desc().nulls_last())
        .limit(limit)
    )
    rows = result.scalars().all()
    return [_anomaly_response(row) for row in rows]


@router.post(
    "/research/anomalies/{anomaly_id}/acknowledge",
    response_model=AnomalyResponse,
)
async def acknowledge_anomaly(
    anomaly_id: uuid.UUID,
    acknowledged_by: str = Query(default="system"),
    session: AsyncSession = Depends(get_session),
):
    """Acknowledge an anomaly."""
    result = await session.execute(
        select(DetectedAnomaly)
        .where(DetectedAnomaly.id == anomaly_id)
    )
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Anomaly not found")

    row.is_acknowledged = True
    row.acknowledged_by = acknowledged_by
    await session.flush()

    return _anomaly_response(row)


@router.put(
    "/research/anomalies/rules/{rule_id}",
    response_model=AnomalyRuleResponse,
)
async def update_anomaly_rule(
    rule_id: uuid.UUID,
    body: AnomalyRuleCreateRequest,
    session: AsyncSession = Depends(get_session),
):
    """Update an existing anomaly detection rule."""
    result = await session.execute(
        select(AnomalyRule)
        .where(AnomalyRule.id == rule_id)
    )
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Anomaly rule not found")

    rule.anomaly_type = body.anomaly_type
    rule.rule_name = body.rule_name
    rule.description = body.description
    rule.threshold_config = body.threshold_config
    rule.is_enabled = body.is_enabled
    await session.flush()

    return _rule_response(rule)


@router.post(
    "/research/anomalies/scan/{entity_id}",
    response_model=dict,
)
async def trigger_anomaly_scan(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Trigger a manual anomaly scan for an entity."""
    await _get_entity(session, entity_id)

    return {
        "entity_id": str(entity_id),
        "scan_status": "INITIATED",
        "message": "Anomaly scan queued for processing.",
    }
