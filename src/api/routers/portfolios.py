"""Portfolio Management API endpoints (Pillar 4 Phase 1)."""

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_optional_user, get_session
from src.engines import csv_upload_engine, nav_engine
from src.engines.portfolio_parser import parse_csv, match_holdings_to_securities
from src.models.portfolio import Portfolio
from src.models.position import Position
from src.models.security import EODPrice, SecurityIdentifier
from src.models.transaction import Transaction
from src.models.nav_snapshot import NAVSnapshot, CorporateActionQueue
from src.schemas.portfolio import (
    PortfolioCreateRequest,
    PortfolioListResponse,
    PortfolioResponse,
    PortfolioUpdateRequest,
)
from src.schemas.position import PositionAddRequest, PositionResponse, PositionUpdateRequest
from src.schemas.transaction_schema import (
    TransactionCreateRequest,
    TransactionListResponse,
    TransactionResponse,
)
from src.schemas.nav import (
    NAVHistoryEntry,
    NAVHistoryResponse,
    NAVResponse,
    NAVSnapshotResponse,
)
from src.schemas.portfolio_upload_schema import (
    UploadCommitResponse,
    UploadPreviewResponse,
    UploadPreviewPosition,
)
from src.schemas.corporate_action_schema import CorporateActionApplyRequest, CorporateActionResponse

router = APIRouter(tags=["Portfolio Management"])

# Fallback identity used only when no Bearer token is present and REQUIRE_AUTH
# is not set. Real authenticated users are resolved via ``get_optional_user``.
# When REQUIRE_AUTH is off, requests without a Bearer token resolve to
# this fallback identity. The audit's intent (P4-R-001) was to eliminate
# the previous always-shared "default_user" — but for unauthenticated
# anonymous traffic we still need a single bucket so existing data and
# tests keep working. Real authenticated callers replace this with the
# JWT-derived ``sub`` claim.
ANONYMOUS_USER = "default_user"


def _resolve_user(user: str | None) -> str:
    return user or ANONYMOUS_USER


# ── Upload request bodies ─────────────────────────────────────────────


class UploadPreviewRequest(BaseModel):
    csv_content: str


class UploadCommitRequest(BaseModel):
    csv_content: str
    portfolio_name: str


# ── Helpers ──────────────────────────────────────────────────────────


async def _get_portfolio(session: AsyncSession, portfolio_id: uuid.UUID) -> Portfolio:
    result = await session.execute(
        select(Portfolio).where(Portfolio.id == portfolio_id)
    )
    portfolio = result.scalar_one_or_none()
    if not portfolio:
        raise HTTPException(status_code=404, detail="Portfolio not found")
    return portfolio


async def _get_position(session: AsyncSession, position_id: uuid.UUID) -> Position:
    result = await session.execute(
        select(Position).where(Position.id == position_id)
    )
    position = result.scalar_one_or_none()
    if not position:
        raise HTTPException(status_code=404, detail="Position not found")
    return position


async def _resolve_security_id(session: AsyncSession, ticker: str) -> uuid.UUID | None:
    result = await session.execute(
        select(SecurityIdentifier.security_id).where(
            SecurityIdentifier.identifier_type == "TICKER",
            SecurityIdentifier.identifier_value == ticker.upper(),
        )
    )
    return result.scalar_one_or_none()


async def _latest_prices(
    session: AsyncSession, security_id: uuid.UUID
) -> tuple[float | None, float | None]:
    """Return (latest_close, prior_close) for a security from real EOD prices."""
    rows = (
        await session.execute(
            select(EODPrice.close)
            .where(EODPrice.security_id == security_id, EODPrice.close.isnot(None))
            .order_by(EODPrice.price_date.desc())
            .limit(2)
        )
    ).scalars().all()
    latest = float(rows[0]) if rows else None
    prior = float(rows[1]) if len(rows) > 1 else None
    return latest, prior


async def _refresh_portfolio_positions(session: AsyncSession, portfolio_id: uuid.UUID) -> None:
    """Recompute and persist market_value/unrealized_pnl/weight/closing_price/
    day_change_pct for every open position, from real EOD prices via
    nav_engine.compute_position_valuation().

    Previously nothing ever called this engine in production — positions
    kept these columns permanently null, so portfolio NAV was
    cash-balance-only regardless of what was actually held.
    """
    portfolio = await _get_portfolio(session, portfolio_id)
    result = await session.execute(
        select(Position).where(
            Position.portfolio_id == portfolio_id,
            Position.status == "OPEN",
        )
    )
    positions = list(result.scalars().all())
    if not positions:
        return

    for pos in positions:
        if pos.security_id is None:
            pos.security_id = await _resolve_security_id(session, pos.ticker)

        latest_close, prior_close = (
            await _latest_prices(session, pos.security_id)
            if pos.security_id is not None
            else (None, None)
        )
        if latest_close is None:
            # No real price available — leave existing stored values as-is
            # rather than fabricating a valuation.
            continue

        val = nav_engine.compute_position_valuation(
            ticker=pos.ticker,
            shares=float(pos.shares or 0),
            cost_basis_total=float(pos.cost_basis_total or 0),
            cost_basis_per_share=float(pos.cost_basis_per_share or 0),
            closing_price=latest_close,
            prior_close=prior_close,
        )
        pos.closing_price = Decimal(str(latest_close))
        pos.market_value = Decimal(str(round(val.market_value, 2)))
        pos.unrealized_pnl = Decimal(str(round(val.unrealized_pnl, 2)))
        pos.unrealized_pnl_pct = Decimal(str(val.unrealized_pnl_pct))
        pos.day_change_pct = (
            Decimal(str(val.day_change_pct)) if val.day_change_pct is not None else None
        )

    total_market_value = sum(
        float(pos.market_value) for pos in positions if pos.market_value is not None
    )
    nav = total_market_value + float(portfolio.current_cash or 0)
    if nav > 0:
        for pos in positions:
            if pos.market_value is not None:
                pos.weight = Decimal(str(round(float(pos.market_value) / nav, 6)))

    await session.commit()


