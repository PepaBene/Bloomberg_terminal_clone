"""Research Briefings API endpoints (Pillar 3 Phase 4A)."""

import uuid
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.ai.llm_client import get_llm_client
from src.api.auth.dependencies import get_current_active_user
from src.api.deps import get_session
from src.models.auth import User
from src.models.entity import Entity
from src.models.investment_thesis import InvestmentThesis
from src.models.macro import MacroIndicator, MacroValue
from src.models.morning_briefing import MorningBriefing, BriefingPreference
from src.models.security import EODPrice, Security
from src.schemas.morning_briefing_schema import (
    BriefingPreferenceRequest,
    BriefingPreferenceResponse,
    MorningBriefingResponse,
)

router = APIRouter(tags=["Research - Morning Briefings"])

# Headline series shown in every macro-context section, mirroring the FRED
# seed set in src/ingestion/fred_macro.py.
_MACRO_HEADLINE_CODES = ["UNRATE", "CPIAUCSL", "FEDFUNDS", "DGS10", "T10Y2Y"]


def _preference_entity_ids(raw: dict | None) -> set[uuid.UUID]:
    """Extract entity UUIDs from a BriefingPreference JSONB field.

    The field is stored as an open-ended JSON dict; accept the common
    shapes (``{"ids": [...]}`` or a dict keyed by entity id).
    """
    if not raw:
        return set()
    candidates = raw.get("ids") if isinstance(raw, dict) and "ids" in raw else raw
    if isinstance(candidates, dict):
        candidates = list(candidates.keys())
    if not isinstance(candidates, list):
        return set()
    ids = set()
    for c in candidates:
        try:
            ids.add(uuid.UUID(str(c)))
        except (ValueError, AttributeError, TypeError):
            continue
    return ids


async def _assemble_portfolio_impact(session: AsyncSession, entity_ids: set[uuid.UUID]) -> dict | None:
    """Real 1-day price moves for tracked entities, from EODPrice."""
    if not entity_ids:
        return None

    impacts = {}
    for entity_id in entity_ids:
        entity = (
            await session.execute(select(Entity).where(Entity.entity_id == entity_id))
        ).scalar_one_or_none()
        if not entity:
            continue

        sec_row = (
            await session.execute(
                select(Security.security_id)
                .where(Security.issuer_entity_id == entity_id, Security.asset_class == "EQUITY")
                .limit(1)
            )
        ).scalar_one_or_none()
        if not sec_row:
            continue

        closes = (
            await session.execute(
                select(EODPrice.close)
                .where(EODPrice.security_id == sec_row, EODPrice.close.isnot(None))
                .order_by(EODPrice.price_date.desc())
                .limit(2)
            )
        ).scalars().all()
        if len(closes) < 2 or not closes[1]:
            continue

        latest, prior = float(closes[0]), float(closes[1])
        impacts[str(entity_id)] = {
            "entity_name": entity.legal_name,
            "price_change_1d_pct": round((latest - prior) / prior * 100, 2),
        }

    return impacts or None


async def _assemble_thesis_updates(session: AsyncSession, entity_ids: set[uuid.UUID]) -> dict | None:
    """Recently-updated investment theses for tracked entities."""
    if not entity_ids:
        return None

    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    rows = (
        await session.execute(
            select(InvestmentThesis)
            .where(
                InvestmentThesis.entity_id.in_(entity_ids),
                InvestmentThesis.updated_at >= cutoff,
            )
            .order_by(InvestmentThesis.updated_at.desc())
            .limit(20)
        )
    ).scalars().all()
    if not rows:
        return None

    return {
        "updates": [
            {
                "entity_id": str(t.entity_id),
                "thesis_title": t.thesis_title,
                "conviction_level": t.conviction_level,
                "version": t.version,
                "updated_at": t.updated_at.isoformat() if t.updated_at else None,
            }
            for t in rows
        ]
    }


