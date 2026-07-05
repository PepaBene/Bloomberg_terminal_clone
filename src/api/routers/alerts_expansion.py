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
    # R-016: Map credit_regime to severity instead of using raw regime value
    _REGIME_TO_SEVERITY = {"TIGHT": "HIGH", "NORMAL": "MEDIUM", "LOOSE": "LOW"}
    return [
        SpreadMoveResponse(
            spread_bps=float(row.ig_oas_bps) if row.ig_oas_bps is not None else None,
            spread_change_bps=float(row.ig_oas_1w_change) if row.ig_oas_1w_change is not None else None,
            as_of_date=row.briefing_date,
            severity=_REGIME_TO_SEVERITY.get(row.credit_regime, "MEDIUM"),
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


@router.get(
    "/alerts/quality-scores",
    response_model=list[QualityAlertResponse],
)
async def get_quality_score_alerts(
    session: AsyncSession = Depends(get_session),
):
    """Get quality score change alert events."""
    # Quality alerts are derived from alert configs with quality type
    result = await session.execute(
        select(FIAlertConfig)
        .where(FIAlertConfig.alert_type == "QUALITY_SCORE")
        .limit(20)
    )
    rows = result.scalars().all()
    # R-017: Use None instead of random uuid4() when entity_id is missing
    return [
        QualityAlertResponse(
            entity_id=uuid.UUID(row.entity_scope.get("entity_id")) if row.entity_scope and row.entity_scope.get("entity_id") else None,
            alert_type=row.alert_type,
            severity="MEDIUM",
            current_score=float(row.threshold_value) if row.threshold_value is not None else None,
        )
        for row in rows
    ]


@router.get(
    "/alerts/institutional-flow",
    response_model=list[FlowAlertResponse],
)
async def get_institutional_flow_alerts(
    session: AsyncSession = Depends(get_session),
):
    """Get institutional flow alert events."""
    result = await session.execute(
        select(FIAlertConfig)
        .where(FIAlertConfig.alert_type == "INSTITUTIONAL_FLOW")
        .limit(20)
    )
    rows = result.scalars().all()
    # R-017: Use None instead of random uuid4() when entity_id is missing
    # R-018: Derive flow direction from actual flow data in entity_scope,
    # not from the threshold value (which is the alert trigger limit).
    alerts: list[FlowAlertResponse] = []
    for row in rows:
        entity_id_str = row.entity_scope.get("entity_id") if row.entity_scope else None
        scope = row.entity_scope or {}
        # Prefer actual flow_direction stored in entity_scope; fall back
        # to net_flow sign; only use threshold sign as last resort.
        if scope.get("flow_direction"):
            direction = scope["flow_direction"]
        elif scope.get("net_flow") is not None:
            direction = "INFLOW" if float(scope["net_flow"]) > 0 else "OUTFLOW"
        else:
            direction = "UNKNOWN"
        alerts.append(FlowAlertResponse(
            entity_id=uuid.UUID(entity_id_str) if entity_id_str else None,
            alert_type=row.alert_type,
            direction=direction,
            volume_mm=float(row.threshold_value) if row.threshold_value is not None else None,
        ))
    return alerts
