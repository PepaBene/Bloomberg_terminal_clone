"""Company Intelligence API endpoints (Pillar 2 Supplement – Part 7)."""

import statistics
import uuid
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.ai.client import get_ai_client
from src.ai.prompts import load_prompt
from src.api.deps import get_session
from src.engines.company_intelligence import (
    extract_key_signals,
    compute_valuation_context,
    generate_briefing,
)
from src.models.analytics import AnalyticsResult
from src.models.company_intelligence import CompanyBriefing
from src.models.entity import Entity
from src.models.fundamentals import FinancialPeriod  # noqa: F401 — relationships load IncomeStatement etc.
from src.models.security import EODPrice, EquityDetails, Security
from src.schemas.company_intelligence import (
    CompanyBriefingResponse,
    KeySignal,
    SignalsOnlyResponse,
    ValuationContext,
)

router = APIRouter(tags=["Company Intelligence"])

_PRICE_LOOKBACK_DAYS = 45
_MOMENTUM_WINDOW = 5  # trading sessions for price_change_pct / volume_ratio


async def _get_entity(session: AsyncSession, entity_id: uuid.UUID) -> Entity:
    """Fetch entity or raise 404."""
    result = await session.execute(
        select(Entity).where(Entity.entity_id == entity_id)
    )
    entity = result.scalar_one_or_none()
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
    return entity


async def _primary_equity_security_id(
    session: AsyncSession, entity_id: uuid.UUID
) -> uuid.UUID | None:
    """Find the entity's primary (active common-stock) equity security."""
    rows = (
        await session.execute(
            select(Security.security_id, Security.security_type, Security.status)
            .where(
                Security.issuer_entity_id == entity_id,
                Security.asset_class == "EQUITY",
            )
        )
    ).all()
    if not rows:
        return None
    rows.sort(key=lambda r: (r[2] != "ACTIVE", r[1] != "COMMON_STOCK"))
    return rows[0][0]


async def _assemble_signal_data(session: AsyncSession, entity_id: uuid.UUID) -> dict:
    """Assemble real signal inputs from Pillar 1 data (prices + fundamentals).

    Sub-signals with no production data source yet (earnings surprise,
    insider net shares, guidance revision, analyst revisions) are left out
    rather than fabricated — extract_key_signals() treats missing keys as
    "no signal" instead of a fake neutral value.
    """
    data: dict = {}

    security_id = await _primary_equity_security_id(session, entity_id)
    if security_id is not None:
        cutoff = date.today() - timedelta(days=_PRICE_LOOKBACK_DAYS)
        rows = (
            await session.execute(
                select(EODPrice.close, EODPrice.volume)
                .where(
                    EODPrice.security_id == security_id,
                    EODPrice.price_date >= cutoff,
                )
                .order_by(EODPrice.price_date.asc())
            )
        ).all()
        closes = [float(r[0]) for r in rows if r[0] is not None]
        volumes = [int(r[1]) for r in rows if r[1] is not None]

        if len(closes) > _MOMENTUM_WINDOW:
            prior = closes[-1 - _MOMENTUM_WINDOW]
            if prior > 0:
                data["price_change_pct"] = (closes[-1] - prior) / prior * 100

        if len(volumes) > _MOMENTUM_WINDOW:
            recent = volumes[-_MOMENTUM_WINDOW:]
            history = volumes[:-_MOMENTUM_WINDOW]
            if history:
                avg_volume = statistics.mean(history)
                if avg_volume > 0:
                    data["volume_ratio"] = statistics.mean(recent) / avg_volume

    fp_result = await session.execute(
        select(FinancialPeriod)
        .where(FinancialPeriod.entity_id == entity_id)
        .order_by(FinancialPeriod.period_end_date.desc())
        .limit(1)
    )
    latest_period = fp_result.scalar_one_or_none()
    if latest_period:
        inc = latest_period.income_statement
        bs = latest_period.balance_sheet
        if bs and bs.total_debt is not None and bs.total_equity:
            data["debt_to_equity"] = float(bs.total_debt) / float(bs.total_equity)
        if (
            inc
            and inc.operating_income is not None
            and inc.interest_expense
        ):
            data["interest_coverage"] = float(inc.operating_income) / abs(
                float(inc.interest_expense)
            )

    return data


