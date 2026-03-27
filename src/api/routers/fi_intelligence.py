"""Fixed Income Intelligence API endpoints (Pillar 3 Phase 3C)."""

import uuid
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_session
from src.models.entity import Entity
from src.models.fi_intelligence import (
    CrossAssetSignal,
    FIMarketBriefing,
    NewIssuanceEvent,
)
from src.schemas.fi_intelligence import (
    CreditMarketBriefingResponse,
    CrossAssetSignalResponse,
    FIDashboardResponse,
    IssuanceEventResponse,
    IssuanceWeekResponse,
    IssuerCreditProfileResponse,
    YieldCurveBriefingResponse,
)

router = APIRouter(tags=["Fixed Income Intelligence"])


# ── Helpers ──────────────────────────────────────────────────────────


async def _get_entity(session: AsyncSession, entity_id: uuid.UUID) -> Entity:
    result = await session.execute(
        select(Entity).where(Entity.entity_id == entity_id)
    )
    entity = result.scalar_one_or_none()
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
    return entity


# ══════════════════════════════════════════════════════════════════════
# Yield Curve Intelligence
# ══════════════════════════════════════════════════════════════════════


@router.get(
    "/fi/yield-curve/briefing",
    response_model=list[YieldCurveBriefingResponse],
)
async def get_yield_curve_briefing(
    session: AsyncSession = Depends(get_session),
):
    """Get the latest daily yield curve briefing."""
    result = await session.execute(
        select(FIMarketBriefing)
        .where(FIMarketBriefing.briefing_type.in_(["YIELD_CURVE", None]))
        .order_by(FIMarketBriefing.briefing_date.desc())
        .limit(5)
    )
    rows = result.scalars().all()
    return [
        YieldCurveBriefingResponse(
            id=row.id,
            briefing_date=row.briefing_date,
            spread_2s10s_bps=float(row.spread_2s10s_bps) if row.spread_2s10s_bps is not None else None,
            spread_3m10y_bps=float(row.spread_3m10y_bps) if row.spread_3m10y_bps is not None else None,
            curve_shape=row.curve_shape,
            narrative=row.narrative,
            ai_enabled=row.ai_enabled,
        )
        for row in rows
    ]


@router.get(
    "/fi/yield-curve/history",
    response_model=list[YieldCurveBriefingResponse],
)
async def get_yield_curve_history(
    days: int = Query(default=30, ge=1, le=365),
    session: AsyncSession = Depends(get_session),
):
    """Get historical yield curve briefings."""
    cutoff = date.today() - timedelta(days=days)
    result = await session.execute(
        select(FIMarketBriefing)
        .where(FIMarketBriefing.briefing_date >= cutoff)
        .order_by(FIMarketBriefing.briefing_date.desc())
        .limit(100)
    )
    rows = result.scalars().all()
    return [
        YieldCurveBriefingResponse(
            id=row.id,
            briefing_date=row.briefing_date,
            spread_2s10s_bps=float(row.spread_2s10s_bps) if row.spread_2s10s_bps is not None else None,
            spread_3m10y_bps=float(row.spread_3m10y_bps) if row.spread_3m10y_bps is not None else None,
            curve_shape=row.curve_shape,
            narrative=row.narrative,
            ai_enabled=row.ai_enabled,
        )
        for row in rows
    ]


@router.get(
    "/fi/yield-curve/auctions",
    response_model=list[YieldCurveBriefingResponse],
)
async def get_yield_curve_auctions(
    session: AsyncSession = Depends(get_session),
):
    """Get recent auction-related yield curve data."""
    result = await session.execute(
        select(FIMarketBriefing)
        .order_by(FIMarketBriefing.briefing_date.desc())
        .limit(10)
    )
    rows = result.scalars().all()
    return [
        YieldCurveBriefingResponse(
            id=row.id,
            briefing_date=row.briefing_date,
            spread_2s10s_bps=float(row.spread_2s10s_bps) if row.spread_2s10s_bps is not None else None,
            spread_3m10y_bps=float(row.spread_3m10y_bps) if row.spread_3m10y_bps is not None else None,
            curve_shape=row.curve_shape,
            narrative=row.narrative,
            ai_enabled=row.ai_enabled,
        )
        for row in rows
    ]


