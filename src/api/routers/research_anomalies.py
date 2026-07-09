"""Research Anomaly Detection API endpoints (Pillar 3 Phase 4A)."""

import statistics
import uuid
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_session
from src.models.entity import Entity
from src.models.anomaly_detection import DetectedAnomaly, AnomalyRule
from src.models.security import EODPrice, Security
from src.schemas.anomaly_detection_schema import (
    AnomalyListResponse,
    AnomalyResponse,
    AnomalyRuleCreateRequest,
    AnomalyRuleResponse,
)

router = APIRouter(tags=["Research - Anomaly Detection"])

_SCAN_LOOKBACK_DAYS = 120
_DEFAULT_Z_THRESHOLD = 2.5
_MIN_OBSERVATIONS = 20


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
    await session.commit()

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
    await session.commit()

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
    await session.commit()

    return _rule_response(rule)


async def _z_threshold(session: AsyncSession, anomaly_type: str) -> float:
    """Look up the configured z-score threshold for an anomaly type, if any."""
    rule = (
        await session.execute(
            select(AnomalyRule)
            .where(AnomalyRule.anomaly_type == anomaly_type, AnomalyRule.is_enabled == True)
            .limit(1)
        )
    ).scalar_one_or_none()
    if rule and rule.threshold_config:
        threshold = rule.threshold_config.get("z_score_threshold")
        if threshold is not None:
            return float(threshold)
    return _DEFAULT_Z_THRESHOLD


def _severity_from_z(z: float, threshold: float) -> float:
    """Map a z-score (relative to its trigger threshold) onto a 0-100 severity scale."""
    ratio = min(abs(z) / threshold, 3.0) if threshold else 1.0
    return round(min(50.0 + ratio * 25.0, 100.0), 2)


async def _detect_price_volume_anomalies(
    session: AsyncSession, entity_id: uuid.UUID
) -> list[DetectedAnomaly]:
    """Real statistical scan: flag today's return/volume as anomalous if it's
    an outlier (z-score) versus its own trailing distribution."""
    sec_row = (
        await session.execute(
            select(Security.security_id, Security.security_type, Security.status)
            .where(Security.issuer_entity_id == entity_id, Security.asset_class == "EQUITY")
        )
    ).all()
    if not sec_row:
        return []
    sec_row.sort(key=lambda r: (r[2] != "ACTIVE", r[1] != "COMMON_STOCK"))
    security_id = sec_row[0][0]

    cutoff = date.today() - timedelta(days=_SCAN_LOOKBACK_DAYS)
    rows = (
        await session.execute(
            select(EODPrice.price_date, EODPrice.close, EODPrice.volume)
            .where(EODPrice.security_id == security_id, EODPrice.price_date >= cutoff)
            .order_by(EODPrice.price_date.asc())
        )
    ).all()
    if len(rows) < _MIN_OBSERVATIONS:
        return []

    detected: list[DetectedAnomaly] = []
    latest_date = rows[-1][0]

    closes = [float(r[1]) for r in rows if r[1] is not None]
    if len(closes) >= _MIN_OBSERVATIONS + 1:
        returns = [
            (closes[i] - closes[i - 1]) / closes[i - 1]
            for i in range(1, len(closes))
            if closes[i - 1] > 0
        ]
        history, latest_return = returns[:-1], returns[-1]
        mean_r, std_r = statistics.mean(history), statistics.pstdev(history)
        if std_r > 0:
            z = (latest_return - mean_r) / std_r
            threshold = await _z_threshold(session, "PRICE_MOVE")
            if abs(z) >= threshold:
                detected.append(DetectedAnomaly(
                    id=uuid.uuid4(),
                    entity_id=entity_id,
                    anomaly_type="PRICE_MOVE",
                    severity_score=_severity_from_z(z, threshold),
                    anomaly_window_start=latest_date,
                    anomaly_window_end=latest_date,
                    lookback_period=f"{len(history)}D",
                    observed_value=round(latest_return * 100, 4),
                    expected_value=round(mean_r * 100, 4),
                    z_score=round(z, 4),
                    related_data={"security_id": str(security_id), "metric": "daily_return_pct"},
                    confidence_level=min(abs(z) / (threshold * 2), 1.0),
                ))

    volumes = [int(r[2]) for r in rows if r[2] is not None]
    if len(volumes) >= _MIN_OBSERVATIONS + 1:
        history, latest_volume = volumes[:-1], volumes[-1]
        mean_v, std_v = statistics.mean(history), statistics.pstdev(history)
        if std_v > 0:
            z = (latest_volume - mean_v) / std_v
            threshold = await _z_threshold(session, "VOLUME_SPIKE")
            if abs(z) >= threshold:
                detected.append(DetectedAnomaly(
                    id=uuid.uuid4(),
                    entity_id=entity_id,
                    anomaly_type="VOLUME_SPIKE",
                    severity_score=_severity_from_z(z, threshold),
                    anomaly_window_start=latest_date,
                    anomaly_window_end=latest_date,
                    lookback_period=f"{len(history)}D",
                    observed_value=latest_volume,
                    expected_value=round(mean_v, 2),
                    z_score=round(z, 4),
                    related_data={"security_id": str(security_id), "metric": "volume"},
                    confidence_level=min(abs(z) / (threshold * 2), 1.0),
                ))

    return detected


@router.post(
    "/research/anomalies/scan/{entity_id}",
    response_model=dict,
)
async def trigger_anomaly_scan(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Run a real anomaly scan for an entity against price/volume history.

    Persists any newly detected anomalies (skipping ones already recorded
    for the same window) and reports what was actually found — this used
    to be a pure no-op that always replied "INITIATED" without scanning
    anything.
    """
    await _get_entity(session, entity_id)

    candidates = await _detect_price_volume_anomalies(session, entity_id)

    inserted = []
    for candidate in candidates:
        existing = await session.execute(
            select(DetectedAnomaly).where(
                DetectedAnomaly.entity_id == entity_id,
                DetectedAnomaly.anomaly_type == candidate.anomaly_type,
                DetectedAnomaly.anomaly_window_start == candidate.anomaly_window_start,
            )
        )
        if existing.scalar_one_or_none() is not None:
            continue
        session.add(candidate)
        inserted.append(candidate)

    if inserted:
        await session.commit()

    return {
        "entity_id": str(entity_id),
        "scan_status": "COMPLETED",
        "anomalies_detected": len(inserted),
        "anomaly_types": [a.anomaly_type for a in inserted],
    }
