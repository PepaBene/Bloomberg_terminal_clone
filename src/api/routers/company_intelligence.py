"""Company Intelligence API endpoints (Pillar 2 Supplement – Part 7)."""

import uuid
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.ai.llm_client import get_llm_client
from src.api.deps import get_session
from src.engines.company_intelligence import (
    extract_key_signals,
    compute_valuation_context,
    generate_briefing,
)
from src.models.company_intelligence import CompanyBriefing
from src.models.entity import Entity
from src.schemas.company_intelligence import (
    CompanyBriefingResponse,
    KeySignal,
    SignalsOnlyResponse,
    ValuationContext,
)

router = APIRouter(tags=["Company Intelligence"])


async def _get_entity(session: AsyncSession, entity_id: uuid.UUID) -> Entity:
    """Fetch entity or raise 404."""
    result = await session.execute(
        select(Entity).where(Entity.entity_id == entity_id)
    )
    entity = result.scalar_one_or_none()
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
    return entity


@router.get(
    "/analytics/intelligence/{entity_id}",
    response_model=CompanyBriefingResponse,
)
async def get_company_briefing(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get the latest company intelligence briefing.

    Generates a new briefing if none exists or the existing one is stale.
    When AI is disabled, structured data is returned but narrative text is null.
    """
    entity = await _get_entity(session, entity_id)

    # Check for existing recent briefing
    result = await session.execute(
        select(CompanyBriefing)
        .where(CompanyBriefing.entity_id == entity_id)
        .order_by(CompanyBriefing.briefing_date.desc())
        .limit(1)
    )
    existing = result.scalar_one_or_none()

    if existing and existing.briefing_date == date.today():
        return _briefing_to_response(existing)

    # Generate new briefing
    llm = get_llm_client()
    signal_data = {}  # In production, assemble from DB queries
    valuation_data = {}

    briefing = generate_briefing(
        entity_id=str(entity_id),
        entity_name=entity.legal_name,
        signal_data=signal_data,
        valuation_data=valuation_data,
        ai_summary=None,  # LLM integration deferred
    )

    # Persist
    db_briefing = CompanyBriefing(
        briefing_id=uuid.uuid4(),
        entity_id=entity_id,
        briefing_type="DAILY",
        briefing_date=date.today(),
        status="COMPLETED",
        summary_text=briefing.summary_text,
        key_signals=[{"signal": s.signal, "severity": s.severity, "detail": s.detail}
                     for s in briefing.key_signals],
        valuation_context=_valuation_to_dict(briefing.valuation_context) if briefing.valuation_context else None,
        ai_enabled=briefing.ai_enabled,
    )
    session.add(db_briefing)
    await session.commit()
    await session.refresh(db_briefing)

    return _briefing_to_response(db_briefing)


# NOTE: /signals must be defined as a separate path — no conflict here
# because entity_id is required in the path.
@router.get(
    "/analytics/intelligence/{entity_id}/signals",
    response_model=SignalsOnlyResponse,
)
async def get_company_signals(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get key signals for a company (no AI needed)."""
    await _get_entity(session, entity_id)

    signal_data = {}  # In production, assemble from DB queries
    signals = extract_key_signals(signal_data)

    return SignalsOnlyResponse(
        entity_id=entity_id,
        signals=[KeySignal(signal=s.signal, severity=s.severity, detail=s.detail)
                 for s in signals],
        generated_at=datetime.now(timezone.utc),
    )


@router.post(
    "/analytics/intelligence/{entity_id}/refresh",
    response_model=CompanyBriefingResponse,
)
async def refresh_briefing(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Force regenerate a company briefing."""
    entity = await _get_entity(session, entity_id)

    llm = get_llm_client()
    signal_data = {}
    valuation_data = {}

    briefing = generate_briefing(
        entity_id=str(entity_id),
        entity_name=entity.legal_name,
        signal_data=signal_data,
        valuation_data=valuation_data,
        ai_summary=None,
    )

    db_briefing = CompanyBriefing(
        briefing_id=uuid.uuid4(),
        entity_id=entity_id,
        briefing_type="DAILY",
        briefing_date=date.today(),
        status="COMPLETED",
        summary_text=briefing.summary_text,
        key_signals=[{"signal": s.signal, "severity": s.severity, "detail": s.detail}
                     for s in briefing.key_signals],
        valuation_context=_valuation_to_dict(briefing.valuation_context) if briefing.valuation_context else None,
        ai_enabled=briefing.ai_enabled,
    )
    session.add(db_briefing)
    await session.commit()
    await session.refresh(db_briefing)

    return _briefing_to_response(db_briefing)


def _briefing_to_response(briefing: CompanyBriefing) -> CompanyBriefingResponse:
    """Convert a DB briefing to response schema."""
    signals = []
    if briefing.key_signals and isinstance(briefing.key_signals, list):
        signals = [KeySignal(**s) for s in briefing.key_signals]

    vc = None
    if briefing.valuation_context and isinstance(briefing.valuation_context, dict):
        vc = ValuationContext(**briefing.valuation_context)

    return CompanyBriefingResponse(
        briefing_id=briefing.briefing_id,
        entity_id=briefing.entity_id,
        briefing_type=briefing.briefing_type,
        briefing_date=briefing.briefing_date,
        status=briefing.status,
        summary_text=briefing.summary_text,
        key_signals=signals,
        valuation_context=vc,
        value_investing_lens=briefing.value_investing_lens,
        ai_enabled=briefing.ai_enabled,
    )


def _valuation_to_dict(vc) -> dict:
    """Convert ValuationContext dataclass to dict."""
    return {
        "pe_current": vc.pe_current,
        "pe_5y_avg": vc.pe_5y_avg,
        "pe_vs_peers": vc.pe_vs_peers,
        "ev_ebitda": vc.ev_ebitda,
        "pb_ratio": vc.pb_ratio,
        "dividend_yield": vc.dividend_yield,
    }
