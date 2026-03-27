"""Pillar 2 FI Supplement -- Part 1: Bond Pricing Analytics API endpoints."""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_session
from src.engines.e9_bond_pricing import (
    compute_accrued_interest,
    compute_ytw_full,
    generate_cash_flow_schedule,
    price_from_yield,
    yield_from_price,
    _find_last_coupon_date,
)
from src.models.corporate_bond import (
    BondCallSchedule,
    BondEODPrice,
    CorporateBond,
)
from src.schemas.fi_bond_analytics import (
    BondPriceHistoryItem,
    BondPriceHistoryResponse,
    BondPriceResponse,
    CashFlowItem,
    CashFlowScheduleResponse,
    PriceFromYieldRequest,
    PriceFromYieldResponse,
    YieldFromPriceRequest,
    YieldFromPriceResponse,
    YTWRequest,
    YTWResponse,
)

router = APIRouter(prefix="/v2/analytics", tags=["FI Bond Analytics"])


# ---- Helpers ---------------------------------------------------------------


async def _get_bond_by_cusip(cusip: str, session: AsyncSession) -> CorporateBond:
    """Look up a bond by CUSIP or raise 404."""
    query = select(CorporateBond).where(CorporateBond.cusip == cusip)
    result = await session.execute(query)
    bond = result.scalars().unique().one_or_none()
    if bond is None:
        raise HTTPException(status_code=404, detail=f"Bond with CUSIP {cusip} not found")
    return bond


# ---- 1. GET /bonds/{cusip}/price -------------------------------------------


@router.get(
    "/bonds/{cusip}/price",
    response_model=BondPriceResponse,
)
async def get_bond_price(
    cusip: str,
    session: AsyncSession = Depends(get_session),
    price_date: date | None = Query(None, description="Price date (defaults to latest)"),
):
    """Get the bond price with computed analytics (clean price, dirty price, accrued, YTM, YTW)."""
    bond = await _get_bond_by_cusip(cusip, session)

    # Get EOD price
    eod_query = select(BondEODPrice).where(BondEODPrice.bond_id == bond.bond_id)
    if price_date:
        eod_query = eod_query.where(BondEODPrice.price_date == price_date)
    else:
        eod_query = eod_query.order_by(BondEODPrice.price_date.desc())
    eod_query = eod_query.limit(1)

    result = await session.execute(eod_query)
    eod = result.scalar_one_or_none()
    if eod is None:
        raise HTTPException(status_code=404, detail=f"No price data for bond {cusip}")

    coupon_rate = float(bond.coupon_rate) if bond.coupon_rate is not None else 0.0
    freq = bond.coupon_frequency if bond.coupon_frequency is not None else 2
    dc = bond.day_count_convention or "30/360"
    settlement = eod.price_date
    trade_price = float(eod.last_trade_price) if eod.last_trade_price is not None else 100.0

    # Compute accrued interest
    last_coupon = _find_last_coupon_date(settlement, bond.maturity_date, freq)
    accrued = compute_accrued_interest(coupon_rate, 100.0, freq, last_coupon, settlement, dc)

    # Dirty price = trade_price (which is typically the clean price in TRACE)
    clean_price = trade_price
    dirty_price = clean_price + accrued

    # Compute YTM
    ytm_val = yield_from_price(
        clean_price, coupon_rate, 100.0, settlement, bond.maturity_date, freq, dc,
    )

    # Compute YTW if callable
    ytw_val = None
    if bond.is_callable and bond.call_schedule:
        call_entries = [
            {"call_date": cs.call_date, "call_price": float(cs.call_price) if cs.call_price else 100.0}
            for cs in bond.call_schedule
        ]
        ytw_result = compute_ytw_full(
            clean_price, coupon_rate, 100.0, settlement, bond.maturity_date,
            call_entries, freq, dc,
        )
        ytw_val = ytw_result["ytw"]

    return BondPriceResponse(
        cusip=cusip,
        price_date=eod.price_date,
        clean_price=round(clean_price, 6),
        dirty_price=round(dirty_price, 6),
        accrued_interest=round(accrued, 6),
        yield_to_maturity=round(ytm_val, 8),
        yield_to_worst=round(ytw_val, 8) if ytw_val is not None else None,
    )


# ---- 2. GET /bonds/{cusip}/price-history -----------------------------------


