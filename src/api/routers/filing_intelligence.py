"""Filing Intelligence API endpoints (Pillar 3 Phase 1)."""

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_session
from src.models.entity import Entity
from src.models.filing_intelligence import EightKEvent, FilingDiff
from src.models.insider_intelligence import InsiderTransactionP3, InsiderSignal
from src.schemas.filing_intelligence import (
    EightKEventResponse,
    EightKEventsListResponse,
    FilingDiffResponse,
    FilingDiffSectionResponse,
    FilingDiffSummaryResponse,
)
from src.schemas.insider_intelligence import (
    InsiderScreenRequest,
    InsiderScreenResponse,
    InsiderSignalResponse,
    InsiderSummaryResponse,
    InsiderTransactionResponse,
)

router = APIRouter(tags=["Filing Intelligence"])


async def _get_entity(session: AsyncSession, entity_id: uuid.UUID) -> Entity:
    result = await session.execute(
        select(Entity).where(Entity.entity_id == entity_id)
    )
    entity = result.scalar_one_or_none()
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
    return entity


# ── 8-K Events ─────────────────────────────────────────────────────────


@router.get(
    "/filings/events/today",
    response_model=EightKEventsListResponse,
)
async def get_todays_events(
    session: AsyncSession = Depends(get_session),
    item: str | None = Query(None, description="Filter by item number (e.g. 1.01)"),
    priority: int | None = Query(None, ge=1, le=5, description="Filter by priority"),
):
    """Get all 8-K events filed today."""
    today = date.today()
    stmt = select(EightKEvent).where(EightKEvent.filing_date == today)

    if item:
        stmt = stmt.where(EightKEvent.item_number == item)
    if priority is not None:
        stmt = stmt.where(EightKEvent.priority <= priority)

    stmt = stmt.order_by(EightKEvent.priority.asc())
    result = await session.execute(stmt)
    rows = result.scalars().all()

    events = [
        EightKEventResponse(
            id=row.id,
            entity_id=row.entity_id,
            filing_date=row.filing_date,
            item_number=row.item_number,
            item_description=row.item_description,
            priority=row.priority,
            monetary_figures=row.monetary_figures,
            key_dates=row.key_dates,
            key_people=row.key_people,
            ai_summary=row.ai_summary,
            materiality=row.materiality,
            filing_url=row.filing_url,
        )
        for row in rows
    ]
    return EightKEventsListResponse(events=events, total_count=len(events))


@router.get(
    "/filings/{entity_id}/events",
    response_model=EightKEventsListResponse,
)
async def get_entity_events(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    priority: int | None = Query(None, ge=1, le=5, description="Max priority level"),
    item: str | None = Query(None, description="Filter by item number"),
    from_date: date | None = Query(None, description="Start date"),
    to_date: date | None = Query(None, description="End date"),
):
    """Get 8-K events for a specific entity."""
    await _get_entity(session, entity_id)

    stmt = select(EightKEvent).where(EightKEvent.entity_id == entity_id)

    if priority is not None:
        stmt = stmt.where(EightKEvent.priority <= priority)
    if item:
        stmt = stmt.where(EightKEvent.item_number == item)
    if from_date:
        stmt = stmt.where(EightKEvent.filing_date >= from_date)
    if to_date:
        stmt = stmt.where(EightKEvent.filing_date <= to_date)

    stmt = stmt.order_by(desc(EightKEvent.filing_date))
    result = await session.execute(stmt)
    rows = result.scalars().all()

    events = [
        EightKEventResponse(
            id=row.id,
            entity_id=row.entity_id,
            filing_date=row.filing_date,
            item_number=row.item_number,
            item_description=row.item_description,
            priority=row.priority,
            monetary_figures=row.monetary_figures,
            key_dates=row.key_dates,
            key_people=row.key_people,
            ai_summary=row.ai_summary,
            materiality=row.materiality,
            filing_url=row.filing_url,
        )
        for row in rows
    ]
    return EightKEventsListResponse(events=events, total_count=len(events))


# ── Filing Diffs ───────────────────────────────────────────────────────