@router.get(
    "/fi/yield-curve/equity-impact",
    response_model=list[CrossAssetSignalResponse],
)
async def get_yield_curve_equity_impact(
    session: AsyncSession = Depends(get_session),
):
    """Get rate-sensitive equity sector impact signals."""
    result = await session.execute(
        select(CrossAssetSignal)
        .where(CrossAssetSignal.signal_type == "RATE_SENSITIVITY")
        .order_by(CrossAssetSignal.signal_date.desc())
        .limit(20)
    )
    rows = result.scalars().all()
    return [
        CrossAssetSignalResponse(
            id=row.id,
            entity_id=row.entity_id,
            signal_date=row.signal_date,
            signal_type=row.signal_type,
            equity_return_pct=float(row.equity_return_pct) if row.equity_return_pct is not None else None,
            spread_change_bps=float(row.spread_change_bps) if row.spread_change_bps is not None else None,
            severity=row.severity,
            narrative=row.narrative,
            ai_enabled=row.ai_enabled,
        )
        for row in rows
    ]


# ══════════════════════════════════════════════════════════════════════
# Credit Market Intelligence
# ══════════════════════════════════════════════════════════════════════


@router.get(
    "/fi/credit/briefing",
    response_model=list[CreditMarketBriefingResponse],
)
async def get_credit_briefing(
    session: AsyncSession = Depends(get_session),
):
    """Get the latest daily credit market briefing."""
    result = await session.execute(
        select(FIMarketBriefing)
        .where(FIMarketBriefing.briefing_type.in_(["CREDIT", None]))
        .order_by(FIMarketBriefing.briefing_date.desc())
        .limit(5)
    )
    rows = result.scalars().all()
    return [
        CreditMarketBriefingResponse(
            id=row.id,
            briefing_date=row.briefing_date,
            briefing_type=row.briefing_type,
            ig_oas_bps=float(row.ig_oas_bps) if row.ig_oas_bps is not None else None,
            hy_oas_bps=float(row.hy_oas_bps) if row.hy_oas_bps is not None else None,
            ig_oas_1w_change=float(row.ig_oas_1w_change) if row.ig_oas_1w_change is not None else None,
            hy_oas_1w_change=float(row.hy_oas_1w_change) if row.hy_oas_1w_change is not None else None,
            credit_regime=row.credit_regime,
            fallen_angels_this_period=row.fallen_angels_this_period,
            rising_stars_this_period=row.rising_stars_this_period,
            narrative=row.narrative,
            ai_enabled=row.ai_enabled,
        )
        for row in rows
    ]


@router.get(
    "/fi/credit/regime",
    response_model=CreditMarketBriefingResponse | None,
)
async def get_credit_regime(
    session: AsyncSession = Depends(get_session),
):
    """Get the current credit spread regime classification."""
    result = await session.execute(
        select(FIMarketBriefing)
        .where(FIMarketBriefing.credit_regime.isnot(None))
        .order_by(FIMarketBriefing.briefing_date.desc())
        .limit(1)
    )
    row = result.scalar_one_or_none()
    if not row:
        return None
    return CreditMarketBriefingResponse(
        id=row.id,
        briefing_date=row.briefing_date,
        briefing_type=row.briefing_type,
        ig_oas_bps=float(row.ig_oas_bps) if row.ig_oas_bps is not None else None,
        hy_oas_bps=float(row.hy_oas_bps) if row.hy_oas_bps is not None else None,
        ig_oas_1w_change=float(row.ig_oas_1w_change) if row.ig_oas_1w_change is not None else None,
        hy_oas_1w_change=float(row.hy_oas_1w_change) if row.hy_oas_1w_change is not None else None,
        credit_regime=row.credit_regime,
        fallen_angels_this_period=row.fallen_angels_this_period,
        rising_stars_this_period=row.rising_stars_this_period,
        narrative=row.narrative,
        ai_enabled=row.ai_enabled,
    )