# ══════════════════════════════════════════════════════════════════════
# Upload (STATIC — must be before /{id} routes)
# ══════════════════════════════════════════════════════════════════════


@router.post("/portfolios/upload/preview", response_model=UploadPreviewResponse)
async def upload_preview(
    body: UploadPreviewRequest,
    session: AsyncSession = Depends(get_session),
):
    """Preview a portfolio upload before committing."""
    # Step 1: Parse CSV rows via the upload engine
    rows = csv_upload_engine.parse_csv_holdings(body.csv_content)
    total_rows = len(rows)

    # Step 2: Validate required fields (ticker, shares)
    valid_rows, req_errors = csv_upload_engine.validate_required_fields(rows)

    # Step 3: Normalize ticker symbols
    normalized = csv_upload_engine.normalize_tickers(valid_rows)

    # Step 4: Detect duplicates (informational, not blocking)
    _duplicates = csv_upload_engine.detect_duplicates(normalized)

    # Step 5: Validate numeric fields
    final_valid, num_errors = csv_upload_engine.validate_numeric_fields(normalized)
    all_errors = req_errors + num_errors

    # Step 6: Build position list from validated rows
    positions = csv_upload_engine.build_position_list(final_valid)

    # Step 7: Use portfolio_parser to match holdings to securities
    holdings = parse_csv(body.csv_content)
    match_results = match_holdings_to_securities(holdings)

    matched_count = sum(1 for m in match_results if m.status == "MATCHED")
    unmatched_count = sum(1 for m in match_results if m.status != "MATCHED")

    # Build a lookup of matched tickers for the preview
    matched_tickers = {
        m.identifier.upper()
        for m in match_results
        if m.status == "MATCHED" and m.identifier
    }

    preview_positions = [
        UploadPreviewPosition(
            ticker=p["ticker"],
            shares=p["shares"],
            cost_basis_per_share=p["cost_basis_per_share"],
            matched=p["ticker"].upper() in matched_tickers,
        )
        for p in positions
    ]

    return UploadPreviewResponse(
        total_rows=total_rows,
        matched=matched_count,
        unmatched=unmatched_count,
        errors=len(all_errors),
        preview_positions=preview_positions,
    )