def _build_diff_response(
    entity_id: uuid.UUID, rows: list[FilingDiff],
) -> FilingDiffResponse:
    """Convert a list of FilingDiff ORM rows into a single FilingDiffResponse."""
    if not rows:
        raise HTTPException(status_code=404, detail="No filing diffs found")

    first = rows[0]
    materiality_order = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}
    overall_materiality = max(
        (r.materiality for r in rows if r.materiality),
        key=lambda m: materiality_order.get(m, 0),
        default=None,
    )

    section_diffs = [
        FilingDiffSectionResponse(
            section_key=row.section_key,
            change_pct=float(row.change_pct) if row.change_pct is not None else None,
            classification=row.change_classification,
            materiality=row.materiality,
            substantive_count=row.substantive_change_count,
            added_count=len(row.added_paragraphs) if row.added_paragraphs else 0,
            removed_count=len(row.removed_paragraphs) if row.removed_paragraphs else 0,
            modified_count=len(row.modified_paragraphs) if row.modified_paragraphs else 0,
            added_paragraphs=row.added_paragraphs,
            removed_paragraphs=row.removed_paragraphs,
            modified_paragraphs=row.modified_paragraphs,
        )
        for row in rows
    ]

    ai_summaries = [r.ai_summary for r in rows if r.ai_summary]
    combined_summary = " /// ".join(ai_summaries) if ai_summaries else None

    return FilingDiffResponse(
        entity_id=entity_id,
        year_old=first.year_old,
        year_new=first.year_new,
        overall_materiality=overall_materiality,
        section_diffs=section_diffs,
        ai_summary=combined_summary,
    )


