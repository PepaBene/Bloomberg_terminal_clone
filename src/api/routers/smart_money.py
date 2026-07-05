"""Smart-Money / Notable-Filer tracking API endpoints.

Follow notable investors, corporate insiders, and politicians (Michael Burry,
Jamie Dimon, Nancy Pelosi, ...) using only FREE public filings already
ingested by the platform (13F-HR, Form 4, STOCK Act PTRs).
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_pagination, get_session
from src.engines.smart_money import (
    aggregate_smart_money_flow,
    build_filer_profile,
    classify_political_trade,
    compute_follow_signal,
    detect_consensus,
    find_investor,
    load_notable_investors,
)
from src.models.congressional_trades import CongressionalTrade
from src.models.ownership import InstitutionalHolding, InstitutionProfile
from src.models.security import Security, SecurityIdentifier
from src.schemas.common import PaginationParams
from src.schemas.smart_money import (
    ConsensusRow,
    CongressionalTradeResponse,
    FilerProfileResponse,
    NotableInvestorResponse,
    SmartMoneyFlowRow,
)

router = APIRouter(prefix="/smart-money", tags=["Smart Money"])

# Registry is static config; load once at import (same lifecycle as reference data).
_REGISTRY = load_notable_investors()


# ── Registry endpoints ──────────────────────────────────────────────────

@router.get("/investors", response_model=list[NotableInvestorResponse])
async def list_notable_investors(
    category: str | None = Query(None, description="GURU_13F / INSIDER_FORM4 / POLITICIAN"),
):
    """List the curated registry of notable people you can follow."""
    investors = _REGISTRY
    if category:
        investors = [i for i in investors if i.get("category") == category.upper()]
    return investors


@router.get("/investors/{key}", response_model=NotableInvestorResponse)
async def get_notable_investor(key: str):
    """Resolve a registry entry by key or display name."""
    entry = find_investor(_REGISTRY, key)
    if not entry:
        raise HTTPException(status_code=404, detail=f"Notable investor '{key}' not found")
    return entry


# ── Helpers ─────────────────────────────────────────────────────────────

async def _ticker_map(session: AsyncSession, security_ids: list[uuid.UUID]) -> dict[uuid.UUID, str]:
    """Map security_id → ticker via SecurityIdentifier (best-effort)."""
    if not security_ids:
        return {}
    result = await session.execute(
        select(SecurityIdentifier.security_id, SecurityIdentifier.identifier_value).where(
            SecurityIdentifier.security_id.in_(security_ids),
            SecurityIdentifier.identifier_type == "TICKER",
        )
    )
    return {row[0]: row[1] for row in result.all()}


async def _holdings_for_report(
    session: AsyncSession, institution_id: uuid.UUID, report_date
) -> list[dict]:
    """Fetch a 13F manager's holdings for one report date as engine-ready dicts."""
    rows = (
        await session.execute(
            select(InstitutionalHolding, Security.name)
            .join(Security, Security.security_id == InstitutionalHolding.security_id)
            .where(
                InstitutionalHolding.institution_id == institution_id,
                InstitutionalHolding.report_date == report_date,
            )
        )
    ).all()
    sec_ids = [h.security_id for h, _ in rows]
    tickers = await _ticker_map(session, sec_ids)
    return [
        {
            "ticker": tickers.get(h.security_id),
            "name": name,
            "security_id": str(h.security_id),
            "market_value": float(h.market_value) if h.market_value is not None else None,
            "percent_of_portfolio": float(h.percent_of_portfolio)
            if h.percent_of_portfolio is not None
            else None,
            "shares": float(h.shares_held) if h.shares_held is not None else None,
        }
        for h, name in rows
    ]


async def _build_guru_profile(session: AsyncSession, entry: dict) -> dict:
    """Build a 13F filer profile from the two most recent report dates."""
    cik = entry.get("cik")
    inst = None
    if cik:
        inst = (
            await session.execute(
                select(InstitutionProfile).where(InstitutionProfile.cik == cik)
            )
        ).scalar_one_or_none()
    if inst is None:
        inst = (
            await session.execute(
                select(InstitutionProfile).where(
                    InstitutionProfile.institution_name.ilike(f"%{entry.get('vehicle', '')}%")
                )
            )
        ).scalars().first()
    if inst is None:
        raise HTTPException(
            status_code=404,
            detail=f"No 13F filer found for {entry['display_name']} (vehicle: {entry.get('vehicle')})",
        )

    dates = (
        await session.execute(
            select(InstitutionalHolding.report_date)
            .where(InstitutionalHolding.institution_id == inst.institution_id)
            .distinct()
            .order_by(InstitutionalHolding.report_date.desc())
            .limit(2)
        )
    ).scalars().all()
    if not dates:
        raise HTTPException(status_code=404, detail="No 13F holdings on file for this filer")

    current = await _holdings_for_report(session, inst.institution_id, dates[0])
    prior = await _holdings_for_report(session, inst.institution_id, dates[1]) if len(dates) > 1 else []
    return build_filer_profile(entry["display_name"], entry["category"], current, prior)