async def _assemble_valuation_data(session: AsyncSession, entity_id: uuid.UUID) -> dict:
    """Assemble real valuation inputs from Pillar 1/2 data."""
    data: dict = {}
    shares_outstanding: float | None = None

    security_id = await _primary_equity_security_id(session, entity_id)
    if security_id is not None:
        price_row = (
            await session.execute(
                select(EODPrice.close)
                .where(EODPrice.security_id == security_id, EODPrice.close.isnot(None))
                .order_by(EODPrice.price_date.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if price_row is not None:
            data["price"] = float(price_row)

        shares = (
            await session.execute(
                select(EquityDetails.shares_outstanding).where(
                    EquityDetails.security_id == security_id
                )
            )
        ).scalar_one_or_none()
        if shares is not None:
            shares_outstanding = float(shares)

    fp_result = await session.execute(
        select(FinancialPeriod)
        .where(FinancialPeriod.entity_id == entity_id)
        .order_by(FinancialPeriod.period_end_date.desc())
        .limit(1)
    )
    latest_period = fp_result.scalar_one_or_none()
    if latest_period:
        inc = latest_period.income_statement
        bs = latest_period.balance_sheet
        if inc and inc.diluted_eps is not None:
            data["eps"] = float(inc.diluted_eps)
        if inc and inc.ebitda is not None:
            data["ebitda"] = float(inc.ebitda)
        if bs and bs.total_equity is not None and shares_outstanding:
            data["book_value_per_share"] = float(bs.total_equity) / shares_outstanding

    # Real ev_ebitda / dividend_yield already computed by the batch comps
    # engine (E2) — use them to derive a dividend-per-share input rather
    # than fabricating one.
    val_result = await session.execute(
        select(AnalyticsResult)
        .where(
            AnalyticsResult.entity_id == entity_id,
            AnalyticsResult.metric_category == "VALUATION",
        )
        .order_by(AnalyticsResult.as_of_date.desc())
        .limit(10)
    )
    metrics = {}
    for ar in val_result.scalars().all():
        name = ar.metric_name.lower()
        if ar.value is not None and name not in metrics:
            metrics[name] = float(ar.value)

    if "ev_ebitda" in metrics and data.get("ebitda"):
        data["ev"] = metrics["ev_ebitda"] * data["ebitda"]
    if "dividend_yield" in metrics and data.get("price"):
        data["dividend_per_share"] = metrics["dividend_yield"] / 100 * data["price"]

    return data


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

    db_briefing = await _generate_and_persist_briefing(session, entity)
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

    signal_data = await _assemble_signal_data(session, entity_id)
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
    db_briefing = await _generate_and_persist_briefing(session, entity)
    return _briefing_to_response(db_briefing)


async def _generate_and_persist_briefing(
    session: AsyncSession, entity: Entity
) -> CompanyBriefing:
    """Assemble real signal/valuation data, optionally generate an AI summary,
    and persist a new briefing row."""
    entity_id = entity.entity_id
    client = get_ai_client()
    signal_data = await _assemble_signal_data(session, entity_id)
    valuation_data = await _assemble_valuation_data(session, entity_id)

    ai_summary = None
    if client.enabled:
        signals_preview = extract_key_signals(signal_data)
        prompt = load_prompt("company_briefing_summary")
        ai_summary = await client.complete_text(
            user=prompt.render(
                company=entity.legal_name,
                signals=[s.signal for s in signals_preview],
                valuation_data=valuation_data,
            ),
            system=prompt.system,
            tier=prompt.tier,
            max_tokens=prompt.max_tokens,
            feature=prompt.feature,
        )

    briefing = generate_briefing(
        entity_id=str(entity_id),
        entity_name=entity.legal_name,
        signal_data=signal_data,
        valuation_data=valuation_data,
        ai_summary=ai_summary,
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
    return db_briefing


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