@router.get(
    "/filings/{entity_id}/diff/latest",
    response_model=FilingDiffResponse,
)
async def get_latest_filing_diff(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get the latest year-over-year filing diff for an entity."""
    await _get_entity(session, entity_id)

    # Find the most recent year_new for this entity
    max_year_result = await session.execute(
        select(func.max(FilingDiff.year_new)).where(
            FilingDiff.entity_id == entity_id
        )
    )
    max_year = max_year_result.scalar_one_or_none()
    if max_year is None:
        raise HTTPException(status_code=404, detail="No filing diffs found for this entity")

    # Get the corresponding year_old
    year_pair = await session.execute(
        select(FilingDiff.year_old)
        .where(and_(FilingDiff.entity_id == entity_id, FilingDiff.year_new == max_year))
        .limit(1)
    )
    year_old = year_pair.scalar_one_or_none()
    if year_old is None:
        # No paired prior-year row for this max year; return an empty diff
        # (via the shared helper, which itself 404s on an empty row list)
        # rather than passing None into the WHERE clause below.
        return _build_diff_response(entity_id, [])

    result = await session.execute(
        select(FilingDiff)
        .where(
            and_(
                FilingDiff.entity_id == entity_id,
                FilingDiff.year_old == year_old,
                FilingDiff.year_new == max_year,
            )
        )
        .order_by(FilingDiff.section_key)
    )
    rows = result.scalars().all()

    return _build_diff_response(entity_id, list(rows))


@router.get(
    "/filings/{entity_id}/diff/risk-factors",
    response_model=FilingDiffResponse,
)
async def get_risk_factors_diff(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get latest risk factors (Item 1A) diff for an entity."""
    await _get_entity(session, entity_id)

    result = await session.execute(
        select(FilingDiff)
        .where(
            and_(
                FilingDiff.entity_id == entity_id,
                FilingDiff.section_key == "ITEM_1A",
            )
        )
        .order_by(FilingDiff.year_new.desc())
        .limit(1)
    )
    rows = result.scalars().all()

    return _build_diff_response(entity_id, list(rows))


@router.get(
    "/filings/{entity_id}/diff/summary",
    response_model=FilingDiffSummaryResponse,
)
async def get_filing_diff_summary(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get a summary of the latest filing diff (top changes only)."""
    await _get_entity(session, entity_id)

    # Find the most recent diff pair
    max_year_result = await session.execute(
        select(func.max(FilingDiff.year_new)).where(
            FilingDiff.entity_id == entity_id
        )
    )
    max_year = max_year_result.scalar_one_or_none()
    if max_year is None:
        raise HTTPException(status_code=404, detail="No filing diffs found for this entity")

    year_pair = await session.execute(
        select(FilingDiff.year_old)
        .where(and_(FilingDiff.entity_id == entity_id, FilingDiff.year_new == max_year))
        .limit(1)
    )
    year_old = year_pair.scalar_one_or_none()
    if year_old is None:
        raise HTTPException(status_code=404, detail="No filing diffs found")

    result = await session.execute(
        select(FilingDiff)
        .where(
            and_(
                FilingDiff.entity_id == entity_id,
                FilingDiff.year_old == year_old,
                FilingDiff.year_new == max_year,
            )
        )
        .order_by(FilingDiff.substantive_change_count.desc())
    )
    rows = result.scalars().all()

    if not rows:
        raise HTTPException(status_code=404, detail="No filing diffs found")

    materiality_order = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}
    overall_materiality = max(
        (r.materiality for r in rows if r.materiality),
        key=lambda m: materiality_order.get(m, 0),
        default=None,
    )

    top_changes = [
        {
            "section_key": r.section_key,
            "classification": r.change_classification,
            "materiality": r.materiality,
            "substantive_count": r.substantive_change_count,
            "change_pct": float(r.change_pct) if r.change_pct is not None else None,
        }
        for r in rows[:5]
    ]

    ai_summaries = [r.ai_summary for r in rows if r.ai_summary]
    combined_summary = " /// ".join(ai_summaries[:3]) if ai_summaries else None

    return FilingDiffSummaryResponse(
        entity_id=entity_id,
        year_old=year_old,
        year_new=max_year,
        overall_materiality=overall_materiality,
        ai_summary=combined_summary,
        top_changes=top_changes,
    )


@router.get(
    "/filings/{entity_id}/diff",
    response_model=FilingDiffResponse,
)
async def get_filing_diff(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    year1: int = Query(..., description="Older fiscal year"),
    year2: int = Query(..., description="Newer fiscal year"),
):
    """Get filing diff between two specific fiscal years."""
    await _get_entity(session, entity_id)

    result = await session.execute(
        select(FilingDiff)
        .where(
            and_(
                FilingDiff.entity_id == entity_id,
                FilingDiff.year_old == year1,
                FilingDiff.year_new == year2,
            )
        )
        .order_by(FilingDiff.section_key)
    )
    rows = result.scalars().all()

    return _build_diff_response(entity_id, list(rows))


# ── Insider Intelligence ───────────────────────────────────────────────


@router.get(
    "/filings/{entity_id}/insiders",
    response_model=InsiderSummaryResponse,
)
async def get_insider_summary(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get insider trading summary for an entity (signals + recent transactions)."""
    await _get_entity(session, entity_id)

    # Latest signals
    signal_result = await session.execute(
        select(InsiderSignal)
        .where(InsiderSignal.entity_id == entity_id)
        .order_by(InsiderSignal.signal_date.desc())
        .limit(10)
    )
    signal_rows = signal_result.scalars().all()

    signals = [
        InsiderSignalResponse(
            signal_type=s.signal_type,
            signal_strength=s.signal_strength,
            signal_date=s.signal_date,
            detail=s.detail,
        )
        for s in signal_rows
    ]

    # Aggregate net values from the latest signal
    latest_signal = signal_rows[0] if signal_rows else None

    # Recent transactions
    tx_result = await session.execute(
        select(InsiderTransactionP3)
        .where(InsiderTransactionP3.entity_id == entity_id)
        .order_by(InsiderTransactionP3.transaction_date.desc())
        .limit(20)
    )
    tx_rows = tx_result.scalars().all()

    recent_txs = [
        InsiderTransactionResponse(
            id=t.id,
            entity_id=t.entity_id,
            reporting_person=t.reporting_person,
            relationship=t.relationship,
            transaction_type=t.transaction_type,
            transaction_date=t.transaction_date,
            shares=float(t.shares) if t.shares is not None else None,
            price_per_share=float(t.price_per_share) if t.price_per_share is not None else None,
            total_value=float(t.total_value) if t.total_value is not None else None,
            is_open_market=t.is_open_market,
            is_10b5_1=t.is_10b5_1,
            filing_url=t.filing_url,
        )
        for t in tx_rows
    ]

    return InsiderSummaryResponse(
        entity_id=entity_id,
        signals=signals,
        net_shares_30d=float(latest_signal.net_shares_30d) if latest_signal and latest_signal.net_shares_30d is not None else None,
        net_value_30d=float(latest_signal.net_value_30d) if latest_signal and latest_signal.net_value_30d is not None else None,
        net_shares_90d=float(latest_signal.net_shares_90d) if latest_signal and latest_signal.net_shares_90d is not None else None,
        net_value_90d=float(latest_signal.net_value_90d) if latest_signal and latest_signal.net_value_90d is not None else None,
        recent_transactions=recent_txs,
    )


@router.get(
    "/filings/{entity_id}/insiders/transactions",
    response_model=list[InsiderTransactionResponse],
)
async def get_insider_transactions(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    from_date: date | None = Query(None, description="Start date"),
    to_date: date | None = Query(None, description="End date"),
    type: str | None = Query(None, description="Transaction type filter (BUY, SELL, EXERCISE)"),
):
    """Get insider transactions for an entity."""
    await _get_entity(session, entity_id)

    stmt = select(InsiderTransactionP3).where(
        InsiderTransactionP3.entity_id == entity_id
    )

    if from_date:
        stmt = stmt.where(InsiderTransactionP3.transaction_date >= from_date)
    if to_date:
        stmt = stmt.where(InsiderTransactionP3.transaction_date <= to_date)
    if type:
        stmt = stmt.where(InsiderTransactionP3.transaction_type == type)

    stmt = stmt.order_by(InsiderTransactionP3.transaction_date.desc()).limit(100)
    result = await session.execute(stmt)
    rows = result.scalars().all()

    return [
        InsiderTransactionResponse(
            id=t.id,
            entity_id=t.entity_id,
            reporting_person=t.reporting_person,
            relationship=t.relationship,
            transaction_type=t.transaction_type,
            transaction_date=t.transaction_date,
            shares=float(t.shares) if t.shares is not None else None,
            price_per_share=float(t.price_per_share) if t.price_per_share is not None else None,
            total_value=float(t.total_value) if t.total_value is not None else None,
            is_open_market=t.is_open_market,
            is_10b5_1=t.is_10b5_1,
            filing_url=t.filing_url,
        )
        for t in rows
    ]


@router.get(
    "/filings/{entity_id}/insiders/signal",
    response_model=list[InsiderSignalResponse],
)
async def get_insider_signals(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get computed insider signals for an entity."""
    await _get_entity(session, entity_id)

    result = await session.execute(
        select(InsiderSignal)
        .where(InsiderSignal.entity_id == entity_id)
        .order_by(InsiderSignal.signal_date.desc())
        .limit(20)
    )
    rows = result.scalars().all()

    return [
        InsiderSignalResponse(
            signal_type=s.signal_type,
            signal_strength=s.signal_strength,
            signal_date=s.signal_date,
            detail=s.detail,
        )
        for s in rows
    ]


@router.post(
    "/filings/insiders/screen",
    response_model=InsiderScreenResponse,
)
async def screen_insiders(
    body: InsiderScreenRequest,
    session: AsyncSession = Depends(get_session),
):
    """Screen entities by insider trading signals."""
    stmt = select(InsiderSignal)

    if body.min_signal_strength is not None:
        stmt = stmt.where(InsiderSignal.signal_strength >= body.min_signal_strength)
    if body.signal_types:
        stmt = stmt.where(InsiderSignal.signal_type.in_(body.signal_types))
    if body.min_net_value_90d is not None:
        stmt = stmt.where(InsiderSignal.net_value_90d >= body.min_net_value_90d)

    stmt = stmt.order_by(InsiderSignal.signal_strength.desc()).limit(100)
    result = await session.execute(stmt)
    signal_rows = result.scalars().all()

    # Group by entity_id
    entity_signals: dict[uuid.UUID, list[InsiderSignal]] = {}
    for s in signal_rows:
        entity_signals.setdefault(s.entity_id, []).append(s)

    results = []
    for eid, signals in entity_signals.items():
        latest = signals[0]

        # Optionally filter by relationship
        if body.relationship_filter:
            # Fetch recent transactions with matching relationship
            tx_result = await session.execute(
                select(InsiderTransactionP3)
                .where(
                    and_(
                        InsiderTransactionP3.entity_id == eid,
                        InsiderTransactionP3.relationship.in_(body.relationship_filter),
                    )
                )
                .order_by(InsiderTransactionP3.transaction_date.desc())
                .limit(10)
            )
            tx_rows = tx_result.scalars().all()
        else:
            tx_result = await session.execute(
                select(InsiderTransactionP3)
                .where(InsiderTransactionP3.entity_id == eid)
                .order_by(InsiderTransactionP3.transaction_date.desc())
                .limit(10)
            )
            tx_rows = tx_result.scalars().all()

        results.append(
            InsiderSummaryResponse(
                entity_id=eid,
                signals=[
                    InsiderSignalResponse(
                        signal_type=s.signal_type,
                        signal_strength=s.signal_strength,
                        signal_date=s.signal_date,
                        detail=s.detail,
                    )
                    for s in signals
                ],
                net_shares_30d=float(latest.net_shares_30d) if latest.net_shares_30d is not None else None,
                net_value_30d=float(latest.net_value_30d) if latest.net_value_30d is not None else None,
                net_shares_90d=float(latest.net_shares_90d) if latest.net_shares_90d is not None else None,
                net_value_90d=float(latest.net_value_90d) if latest.net_value_90d is not None else None,
                recent_transactions=[
                    InsiderTransactionResponse(
                        id=t.id,
                        entity_id=t.entity_id,
                        reporting_person=t.reporting_person,
                        relationship=t.relationship,
                        transaction_type=t.transaction_type,
                        transaction_date=t.transaction_date,
                        shares=float(t.shares) if t.shares is not None else None,
                        price_per_share=float(t.price_per_share) if t.price_per_share is not None else None,
                        total_value=float(t.total_value) if t.total_value is not None else None,
                        is_open_market=t.is_open_market,
                        is_10b5_1=t.is_10b5_1,
                        filing_url=t.filing_url,
                    )
                    for t in tx_rows
                ],
            )
        )

    return InsiderScreenResponse(results=results, total_count=len(results))