# ── Profile / activity endpoints ────────────────────────────────────────

@router.get("/filers/{key}/profile", response_model=FilerProfileResponse)
async def get_filer_profile(key: str, session: AsyncSession = Depends(get_session)):
    """Quarter-over-quarter 13F activity profile for a notable manager (e.g. Burry)."""
    entry = find_investor(_REGISTRY, key)
    if not entry:
        raise HTTPException(status_code=404, detail=f"Notable investor '{key}' not found")
    if entry["category"] != "GURU_13F":
        raise HTTPException(
            status_code=400,
            detail=f"{entry['display_name']} is a {entry['category']}; 13F profiles only apply to GURU_13F filers",
        )
    return await _build_guru_profile(session, entry)


@router.get("/congress", response_model=list[CongressionalTradeResponse])
async def list_congressional_trades(
    session: AsyncSession = Depends(get_session),
    pagination: PaginationParams = Depends(get_pagination),
    politician: str | None = Query(None, description="Filter by politician name (e.g. Nancy Pelosi)"),
    ticker: str | None = Query(None, description="Filter by ticker"),
):
    """List congressional STOCK Act trades, enriched with size/lag/conflict flags."""
    query = select(CongressionalTrade)
    if politician:
        query = query.where(CongressionalTrade.politician_name.ilike(f"%{politician}%"))
    if ticker:
        query = query.where(CongressionalTrade.ticker == ticker.upper())
    query = query.order_by(CongressionalTrade.transaction_date.desc())
    offset = (pagination.page - 1) * pagination.page_size
    query = query.offset(offset).limit(pagination.page_size)

    rows = (await session.execute(query)).scalars().all()
    enriched = []
    for t in rows:
        base = {
            "transaction_type": t.transaction_type,
            "transaction_date": t.transaction_date,
            "disclosure_date": t.disclosure_date,
            "amount_range_low": float(t.amount_range_low) if t.amount_range_low is not None else None,
            "amount_range_high": float(t.amount_range_high) if t.amount_range_high is not None else None,
            "sector": None,
        }
        flags = classify_political_trade(base, committees=t.committees or [])
        enriched.append(
            CongressionalTradeResponse(
                id=t.id,
                politician_name=t.politician_name,
                chamber=t.chamber,
                party=t.party,
                state=t.state,
                ticker=t.ticker,
                asset_description=t.asset_description,
                asset_type=t.asset_type,
                transaction_type=t.transaction_type,
                transaction_date=t.transaction_date,
                disclosure_date=t.disclosure_date,
                amount_range_low=base["amount_range_low"],
                amount_range_high=base["amount_range_high"],
                midpoint_amount=flags["midpoint_amount"],
                size_bucket=flags["size_bucket"],
                owner=t.owner,
                disclosure_lag_days=flags["disclosure_lag_days"],
                is_late_disclosure=flags["is_late_disclosure"],
                committee_conflict=flags["committee_conflict"],
                conflict_committee=flags["conflict_committee"],
                source_url=t.source_url,
            )
        )
    return enriched


@router.get("/consensus", response_model=list[ConsensusRow])
async def smart_money_consensus(session: AsyncSession = Depends(get_session)):
    """Securities multiple tracked 13F managers are accumulating or exiting."""
    profiles = []
    for entry in _REGISTRY:
        if entry.get("category") != "GURU_13F":
            continue
        try:
            profiles.append(await _build_guru_profile(session, entry))
        except HTTPException:
            continue  # filer has no data ingested yet — skip gracefully
    return detect_consensus(profiles)


@router.get("/flow/{ticker}", response_model=list[SmartMoneyFlowRow])
async def smart_money_flow(ticker: str, session: AsyncSession = Depends(get_session)):
    """Net smart-money pressure on a ticker across all tracked 13F filers."""
    ticker = ticker.upper()
    events: list[dict] = []
    for entry in _REGISTRY:
        if entry.get("category") != "GURU_13F":
            continue
        try:
            profile = await _build_guru_profile(session, entry)
        except HTTPException:
            continue
        buckets = [
            ("NEW", profile.get("new_positions", [])),
            ("ADD", profile.get("increased_positions", [])),
            ("EXIT", profile.get("exited_positions", [])),
            ("TRIM", profile.get("decreased_positions", [])),
        ]
        for action, holdings in buckets:
            for h in holdings:
                if (h.get("ticker") or "").upper() != ticker:
                    continue
                signal = compute_follow_signal(
                    {
                        "category": "GURU_13F",
                        "action": action,
                        "conviction": h.get("conviction", 50),
                    }
                )
                events.append(
                    {
                        "ticker": ticker,
                        "display_name": entry["display_name"],
                        "direction": signal["direction"],
                        "strength": signal["strength"],
                    }
                )
    return aggregate_smart_money_flow(events)