async def _assemble_macro_context(session: AsyncSession) -> dict | None:
    """Latest readings for a fixed set of headline macro indicators."""
    context = {}
    for code in _MACRO_HEADLINE_CODES:
        indicator = (
            await session.execute(
                select(MacroIndicator).where(MacroIndicator.indicator_code == code)
            )
        ).scalar_one_or_none()
        if not indicator:
            continue
        latest = (
            await session.execute(
                select(MacroValue)
                .where(MacroValue.indicator_id == indicator.indicator_id)
                .order_by(MacroValue.observation_date.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if not latest:
            continue
        context[code] = {
            "name": indicator.name,
            "value": float(latest.value),
            "observation_date": latest.observation_date.isoformat(),
            "yoy_change_pct": float(latest.value_yoy_percent) if latest.value_yoy_percent is not None else None,
        }
    return context or None


def _briefing_response(row: MorningBriefing) -> MorningBriefingResponse:
    return MorningBriefingResponse(
        id=row.id,
        user_id=row.user_id,
        briefing_date=row.briefing_date,
        regional_context=row.regional_context,
        executive_summary=row.executive_summary,
        portfolio_impact=row.portfolio_impact,
        key_news=row.key_news,
        thesis_updates=row.thesis_updates,
        macro_context=row.macro_context,
        actionable_insights=row.actionable_insights,
        delivery_format=row.delivery_format,
        ai_enabled=row.ai_enabled,
    )


# ── Static routes (MUST come before parametric routes) ──────────────


@router.get(
    "/research/briefings/today",
    response_model=list[MorningBriefingResponse],
)
async def get_todays_briefing(
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session),
):
    """Get today's morning briefing."""
    today = date.today()
    result = await session.execute(
        select(MorningBriefing)
        .where(MorningBriefing.user_id == current_user.user_id)
        .where(MorningBriefing.briefing_date == today)
        .order_by(MorningBriefing.briefing_date.desc())
    )
    rows = result.scalars().all()
    return [_briefing_response(row) for row in rows]


@router.get(
    "/research/briefings/history",
    response_model=list[MorningBriefingResponse],
)
async def get_briefing_history(
    limit: int = Query(default=30, ge=1, le=100),
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session),
):
    """Get past briefings for a user."""
    result = await session.execute(
        select(MorningBriefing)
        .where(MorningBriefing.user_id == current_user.user_id)
        .order_by(MorningBriefing.briefing_date.desc())
        .limit(limit)
    )
    rows = result.scalars().all()
    return [_briefing_response(row) for row in rows]


@router.get(
    "/research/briefings/preferences",
    response_model=BriefingPreferenceResponse | None,
)
async def get_briefing_preferences(
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session),
):
    """Get briefing preferences for a user."""
    result = await session.execute(
        select(BriefingPreference)
        .where(BriefingPreference.user_id == current_user.user_id)
    )
    row = result.scalar_one_or_none()
    if not row:
        return None

    return BriefingPreferenceResponse(
        id=row.id,
        user_id=row.user_id,
        portfolio_entity_ids=row.portfolio_entity_ids,
        watchlist_entity_ids=row.watchlist_entity_ids,
        sector_focus=row.sector_focus,
        risk_tolerance=row.risk_tolerance,
        delivery_time_utc=row.delivery_time_utc,
        delivery_format=row.delivery_format,
        timezone=row.timezone,
        is_active=row.is_active,
    )


@router.put(
    "/research/briefings/preferences",
    response_model=BriefingPreferenceResponse,
)
async def update_briefing_preferences(
    body: BriefingPreferenceRequest,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session),
):
    """Create or update briefing preferences."""
    result = await session.execute(
        select(BriefingPreference)
        .where(BriefingPreference.user_id == current_user.user_id)
    )
    pref = result.scalar_one_or_none()

    if pref:
        pref.portfolio_entity_ids = body.portfolio_entity_ids
        pref.watchlist_entity_ids = body.watchlist_entity_ids
        pref.sector_focus = body.sector_focus
        pref.risk_tolerance = body.risk_tolerance
        pref.delivery_time_utc = body.delivery_time_utc
        pref.delivery_format = body.delivery_format
        pref.timezone = body.timezone
        pref.is_active = body.is_active
    else:
        pref = BriefingPreference(
            id=uuid.uuid4(),
            user_id=current_user.user_id,
            portfolio_entity_ids=body.portfolio_entity_ids,
            watchlist_entity_ids=body.watchlist_entity_ids,
            sector_focus=body.sector_focus,
            risk_tolerance=body.risk_tolerance,
            delivery_time_utc=body.delivery_time_utc,
            delivery_format=body.delivery_format,
            timezone=body.timezone,
            is_active=body.is_active,
        )
        session.add(pref)

    await session.commit()

    return BriefingPreferenceResponse(
        id=pref.id,
        user_id=pref.user_id,
        portfolio_entity_ids=pref.portfolio_entity_ids,
        watchlist_entity_ids=pref.watchlist_entity_ids,
        sector_focus=pref.sector_focus,
        risk_tolerance=pref.risk_tolerance,
        delivery_time_utc=pref.delivery_time_utc,
        delivery_format=pref.delivery_format,
        timezone=pref.timezone,
        is_active=pref.is_active,
    )


