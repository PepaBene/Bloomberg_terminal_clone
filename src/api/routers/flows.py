"""Pillar 2: Institutional Flow Analytics API (E6).

Endpoints for institution profiles, security-level flow analysis,
market-level aggregations, and flow alerts.
"""

from __future__ import annotations

import logging
import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_session
from src.models.flows import FlowAlert, InstitutionalFlowSignal, InstitutionAnalytics
from src.models.ownership import (
    InstitutionalHolding,
    InstitutionProfile,
    OwnershipSummary,
    ShortInterest,
)
from src.models.entity import Entity
from src.models.security import Security
from src.schemas.flows import (
    FlowAlertResponse,
    FlowHistoryPoint,
    FlowHistoryResponse,
    FlowSummaryResponse,
    HoldingChangeResponse,
    HoldingResponse,
    InstitutionDetailResponse,
    InstitutionHistoryPoint,
    InstitutionHistoryResponse,
    MarketFlowResponse,
    SectorFlowResponse,
    SecurityHolderResponse,
    ShortInterestDetailResponse,
    SmartMoneyResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v2/analytics", tags=["Institutional Flows"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _resolve_security(session: AsyncSession, security_id: uuid.UUID) -> Security:
    result = await session.execute(
        select(Security).where(Security.security_id == security_id)
    )
    sec = result.scalar_one_or_none()
    if sec is None:
        raise HTTPException(status_code=404, detail="Security not found")
    return sec


async def _resolve_institution(session: AsyncSession, institution_id: uuid.UUID) -> InstitutionProfile:
    result = await session.execute(
        select(InstitutionProfile).where(InstitutionProfile.institution_id == institution_id)
    )
    inst = result.scalar_one_or_none()
    if inst is None:
        raise HTTPException(status_code=404, detail="Institution not found")
    return inst


# ---------------------------------------------------------------------------
# Institution Profiles
# ---------------------------------------------------------------------------

@router.get("/institutions/{institution_id}", response_model=InstitutionDetailResponse)
async def get_institution(
    institution_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get institution profile with derived analytics."""
    inst = await _resolve_institution(session, institution_id)

    # Fetch latest analytics if available
    analytics_result = await session.execute(
        select(InstitutionAnalytics)
        .where(InstitutionAnalytics.institution_id == institution_id)
        .order_by(desc(InstitutionAnalytics.report_date))
        .limit(1)
    )
    analytics = analytics_result.scalar_one_or_none()

    return InstitutionDetailResponse(
        institution_id=inst.institution_id,
        institution_name=inst.institution_name,
        institution_type=inst.institution_type,
        tier=inst.tier,
        aum=float(inst.aum) if inst.aum is not None else None,
        number_of_holdings=inst.number_of_holdings,
        investment_style=analytics.investment_style if analytics else None,
        concentration_score=float(analytics.concentration_score) if analytics and analytics.concentration_score else None,
    )


@router.get("/institutions/{institution_id}/holdings", response_model=list[HoldingResponse])
async def get_institution_holdings(
    institution_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Current holdings for an institution (latest report date)."""
    await _resolve_institution(session, institution_id)

    # Find latest report_date
    date_result = await session.execute(
        select(func.max(InstitutionalHolding.report_date))
        .where(InstitutionalHolding.institution_id == institution_id)
    )
    latest_date = date_result.scalar_one_or_none()
    if latest_date is None:
        return []

    result = await session.execute(
        select(InstitutionalHolding)
        .where(
            InstitutionalHolding.institution_id == institution_id,
            InstitutionalHolding.report_date == latest_date,
        )
        .order_by(desc(InstitutionalHolding.market_value))
    )
    holdings = result.scalars().all()
    return [
        HoldingResponse(
            institution_id=institution_id,
            security_id=h.security_id,
            report_date=h.report_date,
            shares_held=float(h.shares_held) if h.shares_held else None,
            market_value=float(h.market_value) if h.market_value else None,
            percent_of_portfolio=float(h.percent_of_portfolio) if h.percent_of_portfolio else None,
            percent_of_outstanding=float(h.percent_of_outstanding) if h.percent_of_outstanding else None,
        )
        for h in holdings
    ]


@router.get("/institutions/{institution_id}/changes", response_model=list[HoldingChangeResponse])
async def get_institution_changes(
    institution_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Position changes for an institution (latest vs prior quarter)."""
    await _resolve_institution(session, institution_id)

    from src.engines.e6_institution_service import InstitutionService
    svc = InstitutionService()
    changes = await svc.get_changes(session, institution_id, quarters=2)
    return [HoldingChangeResponse(**c) for c in changes]


@router.get("/institutions/{institution_id}/history", response_model=InstitutionHistoryResponse)
async def get_institution_history(
    institution_id: uuid.UUID,
    periods: int = Query(default=8, le=20),
    session: AsyncSession = Depends(get_session),
):
    """Multi-quarter summary history for an institution."""
    inst = await _resolve_institution(session, institution_id)

    from src.engines.e6_institution_service import InstitutionService
    svc = InstitutionService()
    history = await svc.get_history(session, institution_id, periods=periods)
    return InstitutionHistoryResponse(
        institution_id=institution_id,
        institution_name=inst.institution_name,
        data_points=[InstitutionHistoryPoint(**h) for h in history],
    )


@router.get("/institutions/tiers/{tier}", response_model=list[InstitutionDetailResponse])
async def get_institutions_by_tier(
    tier: str,
    session: AsyncSession = Depends(get_session),
):
    """List institutions by tier (WHALE, MAJOR, NOTABLE, SMALL)."""
    result = await session.execute(
        select(InstitutionProfile)
        .where(InstitutionProfile.tier == tier.upper())
        .order_by(desc(InstitutionProfile.aum))
    )
    institutions = result.scalars().all()
    return [
        InstitutionDetailResponse(
            institution_id=i.institution_id,
            institution_name=i.institution_name,
            institution_type=i.institution_type,
            tier=i.tier,
            aum=float(i.aum) if i.aum else None,
            number_of_holdings=i.number_of_holdings,
        )
        for i in institutions
    ]


@router.get("/institutions/types/{inst_type}", response_model=list[InstitutionDetailResponse])
async def get_institutions_by_type(
    inst_type: str,
    session: AsyncSession = Depends(get_session),
):
    """List institutions by type (HEDGE_FUND, PASSIVE_INDEX, etc.)."""
    result = await session.execute(
        select(InstitutionProfile)
        .where(InstitutionProfile.institution_type == inst_type.upper())
        .order_by(desc(InstitutionProfile.aum))
    )
    institutions = result.scalars().all()
    return [
        InstitutionDetailResponse(
            institution_id=i.institution_id,
            institution_name=i.institution_name,
            institution_type=i.institution_type,
            tier=i.tier,
            aum=float(i.aum) if i.aum else None,
            number_of_holdings=i.number_of_holdings,
        )
        for i in institutions
    ]


# ---------------------------------------------------------------------------
# Market-Level Aggregations (static paths — must be registered before {security_id})
# ---------------------------------------------------------------------------

@router.get("/flows/market", response_model=MarketFlowResponse)
async def get_market_flows(session: AsyncSession = Depends(get_session)):
    """Market-wide institutional flow summary (latest quarter)."""
    date_result = await session.execute(
        select(func.max(InstitutionalFlowSignal.report_date))
    )
    latest_date = date_result.scalar_one_or_none()
    if latest_date is None:
        return MarketFlowResponse()

    result = await session.execute(
        select(
            func.sum(InstitutionalFlowSignal.new_positions_count),
            func.sum(InstitutionalFlowSignal.closed_positions_count),
            func.sum(InstitutionalFlowSignal.net_value_change),
            func.avg(InstitutionalFlowSignal.breadth_score),
        ).where(InstitutionalFlowSignal.report_date == latest_date)
    )
    row = result.one_or_none()
    if row is None:
        return MarketFlowResponse(report_date=latest_date)

    return MarketFlowResponse(
        report_date=latest_date,
        total_new_positions=int(row[0]) if row[0] else None,
        total_closed_positions=int(row[1]) if row[1] else None,
        net_institutional_flow=float(row[2]) if row[2] else None,
        breadth_score=float(row[3]) if row[3] else None,
    )


@router.get("/flows/sectors", response_model=list[SectorFlowResponse])
async def get_sector_flows(session: AsyncSession = Depends(get_session)):
    """Institutional flow aggregated by GICS sector."""
    date_result = await session.execute(
        select(func.max(InstitutionalFlowSignal.report_date))
    )
    latest_date = date_result.scalar_one_or_none()
    if latest_date is None:
        return []

    result = await session.execute(
        select(
            Entity.gics_sector,
            func.sum(InstitutionalFlowSignal.net_value_change),
            func.sum(InstitutionalFlowSignal.new_positions_count),
            func.sum(InstitutionalFlowSignal.closed_positions_count),
        )
        .join(Security, InstitutionalFlowSignal.security_id == Security.security_id)
        .join(Entity, Security.issuer_entity_id == Entity.entity_id)
        .where(InstitutionalFlowSignal.report_date == latest_date)
        .group_by(Entity.gics_sector)
    )
    rows = result.all()

    sector_names = {
        "10": "Energy", "15": "Materials", "20": "Industrials",
        "25": "Consumer Discretionary", "30": "Consumer Staples",
        "35": "Health Care", "40": "Financials", "45": "Information Technology",
        "50": "Communication Services", "55": "Utilities", "60": "Real Estate",
    }

    return [
        SectorFlowResponse(
            gics_sector=row[0] or "Unknown",
            sector_name=sector_names.get(row[0], "Unknown"),
            net_flow=float(row[1]) if row[1] else None,
            new_positions=int(row[2]) if row[2] else None,
            closed_positions=int(row[3]) if row[3] else None,
        )
        for row in rows
        if row[0] is not None
    ]


@router.get("/flows/smart-money", response_model=list[SmartMoneyResponse])
async def get_smart_money(
    limit: int = Query(default=20, le=100),
    session: AsyncSession = Depends(get_session),
):
    """Top securities by smart money (whale-tier) activity."""
    date_result = await session.execute(
        select(func.max(InstitutionalFlowSignal.report_date))
    )
    latest_date = date_result.scalar_one_or_none()
    if latest_date is None:
        return []

    result = await session.execute(
        select(InstitutionalFlowSignal)
        .where(
            InstitutionalFlowSignal.report_date == latest_date,
            InstitutionalFlowSignal.whale_net_value != None,  # noqa: E711
        )
        .order_by(desc(func.abs(InstitutionalFlowSignal.whale_net_value)))
        .limit(limit)
    )
    signals = result.scalars().all()

    return [
        SmartMoneyResponse(
            security_id=s.security_id,
            whale_net_shares=float(s.whale_net_shares) if s.whale_net_shares else None,
            whale_net_value=float(s.whale_net_value) if s.whale_net_value else None,
            smart_money_signal=(
                "BULLISH" if s.smart_money_flow and float(s.smart_money_flow) > 0.2
                else "BEARISH" if s.smart_money_flow and float(s.smart_money_flow) < -0.2
                else "NEUTRAL"
            ),
        )
        for s in signals
    ]


# ---------------------------------------------------------------------------
# Alerts (static paths — must be registered before {security_id})
# ---------------------------------------------------------------------------

@router.get("/flows/alerts/whale-moves", response_model=list[FlowAlertResponse])
async def get_whale_alerts(
    limit: int = Query(default=20, le=100),
    session: AsyncSession = Depends(get_session),
):
    """Large position changes by whale-tier institutions."""
    result = await session.execute(
        select(FlowAlert)
        .where(FlowAlert.alert_type == "WHALE_MOVE")
        .order_by(desc(FlowAlert.report_date))
        .limit(limit)
    )
    return [FlowAlertResponse.model_validate(a) for a in result.scalars().all()]


@router.get("/flows/alerts/activist", response_model=list[FlowAlertResponse])
async def get_activist_alerts(
    limit: int = Query(default=20, le=100),
    session: AsyncSession = Depends(get_session),
):
    """Activist filing alerts."""
    result = await session.execute(
        select(FlowAlert)
        .where(FlowAlert.alert_type == "ACTIVIST_FILING")
        .order_by(desc(FlowAlert.report_date))
        .limit(limit)
    )
    return [FlowAlertResponse.model_validate(a) for a in result.scalars().all()]


@router.get("/flows/alerts/new-positions", response_model=list[FlowAlertResponse])
async def get_new_position_alerts(
    limit: int = Query(default=20, le=100),
    session: AsyncSession = Depends(get_session),
):
    """Notable new positions by significant institutions."""
    result = await session.execute(
        select(FlowAlert)
        .where(FlowAlert.alert_type == "NEW_POSITION")
        .order_by(desc(FlowAlert.report_date))
        .limit(limit)
    )
    return [FlowAlertResponse.model_validate(a) for a in result.scalars().all()]


@router.get("/flows/alerts/exits", response_model=list[FlowAlertResponse])
async def get_exit_alerts(
    limit: int = Query(default=20, le=100),
    session: AsyncSession = Depends(get_session),
):
    """Full position exits by notable institutions."""
    result = await session.execute(
        select(FlowAlert)
        .where(FlowAlert.alert_type == "FULL_EXIT")
        .order_by(desc(FlowAlert.report_date))
        .limit(limit)
    )
    return [FlowAlertResponse.model_validate(a) for a in result.scalars().all()]


# ---------------------------------------------------------------------------
# Flow Screening (POST — no conflict with {security_id})
# ---------------------------------------------------------------------------

@router.post("/flows/screen", response_model=list[FlowSummaryResponse])
async def screen_flows(
    min_breadth: float | None = None,
    min_smart_money: float | None = None,
    flow_trend: str | None = None,
    squeeze_potential: str | None = None,
    limit: int = Query(default=50, le=200),
    session: AsyncSession = Depends(get_session),
):
    """Screen securities by institutional flow criteria."""
    date_result = await session.execute(
        select(func.max(InstitutionalFlowSignal.report_date))
    )
    latest_date = date_result.scalar_one_or_none()
    if latest_date is None:
        return []

    stmt = select(InstitutionalFlowSignal).where(
        InstitutionalFlowSignal.report_date == latest_date
    )
    if min_breadth is not None:
        stmt = stmt.where(InstitutionalFlowSignal.breadth_score >= min_breadth)
    if min_smart_money is not None:
        stmt = stmt.where(InstitutionalFlowSignal.smart_money_flow >= min_smart_money)
    if flow_trend is not None:
        stmt = stmt.where(InstitutionalFlowSignal.flow_trend_3q == flow_trend.upper())
    if squeeze_potential is not None:
        stmt = stmt.where(InstitutionalFlowSignal.squeeze_potential == squeeze_potential.upper())

    stmt = stmt.order_by(desc(InstitutionalFlowSignal.breadth_score)).limit(limit)
    result = await session.execute(stmt)
    signals = result.scalars().all()

    return [
        FlowSummaryResponse(
            security_id=s.security_id,
            report_date=s.report_date,
            new_positions=s.new_positions_count,
            closed_positions=s.closed_positions_count,
            increased_positions=s.increased_positions_count,
            decreased_positions=s.decreased_positions_count,
            net_shares_change=float(s.net_shares_change) if s.net_shares_change else None,
            net_value_change=float(s.net_value_change) if s.net_value_change else None,
            buy_sell_ratio=float(s.buy_sell_ratio) if s.buy_sell_ratio else None,
            breadth_score=float(s.breadth_score) if s.breadth_score else None,
            smart_money_flow=float(s.smart_money_flow) if s.smart_money_flow else None,
            flow_trend_3q=s.flow_trend_3q,
            squeeze_potential=s.squeeze_potential,
            data_quality=s.data_quality,
        )
        for s in signals
    ]


# ---------------------------------------------------------------------------
# Security-Level Flow Analysis (parameterized paths — after static routes)
# ---------------------------------------------------------------------------

@router.get("/flows/{security_id}", response_model=FlowSummaryResponse)
async def get_flow_summary(
    security_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Aggregated institutional flow analysis for a security."""
    sec = await _resolve_security(session, security_id)

    result = await session.execute(
        select(InstitutionalFlowSignal)
        .where(InstitutionalFlowSignal.security_id == security_id)
        .order_by(desc(InstitutionalFlowSignal.report_date))
        .limit(1)
    )
    signal = result.scalar_one_or_none()

    if signal is None:
        # Try computing on demand
        try:
            from src.engines.e6_flows import InstitutionalFlowEngine
            engine = InstitutionalFlowEngine()
            await engine.compute(session, security_id=security_id)
            result2 = await session.execute(
                select(InstitutionalFlowSignal)
                .where(InstitutionalFlowSignal.security_id == security_id)
                .order_by(desc(InstitutionalFlowSignal.report_date))
                .limit(1)
            )
            signal = result2.scalar_one_or_none()
        except Exception as exc:
            logger.error("Flow computation failed: %s", exc)

    if signal is None:
        raise HTTPException(status_code=404, detail="No institutional flow data available")

    return FlowSummaryResponse(
        security_id=security_id,
        report_date=signal.report_date,
        new_positions=signal.new_positions_count,
        closed_positions=signal.closed_positions_count,
        increased_positions=signal.increased_positions_count,
        decreased_positions=signal.decreased_positions_count,
        net_shares_change=float(signal.net_shares_change) if signal.net_shares_change else None,
        net_value_change=float(signal.net_value_change) if signal.net_value_change else None,
        buy_sell_ratio=float(signal.buy_sell_ratio) if signal.buy_sell_ratio else None,
        breadth_score=float(signal.breadth_score) if signal.breadth_score else None,
        conviction_score=float(signal.conviction_score) if signal.conviction_score else None,
        smart_money_flow=float(signal.smart_money_flow) if signal.smart_money_flow else None,
        flow_trend_3q=signal.flow_trend_3q,
        flow_trend_4q=signal.flow_trend_4q,
        squeeze_potential=signal.squeeze_potential,
        data_quality=signal.data_quality,
    )


@router.get("/flows/{security_id}/holders", response_model=list[SecurityHolderResponse])
async def get_security_holders(
    security_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Who owns this security (latest report date)."""
    await _resolve_security(session, security_id)

    # Find latest report_date for this security
    date_result = await session.execute(
        select(func.max(InstitutionalHolding.report_date))
        .where(InstitutionalHolding.security_id == security_id)
    )
    latest_date = date_result.scalar_one_or_none()
    if latest_date is None:
        return []

    result = await session.execute(
        select(InstitutionalHolding, InstitutionProfile)
        .join(InstitutionProfile, InstitutionalHolding.institution_id == InstitutionProfile.institution_id)
        .where(
            InstitutionalHolding.security_id == security_id,
            InstitutionalHolding.report_date == latest_date,
        )
        .order_by(desc(InstitutionalHolding.market_value))
    )
    rows = result.all()
    return [
        SecurityHolderResponse(
            institution_id=h.institution_id,
            institution_name=p.institution_name,
            institution_type=p.institution_type,
            tier=p.tier,
            shares_held=float(h.shares_held) if h.shares_held else None,
            market_value=float(h.market_value) if h.market_value else None,
            percent_of_portfolio=float(h.percent_of_portfolio) if h.percent_of_portfolio else None,
            percent_of_outstanding=float(h.percent_of_outstanding) if h.percent_of_outstanding else None,
            shares_change=float(h.shares_change) if h.shares_change else None,
        )
        for h, p in rows
    ]


@router.get("/flows/{security_id}/changes", response_model=list[HoldingChangeResponse])
async def get_security_holding_changes(
    security_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Position changes for a security this quarter."""
    await _resolve_security(session, security_id)

    # Get latest 2 report dates
    date_result = await session.execute(
        select(InstitutionalHolding.report_date)
        .where(InstitutionalHolding.security_id == security_id)
        .distinct()
        .order_by(desc(InstitutionalHolding.report_date))
        .limit(2)
    )
    dates = date_result.scalars().all()
    if len(dates) < 2:
        return []

    current_date, prior_date = dates[0], dates[1]

    # Fetch current and prior holdings
    cur_result = await session.execute(
        select(InstitutionalHolding, InstitutionProfile)
        .join(InstitutionProfile, InstitutionalHolding.institution_id == InstitutionProfile.institution_id)
        .where(
            InstitutionalHolding.security_id == security_id,
            InstitutionalHolding.report_date == current_date,
        )
    )
    current = {row[0].institution_id: (row[0], row[1]) for row in cur_result.all()}

    prior_result = await session.execute(
        select(InstitutionalHolding, InstitutionProfile)
        .join(InstitutionProfile, InstitutionalHolding.institution_id == InstitutionProfile.institution_id)
        .where(
            InstitutionalHolding.security_id == security_id,
            InstitutionalHolding.report_date == prior_date,
        )
    )
    prior = {row[0].institution_id: (row[0], row[1]) for row in prior_result.all()}

    changes = []
    # New positions
    for iid in set(current) - set(prior):
        h, p = current[iid]
        changes.append(HoldingChangeResponse(
            institution_id=iid, institution_name=p.institution_name,
            security_id=security_id, report_date=current_date,
            current_shares=float(h.shares_held) if h.shares_held else None,
            market_value=float(h.market_value) if h.market_value else None,
            change_type="NEW_POSITION",
        ))
    # Closed positions
    for iid in set(prior) - set(current):
        h, p = prior[iid]
        changes.append(HoldingChangeResponse(
            institution_id=iid, institution_name=p.institution_name,
            security_id=security_id, report_date=current_date,
            prior_shares=float(h.shares_held) if h.shares_held else None,
            change_type="CLOSED_POSITION",
        ))
    # Changed positions
    for iid in set(current) & set(prior):
        hc, p = current[iid]
        hp, _ = prior[iid]
        cur_shares = float(hc.shares_held) if hc.shares_held else 0
        pri_shares = float(hp.shares_held) if hp.shares_held else 0
        delta = cur_shares - pri_shares
        pct = delta / pri_shares if pri_shares != 0 else 0
        ctype = "INCREASED" if delta > 0 else "DECREASED" if delta < 0 else "UNCHANGED"
        if abs(pct) < 0.05:
            ctype = "UNCHANGED"
        changes.append(HoldingChangeResponse(
            institution_id=iid, institution_name=p.institution_name,
            security_id=security_id, report_date=current_date,
            prior_shares=pri_shares, current_shares=cur_shares,
            shares_change=delta, change_type=ctype,
            percent_change=pct,
            market_value=float(hc.market_value) if hc.market_value else None,
        ))

    return changes


@router.get("/flows/{security_id}/short-interest", response_model=ShortInterestDetailResponse)
async def get_short_interest(
    security_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Latest short interest data for a security."""
    await _resolve_security(session, security_id)

    result = await session.execute(
        select(ShortInterest)
        .where(ShortInterest.security_id == security_id)
        .order_by(desc(ShortInterest.settlement_date))
        .limit(1)
    )
    si = result.scalar_one_or_none()
    if si is None:
        raise HTTPException(status_code=404, detail="No short interest data available")

    spf = float(si.short_percent_float) if si.short_percent_float else 0
    squeeze = "HIGH" if spf > 0.20 else "MODERATE" if spf > 0.10 else "LOW"

    return ShortInterestDetailResponse(
        security_id=security_id,
        settlement_date=si.settlement_date,
        shares_short=float(si.shares_short) if si.shares_short else None,
        short_percent_float=float(si.short_percent_float) if si.short_percent_float else None,
        short_percent_outstanding=float(si.short_percent_outstanding) if si.short_percent_outstanding else None,
        days_to_cover=float(si.days_to_cover) if si.days_to_cover else None,
        squeeze_potential=squeeze,
    )


@router.get("/flows/{security_id}/history", response_model=FlowHistoryResponse)
async def get_flow_history(
    security_id: uuid.UUID,
    periods: int = Query(default=8, le=20),
    session: AsyncSession = Depends(get_session),
):
    """Multi-quarter institutional flow history for a security."""
    await _resolve_security(session, security_id)

    result = await session.execute(
        select(InstitutionalFlowSignal)
        .where(InstitutionalFlowSignal.security_id == security_id)
        .order_by(desc(InstitutionalFlowSignal.report_date))
        .limit(periods)
    )
    signals = result.scalars().all()

    return FlowHistoryResponse(
        security_id=security_id,
        data_points=[
            FlowHistoryPoint(
                report_date=s.report_date,
                net_shares_change=float(s.net_shares_change) if s.net_shares_change else None,
                breadth_score=float(s.breadth_score) if s.breadth_score else None,
                smart_money_flow=float(s.smart_money_flow) if s.smart_money_flow else None,
                holders_count=(s.new_positions_count or 0) + (s.increased_positions_count or 0) +
                              (s.decreased_positions_count or 0) + (s.unchanged_positions_count or 0),
            )
            for s in signals
        ],
    )