@router.get(
    "/fi/credit/fallen-angels",
    response_model=list[CreditMarketBriefingResponse],
)
async def get_fallen_angels(
    session: AsyncSession = Depends(get_session),
):
    """Get recent fallen angel events from credit briefings."""
    result = await session.execute(
        select(FIMarketBriefing)
        .where(FIMarketBriefing.fallen_angels_this_period.isnot(None))
        .order_by(FIMarketBriefing.briefing_date.desc())
        .limit(20)
    )
    rows = result.scalars().all()
    return [
        CreditMarketBriefingResponse(
            id=row.id,
            briefing_date=row.briefing_date,
            briefing_type=row.briefing_type,
            ig_oas_bps=float(row.ig_oas_bps) if row.ig_oas_bps is not None else None,
            hy_oas_bps=float(row.hy_oas_bps) if row.hy_oas_bps is not None else None,
            ig_oas_1w_change=float(row.ig_oas_1w_change) if row.ig_oas_1w_change is not None else None,
            hy_oas_1w_change=float(row.hy_oas_1w_change) if row.hy_oas_1w_change is not None else None,
            credit_regime=row.credit_regime,
            fallen_angels_this_period=row.fallen_angels_this_period,
            rising_stars_this_period=row.rising_stars_this_period,
            narrative=row.narrative,
            ai_enabled=row.ai_enabled,
        )
        for row in rows
    ]


@router.get(
    "/fi/credit/rising-stars",
    response_model=list[CreditMarketBriefingResponse],
)
async def get_rising_stars(
    session: AsyncSession = Depends(get_session),
):
    """Get recent rising star events from credit briefings."""
    result = await session.execute(
        select(FIMarketBriefing)
        .where(FIMarketBriefing.rising_stars_this_period.isnot(None))
        .order_by(FIMarketBriefing.briefing_date.desc())
        .limit(20)
    )
    rows = result.scalars().all()
    return [
        CreditMarketBriefingResponse(
            id=row.id,
            briefing_date=row.briefing_date,
            briefing_type=row.briefing_type,
            ig_oas_bps=float(row.ig_oas_bps) if row.ig_oas_bps is not None else None,
            hy_oas_bps=float(row.hy_oas_bps) if row.hy_oas_bps is not None else None,
            ig_oas_1w_change=float(row.ig_oas_1w_change) if row.ig_oas_1w_change is not None else None,
            hy_oas_1w_change=float(row.hy_oas_1w_change) if row.hy_oas_1w_change is not None else None,
            credit_regime=row.credit_regime,
            fallen_angels_this_period=row.fallen_angels_this_period,
            rising_stars_this_period=row.rising_stars_this_period,
            narrative=row.narrative,
            ai_enabled=row.ai_enabled,
        )
        for row in rows
    ]


# ══════════════════════════════════════════════════════════════════════
# New Issuance
# ══════════════════════════════════════════════════════════════════════


@router.get(
    "/fi/issuance/today",
    response_model=list[IssuanceEventResponse],
)
async def get_issuance_today(
    session: AsyncSession = Depends(get_session),
):
    """Get today's new bond issues."""
    today = date.today()
    result = await session.execute(
        select(NewIssuanceEvent)
        .where(NewIssuanceEvent.issue_date == today)
        .order_by(NewIssuanceEvent.size_mm.desc().nullslast())
    )
    rows = result.scalars().all()
    return [
        IssuanceEventResponse(
            id=row.id,
            entity_id=row.entity_id,
            issue_date=row.issue_date,
            coupon_rate=float(row.coupon_rate) if row.coupon_rate is not None else None,
            maturity_date=row.maturity_date,
            size_mm=float(row.size_mm) if row.size_mm is not None else None,
            spread_at_issue_bps=float(row.spread_at_issue_bps) if row.spread_at_issue_bps is not None else None,
            initial_talk_bps=float(row.initial_talk_bps) if row.initial_talk_bps is not None else None,
            rating=row.rating,
            use_of_proceeds=row.use_of_proceeds,
            oversubscribed=row.oversubscribed,
            source_url=row.source_url,
        )
        for row in rows
    ]