@router.get(
    "/research/briefings/portfolio-impact",
    response_model=dict,
)
async def get_portfolio_impact(
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session),
):
    """Get portfolio impact section from today's briefing."""
    today = date.today()
    result = await session.execute(
        select(MorningBriefing)
        .where(MorningBriefing.user_id == current_user.user_id)
        .where(MorningBriefing.briefing_date == today)
        .order_by(MorningBriefing.briefing_date.desc())
        .limit(1)
    )
    row = result.scalar_one_or_none()
    if not row:
        return {"portfolio_impact": None, "briefing_date": str(today)}

    return {
        "portfolio_impact": row.portfolio_impact,
        "briefing_date": str(row.briefing_date),
    }


@router.get(
    "/research/briefings/macro-summary",
    response_model=dict,
)
async def get_macro_summary(
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session),
):
    """Get macro context section from today's briefing."""
    today = date.today()
    result = await session.execute(
        select(MorningBriefing)
        .where(MorningBriefing.user_id == current_user.user_id)
        .where(MorningBriefing.briefing_date == today)
        .order_by(MorningBriefing.briefing_date.desc())
        .limit(1)
    )
    row = result.scalar_one_or_none()
    if not row:
        return {"macro_context": None, "briefing_date": str(today)}

    return {
        "macro_context": row.macro_context,
        "briefing_date": str(row.briefing_date),
    }


@router.post(
    "/research/briefings/generate",
    response_model=MorningBriefingResponse,
)
async def generate_briefing(
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session),
):
    """Generate an on-demand briefing from real portfolio/watchlist/macro data."""
    today = date.today()
    llm = get_llm_client()

    pref = (
        await session.execute(
            select(BriefingPreference).where(BriefingPreference.user_id == current_user.user_id)
        )
    ).scalar_one_or_none()

    entity_ids = set()
    if pref:
        entity_ids |= _preference_entity_ids(pref.portfolio_entity_ids)
        entity_ids |= _preference_entity_ids(pref.watchlist_entity_ids)

    portfolio_impact = await _assemble_portfolio_impact(session, entity_ids)
    thesis_updates = await _assemble_thesis_updates(session, entity_ids)
    macro_context = await _assemble_macro_context(session)

    executive_summary = None
    if llm.enabled:
        executive_summary = await llm.generate(
            system_prompt=(
                "You are a Bloomberg financial research AI assistant writing a "
                "morning briefing executive summary. 2-4 sentences, grounded only "
                "in the provided data. If a section has no data, note it plainly "
                "rather than inventing content."
            ),
            user_prompt=(
                f"Portfolio impact: {portfolio_impact}\n"
                f"Thesis updates: {thesis_updates}\n"
                f"Macro context: {macro_context}\n"
                "Write the executive summary."
            ),
        )

    briefing = MorningBriefing(
        id=uuid.uuid4(),
        user_id=current_user.user_id,
        briefing_date=today,
        regional_context="US",
        executive_summary=executive_summary,
        portfolio_impact=portfolio_impact,
        thesis_updates=thesis_updates,
        macro_context=macro_context,
        delivery_format="FULL",
        ai_enabled=executive_summary is not None,
    )
    session.add(briefing)
    await session.commit()

    return _briefing_response(briefing)


# ── Parametric routes ───────────────────────────────────────────────


@router.get(
    "/research/briefings/{briefing_id}",
    response_model=MorningBriefingResponse,
)
async def get_briefing_by_id(
    briefing_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session),
):
    """Get a specific briefing by ID."""
    result = await session.execute(
        select(MorningBriefing)
        .where(MorningBriefing.id == briefing_id)
    )
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Briefing not found")

    return _briefing_response(row)