@router.get(
    "/bonds/{cusip}/price-history",
    response_model=BondPriceHistoryResponse,
)
async def get_bond_price_history(
    cusip: str,
    session: AsyncSession = Depends(get_session),
    start: date | None = Query(None, description="Start date"),
    end: date | None = Query(None, description="End date"),
):
    """Get historical bond prices with computed analytics."""
    bond = await _get_bond_by_cusip(cusip, session)

    query = select(BondEODPrice).where(BondEODPrice.bond_id == bond.bond_id)
    if start:
        query = query.where(BondEODPrice.price_date >= start)
    if end:
        query = query.where(BondEODPrice.price_date <= end)
    query = query.order_by(BondEODPrice.price_date.asc())

    result = await session.execute(query)
    eod_prices = result.scalars().all()

    coupon_rate = float(bond.coupon_rate) if bond.coupon_rate is not None else 0.0
    freq = bond.coupon_frequency if bond.coupon_frequency is not None else 2
    dc = bond.day_count_convention or "30/360"

    history: list[BondPriceHistoryItem] = []
    for eod in eod_prices:
        trade_price = float(eod.last_trade_price) if eod.last_trade_price is not None else None
        clean = trade_price
        dirty = None
        ytm_val = None
        ytw_val = float(eod.yield_to_worst) if eod.yield_to_worst is not None else None

        if trade_price is not None and bond.maturity_date > eod.price_date:
            last_coupon = _find_last_coupon_date(eod.price_date, bond.maturity_date, freq)
            accrued = compute_accrued_interest(
                coupon_rate, 100.0, freq, last_coupon, eod.price_date, dc,
            )
            dirty = round(trade_price + accrued, 6)
            ytm_val = round(
                yield_from_price(
                    trade_price, coupon_rate, 100.0, eod.price_date, bond.maturity_date, freq, dc,
                ),
                8,
            )

        history.append(BondPriceHistoryItem(
            price_date=eod.price_date,
            clean_price=round(clean, 6) if clean is not None else None,
            dirty_price=dirty,
            yield_to_maturity=ytm_val,
            yield_to_worst=ytw_val,
        ))

    return BondPriceHistoryResponse(cusip=cusip, history=history)


# ---- 3. GET /bonds/{cusip}/cash-flows --------------------------------------


@router.get(
    "/bonds/{cusip}/cash-flows",
    response_model=CashFlowScheduleResponse,
)
async def get_bond_cash_flows(
    cusip: str,
    session: AsyncSession = Depends(get_session),
    settlement_date: date | None = Query(None, description="Settlement date (defaults to today)"),
):
    """Generate the cash flow schedule for a bond."""
    bond = await _get_bond_by_cusip(cusip, session)

    coupon_rate = float(bond.coupon_rate) if bond.coupon_rate is not None else 0.0
    face = 100.0
    freq = bond.coupon_frequency if bond.coupon_frequency is not None else 2
    settle = settlement_date or date.today()

    # Build call schedule from DB
    call_entries = None
    if bond.is_callable and bond.call_schedule:
        call_entries = [
            {"call_date": cs.call_date, "call_price": float(cs.call_price) if cs.call_price else 100.0}
            for cs in bond.call_schedule
        ]

    flows = generate_cash_flow_schedule(
        coupon_rate, face, freq, bond.maturity_date, settle, call_entries,
    )

    cf_items = [CashFlowItem(date=f["date"], amount=f["amount"], type=f["type"]) for f in flows]
    total_coupon = sum(f["amount"] for f in flows if f["type"] == "COUPON")
    total_all = sum(f["amount"] for f in flows)

    return CashFlowScheduleResponse(
        cusip=cusip,
        cash_flows=cf_items,
        total_coupon_payments=round(total_coupon, 6),
        total_cash_flows=round(total_all, 6),
    )


# ---- 4. POST /bonds/price-from-yield ---------------------------------------


@router.post(
    "/bonds/price-from-yield",
    response_model=PriceFromYieldResponse,
)
async def compute_price_from_yield(body: PriceFromYieldRequest):
    """Compute clean price, dirty price, and accrued interest from a given yield."""
    result = price_from_yield(
        ytm=body.yield_value,
        coupon_rate=body.coupon_rate,
        face_value=body.face_value,
        settlement_date=body.settlement_date,
        maturity_date=body.maturity_date,
        frequency=body.frequency,
        day_count=body.day_count,
    )
    return PriceFromYieldResponse(
        clean_price=result["clean_price"],
        dirty_price=result["dirty_price"],
        accrued_interest=result["accrued_interest"],
        yield_value=body.yield_value,
    )


# ---- 5. POST /bonds/yield-from-price ---------------------------------------


@router.post(
    "/bonds/yield-from-price",
    response_model=YieldFromPriceResponse,
)
async def compute_yield_from_price(body: YieldFromPriceRequest):
    """Compute yield to maturity from a given clean price."""
    ytm = yield_from_price(
        clean_price=body.clean_price,
        coupon_rate=body.coupon_rate,
        face_value=body.face_value,
        settlement_date=body.settlement_date,
        maturity_date=body.maturity_date,
        frequency=body.frequency,
        day_count=body.day_count,
    )
    return YieldFromPriceResponse(
        yield_to_maturity=round(ytm, 8),
        clean_price=body.clean_price,
    )


# ---- 6. POST /bonds/ytw ----------------------------------------------------


@router.post(
    "/bonds/ytw",
    response_model=YTWResponse,
)
async def compute_ytw_endpoint(body: YTWRequest):
    """Compute yield-to-worst with full detail including all call yields."""
    result = compute_ytw_full(
        clean_price=body.clean_price,
        coupon_rate=body.coupon_rate,
        face_value=body.face_value,
        settlement_date=body.settlement_date,
        maturity_date=body.maturity_date,
        call_schedule=body.call_schedule,
        frequency=body.frequency,
        day_count=body.day_count,
    )
    return YTWResponse(
        yield_to_worst=result["ytw"],
        yield_to=result["yield_to"],
        exercise_date=result["exercise_date"],
        yield_to_maturity=result["ytm"],
        call_yields=result["call_yields"],
    )