@router.post("/portfolios/upload/commit", response_model=UploadCommitResponse)
async def upload_commit(
    body: UploadCommitRequest,
    session: AsyncSession = Depends(get_session),
    user: str | None = Depends(get_optional_user),
):
    """Commit a previewed portfolio upload."""
    user_id = _resolve_user(user)
    # Parse and validate the CSV through the engine pipeline
    rows = csv_upload_engine.parse_csv_holdings(body.csv_content)
    valid_rows, _req_errors = csv_upload_engine.validate_required_fields(rows)
    normalized = csv_upload_engine.normalize_tickers(valid_rows)
    final_valid, _num_errors = csv_upload_engine.validate_numeric_fields(normalized)
    positions = csv_upload_engine.build_position_list(final_valid)

    if not positions:
        raise HTTPException(
            status_code=400,
            detail="No valid positions found in CSV",
        )

    # Check for duplicate portfolio name
    existing = await session.execute(
        select(Portfolio).where(
            Portfolio.user_id == user_id,
            Portfolio.portfolio_name == body.portfolio_name,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Portfolio name already exists")

    # Create the portfolio record
    portfolio = Portfolio(
        id=uuid.uuid4(),
        user_id=user_id,
        portfolio_name=body.portfolio_name,
        portfolio_type="EQUITY",
        inception_date=date.today(),
        initial_cash=Decimal("0"),
        current_cash=Decimal("0"),
    )
    session.add(portfolio)
    await session.flush()

    # Create position records from the validated rows
    positions_created = 0
    for p in positions:
        shares = Decimal(str(p["shares"]))
        cost_basis = Decimal(str(p["cost_basis_per_share"]))
        position = Position(
            id=uuid.uuid4(),
            portfolio_id=portfolio.id,
            ticker=p["ticker"],
            status="OPEN",
            shares=shares,
            cost_basis_per_share=cost_basis,
            cost_basis_total=shares * cost_basis,
            first_acquisition_date=date.today(),
            created_by=user_id,
        )
        session.add(position)
        positions_created += 1

    await session.commit()
    await _refresh_portfolio_positions(session, portfolio.id)

    return UploadCommitResponse(
        portfolio_id=portfolio.id,
        positions_created=positions_created,
        status="COMMITTED",
    )


# ══════════════════════════════════════════════════════════════════════
# Portfolio CRUD
# ══════════════════════════════════════════════════════════════════════


@router.post("/portfolios", response_model=PortfolioResponse, status_code=201)
async def create_portfolio(
    body: PortfolioCreateRequest,
    session: AsyncSession = Depends(get_session),
    user: str | None = Depends(get_optional_user),
):
    """Create a new portfolio."""
    user_id = _resolve_user(user)
    # Check for duplicate name
    existing = await session.execute(
        select(Portfolio).where(
            Portfolio.user_id == user_id,
            Portfolio.portfolio_name == body.portfolio_name,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Portfolio name already exists")

    portfolio = Portfolio(
        id=uuid.uuid4(),
        user_id=user_id,
        portfolio_name=body.portfolio_name,
        portfolio_type=body.portfolio_type,
        benchmark_id=body.benchmark_id,
        inception_date=body.inception_date,
        initial_cash=body.initial_cash,
        current_cash=body.initial_cash,
        tags=body.tags,
        notes=body.notes,
    )
    session.add(portfolio)
    await session.commit()
    await session.refresh(portfolio)

    return PortfolioResponse(
        id=portfolio.id,
        user_id=portfolio.user_id,
        portfolio_name=portfolio.portfolio_name,
        portfolio_type=portfolio.portfolio_type,
        benchmark_id=portfolio.benchmark_id,
        inception_date=portfolio.inception_date,
        base_currency=portfolio.base_currency,
        initial_cash=portfolio.initial_cash,
        current_cash=portfolio.current_cash,
        status=portfolio.status,
        tags=portfolio.tags,
        notes=portfolio.notes,
    )


@router.get("/portfolios", response_model=list[PortfolioResponse])
async def list_portfolios(
    session: AsyncSession = Depends(get_session),
    user: str | None = Depends(get_optional_user),
):
    """List all active portfolios for the current user."""
    user_id = _resolve_user(user)
    result = await session.execute(
        select(Portfolio)
        .where(Portfolio.user_id == user_id, Portfolio.status != "ARCHIVED")
        .order_by(Portfolio.portfolio_name)
    )
    rows = result.scalars().all()
    return [
        PortfolioResponse(
            id=p.id,
            user_id=p.user_id,
            portfolio_name=p.portfolio_name,
            portfolio_type=p.portfolio_type,
            benchmark_id=p.benchmark_id,
            inception_date=p.inception_date,
            base_currency=p.base_currency,
            initial_cash=p.initial_cash,
            current_cash=p.current_cash,
            status=p.status,
            tags=p.tags,
            notes=p.notes,
        )
        for p in rows
    ]


@router.get("/portfolios/{portfolio_id}", response_model=PortfolioResponse)
async def get_portfolio(
    portfolio_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get a portfolio by ID."""
    p = await _get_portfolio(session, portfolio_id)
    return PortfolioResponse(
        id=p.id,
        user_id=p.user_id,
        portfolio_name=p.portfolio_name,
        portfolio_type=p.portfolio_type,
        benchmark_id=p.benchmark_id,
        inception_date=p.inception_date,
        base_currency=p.base_currency,
        initial_cash=p.initial_cash,
        current_cash=p.current_cash,
        status=p.status,
        tags=p.tags,
        notes=p.notes,
    )


@router.put("/portfolios/{portfolio_id}", response_model=PortfolioResponse)
async def update_portfolio(
    portfolio_id: uuid.UUID,
    body: PortfolioUpdateRequest,
    session: AsyncSession = Depends(get_session),
):
    """Update portfolio fields."""
    p = await _get_portfolio(session, portfolio_id)

    if body.portfolio_name is not None:
        p.portfolio_name = body.portfolio_name
    if body.benchmark_id is not None:
        p.benchmark_id = body.benchmark_id
    if body.status is not None:
        p.status = body.status
    if body.tags is not None:
        p.tags = body.tags
    if body.notes is not None:
        p.notes = body.notes

    await session.commit()
    await session.refresh(p)

    return PortfolioResponse(
        id=p.id,
        user_id=p.user_id,
        portfolio_name=p.portfolio_name,
        portfolio_type=p.portfolio_type,
        benchmark_id=p.benchmark_id,
        inception_date=p.inception_date,
        base_currency=p.base_currency,
        initial_cash=p.initial_cash,
        current_cash=p.current_cash,
        status=p.status,
        tags=p.tags,
        notes=p.notes,
    )


@router.delete("/portfolios/{portfolio_id}", response_model=PortfolioResponse)
async def delete_portfolio(
    portfolio_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Soft-delete a portfolio (set status=ARCHIVED)."""
    p = await _get_portfolio(session, portfolio_id)
    p.status = "ARCHIVED"
    await session.commit()
    await session.refresh(p)

    return PortfolioResponse(
        id=p.id,
        user_id=p.user_id,
        portfolio_name=p.portfolio_name,
        portfolio_type=p.portfolio_type,
        benchmark_id=p.benchmark_id,
        inception_date=p.inception_date,
        base_currency=p.base_currency,
        initial_cash=p.initial_cash,
        current_cash=p.current_cash,
        status=p.status,
        tags=p.tags,
        notes=p.notes,
    )


@router.post("/portfolios/{portfolio_id}/clone", response_model=PortfolioResponse, status_code=201)
async def clone_portfolio(
    portfolio_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Clone a portfolio with its positions."""
    source = await _get_portfolio(session, portfolio_id)

    clone = Portfolio(
        id=uuid.uuid4(),
        user_id=source.user_id,
        portfolio_name=f"{source.portfolio_name} (Clone)",
        portfolio_type=source.portfolio_type,
        benchmark_id=source.benchmark_id,
        inception_date=date.today(),
        base_currency=source.base_currency,
        initial_cash=source.current_cash,
        current_cash=source.current_cash,
        tags=source.tags,
        notes=f"Cloned from {source.portfolio_name}",
    )
    session.add(clone)
    await session.flush()

    # Clone open positions
    pos_result = await session.execute(
        select(Position).where(
            Position.portfolio_id == source.id,
            Position.status == "OPEN",
        )
    )
    for pos in pos_result.scalars().all():
        new_pos = Position(
            id=uuid.uuid4(),
            portfolio_id=clone.id,
            security_id=pos.security_id,
            ticker=pos.ticker,
            status="OPEN",
            shares=pos.shares,
            cost_basis_total=pos.cost_basis_total,
            cost_basis_per_share=pos.cost_basis_per_share,
            first_acquisition_date=pos.first_acquisition_date,
            # P4-M-027: this is a clone, not a fresh manual add -- carry
            # over the source position's audit-trail owner rather than
            # attributing the copy to whoever happened to call /clone.
            created_by=pos.created_by,
        )
        session.add(new_pos)
    await session.commit()
    await _refresh_portfolio_positions(session, clone.id)
    await session.refresh(clone)

    return PortfolioResponse(
        id=clone.id,
        user_id=clone.user_id,
        portfolio_name=clone.portfolio_name,
        portfolio_type=clone.portfolio_type,
        benchmark_id=clone.benchmark_id,
        inception_date=clone.inception_date,
        base_currency=clone.base_currency,
        initial_cash=clone.initial_cash,
        current_cash=clone.current_cash,
        status=clone.status,
        tags=clone.tags,
        notes=clone.notes,
    )


# ══════════════════════════════════════════════════════════════════════
# Positions
# ══════════════════════════════════════════════════════════════════════


@router.get(
    "/portfolios/{portfolio_id}/positions",
    response_model=list[PositionResponse],
)
async def list_positions(
    portfolio_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """List all open positions for a portfolio."""
    await _get_portfolio(session, portfolio_id)
    await _refresh_portfolio_positions(session, portfolio_id)
    result = await session.execute(
        select(Position).where(
            Position.portfolio_id == portfolio_id,
            Position.status == "OPEN",
        ).order_by(Position.ticker)
    )
    rows = result.scalars().all()
    return [
        PositionResponse(
            id=pos.id,
            portfolio_id=pos.portfolio_id,
            security_id=pos.security_id,
            ticker=pos.ticker,
            status=pos.status,
            shares=float(pos.shares) if pos.shares is not None else None,
            cost_basis_total=float(pos.cost_basis_total) if pos.cost_basis_total is not None else None,
            cost_basis_per_share=float(pos.cost_basis_per_share) if pos.cost_basis_per_share is not None else None,
            first_acquisition_date=pos.first_acquisition_date,
            market_value=float(pos.market_value) if pos.market_value is not None else None,
            unrealized_pnl=float(pos.unrealized_pnl) if pos.unrealized_pnl is not None else None,
            unrealized_pnl_pct=float(pos.unrealized_pnl_pct) if pos.unrealized_pnl_pct is not None else None,
            weight=float(pos.weight) if pos.weight is not None else None,
            closing_price=float(pos.closing_price) if pos.closing_price is not None else None,
            day_change_pct=float(pos.day_change_pct) if pos.day_change_pct is not None else None,
            notes=pos.notes,
        )
        for pos in rows
    ]


@router.post(
    "/portfolios/{portfolio_id}/positions",
    response_model=PositionResponse,
    status_code=201,
)
async def add_position(
    portfolio_id: uuid.UUID,
    body: PositionAddRequest,
    session: AsyncSession = Depends(get_session),
    user: str | None = Depends(get_optional_user),
):
    """Add or update a position in the portfolio."""
    user_id = _resolve_user(user)
    await _get_portfolio(session, portfolio_id)

    # Check for existing open position with same ticker
    existing_result = await session.execute(
        select(Position).where(
            Position.portfolio_id == portfolio_id,
            Position.ticker == body.ticker,
            Position.status == "OPEN",
        )
    )
    existing = existing_result.scalar_one_or_none()

    if existing:
        # Update existing position (average in)
        old_total = (existing.shares or Decimal("0")) * (existing.cost_basis_per_share or Decimal("0"))
        new_total = body.shares * body.cost_basis_per_share
        total_shares = (existing.shares or Decimal("0")) + body.shares
        # Guard against rounding-artifact share counts that pass a truthy check
        # but produce nonsensical cost basis on division.
        if total_shares > Decimal("0.000001"):
            avg_cost = (old_total + new_total) / total_shares
        else:
            avg_cost = Decimal("0")

        existing.shares = total_shares
        existing.cost_basis_per_share = avg_cost
        existing.cost_basis_total = total_shares * avg_cost
        await session.commit()
        await session.refresh(existing)
        pos = existing
    else:
        cost_total = body.shares * body.cost_basis_per_share
        pos = Position(
            id=uuid.uuid4(),
            portfolio_id=portfolio_id,
            ticker=body.ticker,
            status="OPEN",
            shares=body.shares,
            cost_basis_per_share=body.cost_basis_per_share,
            cost_basis_total=cost_total,
            first_acquisition_date=body.acquisition_date or date.today(),
            notes=body.notes,
            created_by=user_id,
        )
        session.add(pos)
        await session.commit()
        await session.refresh(pos)

    await _refresh_portfolio_positions(session, portfolio_id)
    await session.refresh(pos)

    return PositionResponse(
        id=pos.id,
        portfolio_id=pos.portfolio_id,
        security_id=pos.security_id,
        ticker=pos.ticker,
        status=pos.status,
        shares=float(pos.shares) if pos.shares is not None else None,
        cost_basis_total=float(pos.cost_basis_total) if pos.cost_basis_total is not None else None,
        cost_basis_per_share=float(pos.cost_basis_per_share) if pos.cost_basis_per_share is not None else None,
        first_acquisition_date=pos.first_acquisition_date,
        market_value=float(pos.market_value) if pos.market_value is not None else None,
        unrealized_pnl=float(pos.unrealized_pnl) if pos.unrealized_pnl is not None else None,
        unrealized_pnl_pct=float(pos.unrealized_pnl_pct) if pos.unrealized_pnl_pct is not None else None,
        weight=float(pos.weight) if pos.weight is not None else None,
        closing_price=float(pos.closing_price) if pos.closing_price is not None else None,
        day_change_pct=float(pos.day_change_pct) if pos.day_change_pct is not None else None,
        notes=pos.notes,
    )


@router.put(
    "/portfolios/{portfolio_id}/positions/{position_id}",
    response_model=PositionResponse,
)
async def update_position(
    portfolio_id: uuid.UUID,
    position_id: uuid.UUID,
    body: PositionUpdateRequest,
    session: AsyncSession = Depends(get_session),
):
    """Update a position."""
    await _get_portfolio(session, portfolio_id)
    pos = await _get_position(session, position_id)

    if body.shares is not None:
        pos.shares = body.shares
    if body.cost_basis_per_share is not None:
        pos.cost_basis_per_share = body.cost_basis_per_share
    if body.notes is not None:
        pos.notes = body.notes

    # Recalculate cost basis total
    if pos.shares is not None and pos.cost_basis_per_share is not None:
        pos.cost_basis_total = pos.shares * pos.cost_basis_per_share

    await session.commit()
    await session.refresh(pos)

    await _refresh_portfolio_positions(session, portfolio_id)
    await session.refresh(pos)

    return PositionResponse(
        id=pos.id,
        portfolio_id=pos.portfolio_id,
        security_id=pos.security_id,
        ticker=pos.ticker,
        status=pos.status,
        shares=float(pos.shares) if pos.shares is not None else None,
        cost_basis_total=float(pos.cost_basis_total) if pos.cost_basis_total is not None else None,
        cost_basis_per_share=float(pos.cost_basis_per_share) if pos.cost_basis_per_share is not None else None,
        first_acquisition_date=pos.first_acquisition_date,
        market_value=float(pos.market_value) if pos.market_value is not None else None,
        unrealized_pnl=float(pos.unrealized_pnl) if pos.unrealized_pnl is not None else None,
        unrealized_pnl_pct=float(pos.unrealized_pnl_pct) if pos.unrealized_pnl_pct is not None else None,
        weight=float(pos.weight) if pos.weight is not None else None,
        closing_price=float(pos.closing_price) if pos.closing_price is not None else None,
        day_change_pct=float(pos.day_change_pct) if pos.day_change_pct is not None else None,
        notes=pos.notes,
    )


@router.delete(
    "/portfolios/{portfolio_id}/positions/{position_id}",
    response_model=PositionResponse,
)
async def delete_position(
    portfolio_id: uuid.UUID,
    position_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Close a position (set status=CLOSED) and zero out stale market metrics."""
    await _get_portfolio(session, portfolio_id)
    pos = await _get_position(session, position_id)
    pos.status = "CLOSED"
    pos.shares = Decimal("0")
    # Clear stale aggregates so portfolio NAV stops summing closed-position state.
    pos.market_value = Decimal("0")
    pos.unrealized_pnl = Decimal("0")
    pos.unrealized_pnl_pct = Decimal("0")
    pos.weight = Decimal("0")
    await session.commit()
    await session.refresh(pos)

    return PositionResponse(
        id=pos.id,
        portfolio_id=pos.portfolio_id,
        security_id=pos.security_id,
        ticker=pos.ticker,
        status=pos.status,
        shares=pos.shares,
        cost_basis_total=pos.cost_basis_total,
        cost_basis_per_share=pos.cost_basis_per_share,
        first_acquisition_date=pos.first_acquisition_date,
        notes=pos.notes,
    )


# ══════════════════════════════════════════════════════════════════════
# Transactions
# ══════════════════════════════════════════════════════════════════════


@router.post(
    "/portfolios/{portfolio_id}/transactions",
    response_model=TransactionResponse,
    status_code=201,
)
async def create_transaction(
    portfolio_id: uuid.UUID,
    body: TransactionCreateRequest,
    session: AsyncSession = Depends(get_session),
    user: str | None = Depends(get_optional_user),
):
    """Record a BUY or SELL transaction with position + cash effects."""
    user_id = _resolve_user(user)
    portfolio = await _get_portfolio(session, portfolio_id)

    gross = body.shares * body.price_per_share
    commission = body.commission or Decimal("0")

    if body.transaction_type == "BUY":
        net_amount = gross + commission
        cash_impact = -net_amount
    elif body.transaction_type == "SELL":
        net_amount = gross - commission
        cash_impact = net_amount
    else:
        net_amount = gross
        cash_impact = Decimal("0")

    # Validate cash for BUY
    if body.transaction_type == "BUY":
        if portfolio.current_cash + cash_impact < 0:
            raise HTTPException(status_code=400, detail="Insufficient cash")

    # Validate shares for SELL
    if body.transaction_type == "SELL":
        pos_result = await session.execute(
            select(Position).where(
                Position.portfolio_id == portfolio_id,
                Position.ticker == body.ticker,
                Position.status == "OPEN",
            )
        )
        pos = pos_result.scalar_one_or_none()
        if not pos or (pos.shares or Decimal("0")) < body.shares:
            raise HTTPException(status_code=400, detail="Insufficient shares to sell")

    txn = Transaction(
        id=uuid.uuid4(),
        portfolio_id=portfolio_id,
        ticker=body.ticker,
        transaction_type=body.transaction_type,
        transaction_date=body.transaction_date,
        shares=body.shares,
        price_per_share=body.price_per_share,
        gross_amount=gross,
        commission=commission,
        net_amount=net_amount,
        cash_impact=cash_impact,
        notes=body.notes,
        created_by=user_id,
    )
    session.add(txn)

    # Update portfolio cash
    portfolio.current_cash = portfolio.current_cash + cash_impact

    # Update position
    if body.transaction_type == "BUY":
        pos_result = await session.execute(
            select(Position).where(
                Position.portfolio_id == portfolio_id,
                Position.ticker == body.ticker,
                Position.status == "OPEN",
            )
        )
        existing = pos_result.scalar_one_or_none()
        if existing:
            old_total = (existing.shares or Decimal("0")) * (existing.cost_basis_per_share or Decimal("0"))
            new_total = body.shares * body.price_per_share
            total_shares = (existing.shares or Decimal("0")) + body.shares
            # Guard against rounding-artifact share counts that pass a truthy
            # check but produce nonsensical cost basis on division (same
            # threshold guard as add_position()).
            if total_shares > Decimal("0.000001"):
                avg_cost = (old_total + new_total) / total_shares
            else:
                avg_cost = Decimal("0")
            existing.shares = total_shares
            existing.cost_basis_per_share = avg_cost
            existing.cost_basis_total = total_shares * avg_cost
        else:
            new_pos = Position(
                id=uuid.uuid4(),
                portfolio_id=portfolio_id,
                ticker=body.ticker,
                status="OPEN",
                shares=body.shares,
                cost_basis_per_share=body.price_per_share,
                cost_basis_total=gross,
                first_acquisition_date=body.transaction_date,
                created_by=user_id,
            )
            session.add(new_pos)

    elif body.transaction_type == "SELL":
        pos_result = await session.execute(
            select(Position).where(
                Position.portfolio_id == portfolio_id,
                Position.ticker == body.ticker,
                Position.status == "OPEN",
            )
        )
        pos = pos_result.scalar_one_or_none()
        if pos:
            pos.shares = (pos.shares or Decimal("0")) - body.shares
            if pos.shares <= 0:
                pos.status = "CLOSED"
                pos.shares = Decimal("0")
                # Zero stale aggregates so portfolio NAV doesn't keep summing
                # the closed position's last market value.
                pos.market_value = Decimal("0")
                pos.unrealized_pnl = Decimal("0")
                pos.unrealized_pnl_pct = Decimal("0")
                pos.weight = Decimal("0")

    await session.commit()
    await _refresh_portfolio_positions(session, portfolio_id)
    await session.refresh(txn)

    return TransactionResponse(
        id=txn.id,
        portfolio_id=txn.portfolio_id,
        security_id=txn.security_id,
        ticker=txn.ticker,
        transaction_type=txn.transaction_type,
        transaction_date=txn.transaction_date,
        settlement_date=txn.settlement_date,
        shares=txn.shares,
        price_per_share=txn.price_per_share,
        gross_amount=txn.gross_amount,
        commission=txn.commission,
        net_amount=txn.net_amount,
        cash_impact=txn.cash_impact,
        source=txn.source,
        source_reference=txn.source_reference,
        notes=txn.notes,
    )


@router.get(
    "/portfolios/{portfolio_id}/transactions",
    response_model=list[TransactionResponse],
)
async def list_transactions(
    portfolio_id: uuid.UUID,
    type: str | None = Query(default=None, alias="type"),
    session: AsyncSession = Depends(get_session),
):
    """List transactions with optional type filter."""
    await _get_portfolio(session, portfolio_id)
    stmt = select(Transaction).where(Transaction.portfolio_id == portfolio_id)
    if type:
        stmt = stmt.where(Transaction.transaction_type == type)
    stmt = stmt.order_by(Transaction.transaction_date.desc())

    result = await session.execute(stmt)
    rows = result.scalars().all()
    return [
        TransactionResponse(
            id=t.id,
            portfolio_id=t.portfolio_id,
            security_id=t.security_id,
            ticker=t.ticker,
            transaction_type=t.transaction_type,
            transaction_date=t.transaction_date,
            settlement_date=t.settlement_date,
            shares=float(t.shares) if t.shares is not None else None,
            price_per_share=float(t.price_per_share) if t.price_per_share is not None else None,
            gross_amount=float(t.gross_amount) if t.gross_amount is not None else None,
            commission=float(t.commission) if t.commission is not None else None,
            net_amount=float(t.net_amount) if t.net_amount is not None else None,
            cash_impact=float(t.cash_impact) if t.cash_impact is not None else None,
            source=t.source,
            source_reference=t.source_reference,
            notes=t.notes,
        )
        for t in rows
    ]


# ══════════════════════════════════════════════════════════════════════
# NAV
# ══════════════════════════════════════════════════════════════════════


@router.get("/portfolios/{portfolio_id}/nav", response_model=NAVResponse)
async def get_nav(
    portfolio_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get current NAV summary for a portfolio."""
    portfolio = await _get_portfolio(session, portfolio_id)
    await _refresh_portfolio_positions(session, portfolio_id)

    # Count open positions
    pos_count_result = await session.execute(
        select(func.count(Position.id)).where(
            Position.portfolio_id == portfolio_id,
            Position.status == "OPEN",
        )
    )
    position_count = pos_count_result.scalar() or 0

    # Sum market values of open positions
    mv_result = await session.execute(
        select(func.sum(Position.market_value)).where(
            Position.portfolio_id == portfolio_id,
            Position.status == "OPEN",
        )
    )
    market_value = mv_result.scalar() or Decimal("0")

    # Sum unrealized P&L
    pnl_result = await session.execute(
        select(func.sum(Position.unrealized_pnl)).where(
            Position.portfolio_id == portfolio_id,
            Position.status == "OPEN",
        )
    )
    unrealized_pnl = pnl_result.scalar() or Decimal("0")

    cash = portfolio.current_cash or Decimal("0")
    market_value = market_value or Decimal("0")
    nav = market_value + cash
    cash_weight = float(cash / nav * 100) if nav > 0 else 100.0

    return NAVResponse(
        nav=nav,
        market_value=market_value,
        cash_balance=cash,
        unrealized_pnl=unrealized_pnl,
        cash_weight=round(cash_weight, 2),
        position_count=position_count,
    )


@router.get(
    "/portfolios/{portfolio_id}/nav/history",
    response_model=NAVHistoryResponse,
)
async def get_nav_history(
    portfolio_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get NAV history for a portfolio."""
    await _get_portfolio(session, portfolio_id)

    result = await session.execute(
        select(NAVSnapshot)
        .where(NAVSnapshot.portfolio_id == portfolio_id)
        .order_by(NAVSnapshot.snapshot_date.desc())
        .limit(365)
    )
    rows = result.scalars().all()
    return NAVHistoryResponse(
        history=[
            NAVHistoryEntry(
                date=snap.snapshot_date,
                nav=float(snap.nav),
                daily_return=float(snap.daily_return) if snap.daily_return is not None else None,
                cumulative_return=float(snap.cumulative_return) if snap.cumulative_return is not None else None,
            )
            for snap in rows
        ]
    )


@router.get(
    "/portfolios/{portfolio_id}/nav/snapshot",
    response_model=NAVSnapshotResponse | None,
)
async def get_nav_snapshot(
    portfolio_id: uuid.UUID,
    date: date | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
):
    """Get a specific NAV snapshot by date."""
    await _get_portfolio(session, portfolio_id)

    stmt = select(NAVSnapshot).where(NAVSnapshot.portfolio_id == portfolio_id)
    if date:
        stmt = stmt.where(NAVSnapshot.snapshot_date == date)
    stmt = stmt.order_by(NAVSnapshot.snapshot_date.desc()).limit(1)

    result = await session.execute(stmt)
    snap = result.scalar_one_or_none()
    if not snap:
        return None

    return NAVSnapshotResponse(
        id=snap.id,
        portfolio_id=snap.portfolio_id,
        snapshot_date=snap.snapshot_date,
        nav=float(snap.nav),
        market_value=float(snap.market_value) if snap.market_value is not None else None,
        cash_balance=float(snap.cash_balance) if snap.cash_balance is not None else None,
        unrealized_pnl=float(snap.unrealized_pnl) if snap.unrealized_pnl is not None else None,
        daily_return=float(snap.daily_return) if snap.daily_return is not None else None,
        cumulative_return=float(snap.cumulative_return) if snap.cumulative_return is not None else None,
        benchmark_daily_return=float(snap.benchmark_daily_return) if snap.benchmark_daily_return is not None else None,
        benchmark_cumulative_return=float(snap.benchmark_cumulative_return) if snap.benchmark_cumulative_return is not None else None,
        positions_snapshot=snap.positions_snapshot,
    )


# ══════════════════════════════════════════════════════════════════════
# Corporate Actions
# ══════════════════════════════════════════════════════════════════════


@router.get(
    "/portfolios/{portfolio_id}/corporate-actions",
    response_model=list[CorporateActionResponse],
)
async def list_corporate_actions(
    portfolio_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """List pending corporate actions for a portfolio."""
    await _get_portfolio(session, portfolio_id)

    result = await session.execute(
        select(CorporateActionQueue)
        .where(
            CorporateActionQueue.portfolio_id == portfolio_id,
            CorporateActionQueue.status == "PENDING",
        )
        .order_by(CorporateActionQueue.created_at.desc())
    )
    rows = result.scalars().all()
    return [
        CorporateActionResponse(
            id=ca.id,
            portfolio_id=ca.portfolio_id,
            position_id=ca.position_id,
            action_type=ca.action_type,
            security_id=ca.security_id,
            ticker=ca.ticker,
            ex_date=ca.ex_date,
            payment_date=ca.payment_date,
            details=ca.details,
            status=ca.status,
            applied_at=ca.applied_at,
        )
        for ca in rows
    ]


@router.post(
    "/portfolios/{portfolio_id}/corporate-actions/{queue_id}/apply",
    response_model=CorporateActionResponse,
)
async def apply_corporate_action(
    portfolio_id: uuid.UUID,
    queue_id: uuid.UUID,
    body: CorporateActionApplyRequest | None = None,
    session: AsyncSession = Depends(get_session),
):
    """Apply a pending corporate action."""
    await _get_portfolio(session, portfolio_id)

    result = await session.execute(
        select(CorporateActionQueue).where(CorporateActionQueue.id == queue_id)
    )
    ca = result.scalar_one_or_none()
    if not ca:
        raise HTTPException(status_code=404, detail="Corporate action not found")

    ca.status = "APPLIED"
    ca.applied_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(ca)

    return CorporateActionResponse(
        id=ca.id,
        portfolio_id=ca.portfolio_id,
        position_id=ca.position_id,
        action_type=ca.action_type,
        security_id=ca.security_id,
        ticker=ca.ticker,
        ex_date=ca.ex_date,
        payment_date=ca.payment_date,
        details=ca.details,
        status=ca.status,
        applied_at=ca.applied_at,
    )


@router.post(
    "/portfolios/{portfolio_id}/corporate-actions/{queue_id}/dismiss",
    response_model=CorporateActionResponse,
)
async def dismiss_corporate_action(
    portfolio_id: uuid.UUID,
    queue_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Dismiss a pending corporate action."""
    await _get_portfolio(session, portfolio_id)

    result = await session.execute(
        select(CorporateActionQueue).where(CorporateActionQueue.id == queue_id)
    )
    ca = result.scalar_one_or_none()
    if not ca:
        raise HTTPException(status_code=404, detail="Corporate action not found")

    ca.status = "DISMISSED"
    await session.commit()
    await session.refresh(ca)

    return CorporateActionResponse(
        id=ca.id,
        portfolio_id=ca.portfolio_id,
        position_id=ca.position_id,
        action_type=ca.action_type,
        security_id=ca.security_id,
        ticker=ca.ticker,
        ex_date=ca.ex_date,
        payment_date=ca.payment_date,
        details=ca.details,
        status=ca.status,
        applied_at=ca.applied_at,
    )
