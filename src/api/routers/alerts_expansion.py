"""Alert Expansion API endpoints (Pillar 3 Phase 3C)."""

import uuid
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_session
from src.models.fi_intelligence import (
    CrossAssetSignal,
    FIMarketBriefing,
    NewIssuanceEvent,
)
from src.models.alert_expansion import FIAlertConfig
from src.models.governance_intelligence import GovernanceAssessment
from src.schemas.alert_expansion import (
    FallenAngelResponse,
    FIAlertConfigCreateRequest,
    FIAlertConfigResponse,
    FIRatingChangeResponse,
    FlowAlertResponse,
    QualityAlertResponse,
    SpreadMoveResponse,
)

router = APIRouter(tags=["Alert Expansion"])


# ══════════════════════════════════════════════════════════════════════
# FI Rating & Credit Alerts
# ══════════════════════════════════════════════════════════════════════


@router.get(
    "/alerts/fi/ratings",
    response_model=list[FIRatingChangeResponse],
)
async def get_fi_rating_changes(
    session: AsyncSession = Depends(get_session),
):
    """Get recent credit rating change alerts."""
    # Derive rating changes from issuance events with different ratings
    result = await session.execute(
        select(NewIssuanceEvent)
        .where(NewIssuanceEvent.rating.isnot(None))
        .order_by(NewIssuanceEvent.issue_date.desc())
        .limit(20)
    )
    rows = result.scalars().all()
    return [
        FIRatingChangeResponse(
            entity_id=row.entity_id,
            agency="COMPOSITE",
            new_rating=row.rating,
            event_date=row.issue_date,
        )
        for row in rows
    ]


@router.get(
    "/alerts/fi/fallen-angels",
    response_model=list[FallenAngelResponse],
)
async def get_fallen_angel_alerts(
    session: AsyncSession = Depends(get_session),
):
    """Get fallen angel event alerts (IG to HY downgrades)."""
    result = await session.execute(
        select(FIMarketBriefing)
        .where(FIMarketBriefing.fallen_angels_this_period.isnot(None))
        .order_by(FIMarketBriefing.briefing_date.desc())
        .limit(20)
    )
    rows = result.scalars().all()
    alerts: list[FallenAngelResponse] = []
    for row in rows:
        fa_data = row.fallen_angels_this_period or {}
        alerts.append(FallenAngelResponse(
            entity_name=fa_data.get("entity_name"),
            agency=fa_data.get("agency"),
            old_rating=fa_data.get("old_rating"),
            new_rating=fa_data.get("new_rating"),
            event_date=row.briefing_date,
            spread_impact_bps=fa_data.get("spread_impact_bps"),
        ))
    return alerts


@router.get(
    "/alerts/fi/rising-stars",
    response_model=list[FIRatingChangeResponse],
)
async def get_rising_star_alerts(
    session: AsyncSession = Depends(get_session),
):
    """Get rising star event alerts (HY to IG upgrades)."""
    result = await session.execute(
        select(FIMarketBriefing)
        .where(FIMarketBriefing.rising_stars_this_period.isnot(None))
        .order_by(FIMarketBriefing.briefing_date.desc())
        .limit(20)
    )
    rows = result.scalars().all()
    alerts: list[FIRatingChangeResponse] = []
    for row in rows:
        rs_data = row.rising_stars_this_period or {}
        alerts.append(FIRatingChangeResponse(
            entity_name=rs_data.get("entity_name"),
            agency=rs_data.get("agency"),
            old_rating=rs_data.get("old_rating"),
            new_rating=rs_data.get("new_rating"),
            direction="UPGRADE",
            event_date=row.briefing_date,
            is_rising_star=True,
        ))
    return alerts


@router.get(
    "/alerts/fi/spread-moves",
    response_model=list[SpreadMoveResponse],
)
async def get_spread_move_alerts(
    session: AsyncSession = Depends(get_session),
):
    """Get large spread move alerts for today."""
    result = await session.execute(
        select(FIMarketBriefing)
        .order_by(FIMarketBriefing.briefing_date.desc())
        .limit(10)
    )
    rows = result.scalars().all()
    alerts: list[SpreadMoveResponse] = []
    for row in rows:
        if row.ig_oas_1w_change is not None:
            severity = "LOW"
            change_val = float(row.ig_oas_1w_change)
            if abs(change_val) > 20:
                severity = "HIGH"
            elif abs(change_val) > 10:
                severity = "MEDIUM"
            alerts.append(SpreadMoveResponse(
                spread_bps=float(row.ig_oas_bps) if row.ig_oas_bps is not None else None,
                spread_change_bps=change_val,
                as_of_date=row.briefing_date,
                severity=severity,
            ))
    return alerts


@router.get(
    "/alerts/fi/regime",
    response_model=list[SpreadMoveResponse],
)
async def get_regime_alerts(
    session: AsyncSession = Depends(get_session),
):
    """Get credit spread regime status alerts."""
    result = await session.execute(
        select(FIMarketBriefing)
        .where(FIMarketBriefing.credit_regime.isnot(None))
        .order_by(FIMarketBriefing.briefing_date.desc())
        .limit(10)
    )
    rows = result.scalars().all()
    # R-016: Map credit_regime classifications to a HIGH/MEDIUM/LOW severity
    # (instead of using the raw regime value) so the response field carries a
    # value the schema actually represents.
    _REGIME_TO_SEVERITY = {
        "TIGHT": "HIGH",
        "WIDE": "HIGH",
        "STRESSED": "HIGH",
        "ELEVATED": "MEDIUM",
        "NORMAL": "MEDIUM",
        "LOOSE": "LOW",
    }
    return [
        SpreadMoveResponse(
            spread_bps=float(row.ig_oas_bps) if row.ig_oas_bps is not None else None,
            spread_change_bps=float(row.ig_oas_1w_change) if row.ig_oas_1w_change is not None else None,
            as_of_date=row.briefing_date,
            severity=_REGIME_TO_SEVERITY.get((row.credit_regime or "").upper(), "MEDIUM"),
        )
        for row in rows
    ]