@router.get(
    "/fi/issuance/this-week",
    response_model=list[IssuanceEventResponse],
)
async def get_issuance_this_week(
    session: AsyncSession = Depends(get_session),
):
    """Get this week's new issue volume."""
    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    result = await session.execute(
        select(NewIssuanceEvent)
        .where(NewIssuanceEvent.issue_date >= week_start)
        .order_by(NewIssuanceEvent.issue_date.desc(), NewIssuanceEvent.size_mm.desc().nullslast())
    )
    rows = result.scalars().all()
    return [
        IssuanceEventResponse(
            id=row.id,
            entity_id=row.entity_id,
            issue_date=row.issue_date,
            coupon_rate=float(row.coupon_rate) if row.coupon_rate is not None else None,
            maturity_date=row.maturity_date,
            size_mm=float(row.size_mm) if row.size_mm is not None else None,
            spread_at_issue_bps=float(row.spread_at_issue_bps) if row.spread_at_issue_bps is not None else None,
            initial_talk_bps=float(row.initial_talk_bps) if row.initial_talk_bps is not None else None,
            rating=row.rating,
            use_of_proceeds=row.use_of_proceeds,
            oversubscribed=row.oversubscribed,
            source_url=row.source_url,
        )
        for row in rows
    ]


@router.get(
    "/fi/issuance/pipeline",
    response_model=list[IssuanceEventResponse],
)
async def get_issuance_pipeline(
    session: AsyncSession = Depends(get_session),
):
    """Get the forward issuance calendar / pipeline."""
    today = date.today()
    result = await session.execute(
        select(NewIssuanceEvent)
        .where(NewIssuanceEvent.issue_date > today)
        .order_by(NewIssuanceEvent.issue_date.asc())
        .limit(50)
    )
    rows = result.scalars().all()
    return [
        IssuanceEventResponse(
            id=row.id,
            entity_id=row.entity_id,
            issue_date=row.issue_date,
            coupon_rate=float(row.coupon_rate) if row.coupon_rate is not None else None,
            maturity_date=row.maturity_date,
            size_mm=float(row.size_mm) if row.size_mm is not None else None,
            spread_at_issue_bps=float(row.spread_at_issue_bps) if row.spread_at_issue_bps is not None else None,
            initial_talk_bps=float(row.initial_talk_bps) if row.initial_talk_bps is not None else None,
            rating=row.rating,
            use_of_proceeds=row.use_of_proceeds,
            oversubscribed=row.oversubscribed,
            source_url=row.source_url,
        )
        for row in rows
    ]