@router.get(
    "/alerts/fi/divergence",
    response_model=list[SpreadMoveResponse],
)
async def get_divergence_alerts(
    session: AsyncSession = Depends(get_session),
):
    """Get active bond-equity divergence signal alerts."""
    result = await session.execute(
        select(CrossAssetSignal)
        .where(CrossAssetSignal.signal_type.in_(["DIVERGENCE", "BOND_EQUITY_DIVERGENCE"]))
        .order_by(CrossAssetSignal.signal_date.desc())
        .limit(20)
    )
    rows = result.scalars().all()
    return [
        SpreadMoveResponse(
            entity_id=row.entity_id,
            spread_change_bps=float(row.spread_change_bps) if row.spread_change_bps is not None else None,
            as_of_date=row.signal_date,
            severity=row.severity,
        )
        for row in rows
    ]


def _scope_uuid(scope: dict | None) -> uuid.UUID | None:
    """Return the configured entity UUID or None — never a random UUID
    that would appear to point at a real but non-existent entity."""
    if not scope:
        return None
    raw = scope.get("entity_id")
    if not raw:
        return None
    try:
        return uuid.UUID(str(raw))
    except (ValueError, TypeError):
        return None


@router.get(
    "/alerts/quality-scores",
    response_model=list[QualityAlertResponse],
)
async def get_quality_score_alerts(
    session: AsyncSession = Depends(get_session),
):
    """Get fired quality-score alert events.

    Evaluates each enabled QUALITY_SCORE alert config against the entity's
    actual latest governance (composite quality) score and emits an alert
    ONLY when the real score has fallen below the configured threshold.
    Previously this repackaged every config as a fired alert with a
    hardcoded MEDIUM severity and current_score set to the *trigger
    threshold* rather than any measured score.
    """
    configs = (
        await session.execute(
            select(FIAlertConfig)
            .where(
                FIAlertConfig.alert_type == "QUALITY_SCORE",
                FIAlertConfig.is_enabled == True,  # noqa: E712
            )
            .limit(200)
        )
    ).scalars().all()

    alerts: list[QualityAlertResponse] = []
    for cfg in configs:
        entity_id = _scope_uuid(cfg.entity_scope)
        if entity_id is None or cfg.threshold_value is None:
            continue
        threshold = float(cfg.threshold_value)

        assessment = (
            await session.execute(
                select(GovernanceAssessment)
                .where(GovernanceAssessment.entity_id == entity_id)
                .order_by(GovernanceAssessment.assessment_date.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if assessment is None or assessment.governance_score is None:
            # No measured score to evaluate — do not fabricate a breach.
            continue

        current = float(assessment.governance_score)
        if current >= threshold:
            continue  # not breached

        shortfall = threshold - current
        if shortfall >= 20:
            severity = "HIGH"
        elif shortfall >= 10:
            severity = "MEDIUM"
        else:
            severity = "LOW"

        alerts.append(QualityAlertResponse(
            entity_id=entity_id,
            alert_type=cfg.alert_type,
            severity=severity,
            current_score=round(current, 2),
            change=round(current - threshold, 2),
            triggered_at=datetime.combine(assessment.assessment_date, datetime.min.time()).replace(tzinfo=timezone.utc),
        ))

    return alerts


@router.get(
    "/alerts/institutional-flow",
    response_model=list[FlowAlertResponse],
)
async def get_institutional_flow_alerts(
    session: AsyncSession = Depends(get_session),
):
    """Get fired institutional-flow alert events.

    Evaluates each enabled INSTITUTIONAL_FLOW config against a *measured*
    net flow (recorded on the config's ``entity_scope`` as ``net_flow_mm``
    by the flow-signal pipeline) and emits an alert ONLY when the observed
    absolute flow meets/exceeds the configured threshold. Previously it
    repackaged every config as a fired alert with ``volume_mm`` set to the
    *trigger threshold* rather than any observed volume.

    NOTE: production institutional-flow signals (the never-batchable E6
    engine, see the analytics audit) don't populate a flow table in a fresh
    deployment, so with no measured ``net_flow_mm`` on scope this correctly
    returns empty instead of inventing volumes from thresholds.
    """
    configs = (
        await session.execute(
            select(FIAlertConfig)
            .where(
                FIAlertConfig.alert_type == "INSTITUTIONAL_FLOW",
                FIAlertConfig.is_enabled == True,  # noqa: E712
            )
            .limit(200)
        )
    ).scalars().all()

    alerts: list[FlowAlertResponse] = []
    for cfg in configs:
        scope = cfg.entity_scope or {}
        measured = scope.get("net_flow_mm", scope.get("net_flow"))
        if measured is None or cfg.threshold_value is None:
            continue
        try:
            net_flow = float(measured)
        except (TypeError, ValueError):
            continue

        threshold = float(cfg.threshold_value)
        if abs(net_flow) < threshold:
            continue  # observed flow doesn't breach the configured limit

        alerts.append(FlowAlertResponse(
            entity_id=_scope_uuid(scope),
            alert_type=cfg.alert_type,
            direction="INFLOW" if net_flow > 0 else "OUTFLOW",
            volume_mm=round(net_flow, 2),
        ))

    return alerts