@router.get(
    "/fi/issuance/{entity_id}",
    response_model=list[IssuanceEventResponse],
)
async def get_issuer_issuance_history(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get issuance history for a specific issuer."""
    await _get_entity(session, entity_id)

    result = await session.execute(
        select(NewIssuanceEvent)
        .where(NewIssuanceEvent.entity_id == entity_id)
        .order_by(NewIssuanceEvent.issue_date.desc())
        .limit(50)
    )
    rows = result.scalars().all()
    return [
        IssuanceEventResponse(
            id=row.id,
            entity_id=row.entity_id,
            issue_date=row.issue_date,
            coupon_rate=float(row.coupon_rate) if row.coupon_rate is not None else None,
            maturity_date=row.maturity_date,
            size_mm=float(row.size_mm) if row.size_mm is not None else None,
            spread_at_issue_bps=float(row.spread_at_issue_bps) if row.spread_at_issue_bps is not None else None,
            initial_talk_bps=float(row.initial_talk_bps) if row.initial_talk_bps is not None else None,
            rating=row.rating,
            use_of_proceeds=row.use_of_proceeds,
            oversubscribed=row.oversubscribed,
            source_url=row.source_url,
        )
        for row in rows
    ]


# ══════════════════════════════════════════════════════════════════════
# Cross-Asset Signals
# ══════════════════════════════════════════════════════════════════════


@router.get(
    "/fi/cross-asset/signals",
    response_model=list[CrossAssetSignalResponse],
)
async def get_cross_asset_signals(
    session: AsyncSession = Depends(get_session),
):
    """Get all active cross-asset divergence signals."""
    result = await session.execute(
        select(CrossAssetSignal)
        .order_by(CrossAssetSignal.signal_date.desc())
        .limit(50)
    )
    rows = result.scalars().all()
    return [
        CrossAssetSignalResponse(
            id=row.id,
            entity_id=row.entity_id,
            signal_date=row.signal_date,
            signal_type=row.signal_type,
            equity_return_pct=float(row.equity_return_pct) if row.equity_return_pct is not None else None,
            spread_change_bps=float(row.spread_change_bps) if row.spread_change_bps is not None else None,
            severity=row.severity,
            narrative=row.narrative,
            ai_enabled=row.ai_enabled,
        )
        for row in rows
    ]


@router.get(
    "/fi/cross-asset/signals/{entity_id}",
    response_model=list[CrossAssetSignalResponse],
)
async def get_cross_asset_signals_for_entity(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get cross-asset signals for a specific entity."""
    await _get_entity(session, entity_id)

    result = await session.execute(
        select(CrossAssetSignal)
        .where(CrossAssetSignal.entity_id == entity_id)
        .order_by(CrossAssetSignal.signal_date.desc())
        .limit(20)
    )
    rows = result.scalars().all()
    return [
        CrossAssetSignalResponse(
            id=row.id,
            entity_id=row.entity_id,
            signal_date=row.signal_date,
            signal_type=row.signal_type,
            equity_return_pct=float(row.equity_return_pct) if row.equity_return_pct is not None else None,
            spread_change_bps=float(row.spread_change_bps) if row.spread_change_bps is not None else None,
            severity=row.severity,
            narrative=row.narrative,
            ai_enabled=row.ai_enabled,
        )
        for row in rows
    ]


# ══════════════════════════════════════════════════════════════════════
# Issuer-Level Intelligence
# ══════════════════════════════════════════════════════════════════════


@router.get(
    "/fi/issuers/{entity_id}/credit-intelligence",
    response_model=IssuerCreditProfileResponse,
)
async def get_issuer_credit_intelligence(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get full credit intelligence profile for an issuer."""
    entity = await _get_entity(session, entity_id)

    # Latest briefing for regime info
    briefing_result = await session.execute(
        select(FIMarketBriefing)
        .order_by(FIMarketBriefing.briefing_date.desc())
        .limit(1)
    )
    briefing = briefing_result.scalar_one_or_none()

    # Count outstanding bonds
    bond_count_result = await session.execute(
        select(func.count(NewIssuanceEvent.id))
        .where(NewIssuanceEvent.entity_id == entity_id)
    )
    outstanding_bonds = bond_count_result.scalar() or 0

    # Total debt
    debt_result = await session.execute(
        select(func.sum(NewIssuanceEvent.size_mm))
        .where(NewIssuanceEvent.entity_id == entity_id)
    )
    total_debt = debt_result.scalar()

    # Next maturity
    next_maturity_result = await session.execute(
        select(NewIssuanceEvent.maturity_date)
        .where(
            and_(
                NewIssuanceEvent.entity_id == entity_id,
                NewIssuanceEvent.maturity_date >= date.today(),
            )
        )
        .order_by(NewIssuanceEvent.maturity_date.asc())
        .limit(1)
    )
    next_mat_row = next_maturity_result.scalar_one_or_none()

    return IssuerCreditProfileResponse(
        entity_id=entity.entity_id,
        legal_name=entity.legal_name,
        credit_regime=briefing.credit_regime if briefing else None,
        ig_oas_bps=float(briefing.ig_oas_bps) if briefing and briefing.ig_oas_bps is not None else None,
        outstanding_bonds=outstanding_bonds,
        total_debt_mm=float(total_debt) if total_debt is not None else None,
        next_maturity_date=next_mat_row,
    )


@router.get(
    "/fi/issuers/{entity_id}/bond-equity-divergence",
    response_model=list[CrossAssetSignalResponse],
)
async def get_bond_equity_divergence(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get bond-equity divergence signals for an issuer."""
    await _get_entity(session, entity_id)

    result = await session.execute(
        select(CrossAssetSignal)
        .where(
            and_(
                CrossAssetSignal.entity_id == entity_id,
                CrossAssetSignal.signal_type.in_(["DIVERGENCE", "BOND_EQUITY_DIVERGENCE"]),
            )
        )
        .order_by(CrossAssetSignal.signal_date.desc())
        .limit(20)
    )
    rows = result.scalars().all()
    return [
        CrossAssetSignalResponse(
            id=row.id,
            entity_id=row.entity_id,
            signal_date=row.signal_date,
            signal_type=row.signal_type,
            equity_return_pct=float(row.equity_return_pct) if row.equity_return_pct is not None else None,
            spread_change_bps=float(row.spread_change_bps) if row.spread_change_bps is not None else None,
            severity=row.severity,
            narrative=row.narrative,
            ai_enabled=row.ai_enabled,
        )
        for row in rows
    ]


@router.get(
    "/fi/issuers/{entity_id}/rating-narrative",
    response_model=IssuerCreditProfileResponse,
)
async def get_issuer_rating_narrative(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get rating history and narrative for an issuer."""
    entity = await _get_entity(session, entity_id)

    # Build a narrative from the most recent issuance rating
    issuance_result = await session.execute(
        select(NewIssuanceEvent)
        .where(NewIssuanceEvent.entity_id == entity_id)
        .order_by(NewIssuanceEvent.issue_date.desc())
        .limit(1)
    )
    latest_issuance = issuance_result.scalar_one_or_none()

    return IssuerCreditProfileResponse(
        entity_id=entity.entity_id,
        legal_name=entity.legal_name,
        current_rating=latest_issuance.rating if latest_issuance else None,
        rating_narrative=f"Latest issuance rated {latest_issuance.rating}" if latest_issuance and latest_issuance.rating else "No rating history available",
    )


@router.get(
    "/fi/issuers/{entity_id}/debt-outlook",
    response_model=IssuerCreditProfileResponse,
)
async def get_issuer_debt_outlook(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get maturity wall / debt outlook for an issuer."""
    entity = await _get_entity(session, entity_id)

    # Calculate total debt and next maturity
    debt_result = await session.execute(
        select(func.sum(NewIssuanceEvent.size_mm))
        .where(NewIssuanceEvent.entity_id == entity_id)
    )
    total_debt = debt_result.scalar()

    next_maturity_result = await session.execute(
        select(NewIssuanceEvent.maturity_date)
        .where(
            and_(
                NewIssuanceEvent.entity_id == entity_id,
                NewIssuanceEvent.maturity_date >= date.today(),
            )
        )
        .order_by(NewIssuanceEvent.maturity_date.asc())
        .limit(1)
    )
    next_mat_row = next_maturity_result.scalar_one_or_none()

    outlook = "STABLE"
    if total_debt and float(total_debt) > 10000:
        outlook = "ELEVATED"
    if next_mat_row and (next_mat_row - date.today()).days < 365:
        outlook = "NEAR_TERM_MATURITIES"

    return IssuerCreditProfileResponse(
        entity_id=entity.entity_id,
        legal_name=entity.legal_name,
        total_debt_mm=float(total_debt) if total_debt is not None else None,
        next_maturity_date=next_mat_row,
        debt_outlook=outlook,
    )
