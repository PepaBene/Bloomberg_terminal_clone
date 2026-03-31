"""Pillar 4 Phase 4 — Trade List Generation Engine.

Pure computation engine for trade list generation, execution sequencing,
and broker-compatible formatting (CSV, FIX, EMS).

No database access — all functions accept and return plain data.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone


# -- Constants ---------------------------------------------------------------

MIN_TRADE_NOTIONAL = 100.0  # skip trades below this dollar amount
LIMIT_PRICE_OFFSET_PCT = 0.005  # +/- 0.5% for LIMIT orders
DEFAULT_COMMISSION_PER_SHARE = 0.005
DEFAULT_MARKET_IMPACT_BPS = 2.0

VALID_ORDER_TYPES = ("MARKET", "LIMIT", "VWAP", "TWAP")
VALID_TIF = ("DAY", "GTC", "IOC")
VALID_URGENCY = ("LOW", "NORMAL", "HIGH")

FIX_SIDE_MAP = {"BUY": "1", "SELL": "2"}
FIX_ORDTYPE_MAP = {"MARKET": "1", "LIMIT": "2", "VWAP": "D", "TWAP": "D"}
FIX_TIF_MAP = {"DAY": "0", "GTC": "1", "IOC": "3"}

URGENCY_SORT_ORDER = {"HIGH": 0, "NORMAL": 1, "LOW": 2}


# -- Dataclasses -------------------------------------------------------------


@dataclass
class TradeOrder:
    """A single trade order ready for broker submission."""

    ticker: str
    action: str  # BUY / SELL
    shares: int
    notional_amount: float
    limit_price: float | None
    order_type: str  # MARKET / LIMIT / VWAP / TWAP
    time_in_force: str  # DAY / GTC / IOC
    urgency: str  # LOW / NORMAL / HIGH
    notes: str = ""


@dataclass
class TradeListSummary:
    """Aggregate statistics for a trade list."""

    total_orders: int
    buy_count: int
    sell_count: int
    total_buy_notional: float
    total_sell_notional: float
    net_notional: float
    estimated_commission: float
    estimated_market_impact: float


@dataclass
class TradeList:
    """Complete trade list with orders, summary, and metadata."""

    portfolio_id: str
    portfolio_name: str
    generated_at: str
    orders: list[TradeOrder]
    summary: TradeListSummary
    metadata: dict = field(default_factory=dict)


# -- Rebalance Trades to Orders ---------------------------------------------


def rebalance_trades_to_orders(
    rebalance_trades: list[dict],
    positions: list[dict],
    prices: dict,
    portfolio_nav: float,
    order_type: str = "MARKET",
    time_in_force: str = "DAY",
    commission_per_share: float = DEFAULT_COMMISSION_PER_SHARE,
) -> list[TradeOrder]:
    """Convert drift engine rebalance_trades into TradeOrder objects.

    Parameters
    ----------
    rebalance_trades : list[dict]
        Output from drift engine's ``suggest_rebalance_trades``.
        Each dict: {ticker, action, weight_delta, notional_amount}.
    positions : list[dict]
        Current positions: [{ticker, shares, market_value, ...}, ...].
        Used for context but not required for share calculation.
    prices : dict
        Mapping ticker -> current market price.
    portfolio_nav : float
        Total portfolio net asset value.
    order_type : str
        Default order type for all trades (MARKET/LIMIT/VWAP/TWAP).
    time_in_force : str
        Default time-in-force (DAY/GTC/IOC).
    commission_per_share : float
        Estimated commission per share for cost awareness.

    Returns
    -------
    list[TradeOrder]
        Trade orders with shares calculated from notional / price.
        Trades below the minimum notional threshold are excluded.
    """
    orders: list[TradeOrder] = []

    for trade in rebalance_trades:
        ticker = trade.get("ticker", "")
        action = trade.get("action", "BUY")
        notional = trade.get("notional_amount", 0.0)

        # Skip trades below the minimum threshold
        if abs(notional) < MIN_TRADE_NOTIONAL:
            continue

        price = prices.get(ticker)
        if price is None or price <= 0:
            continue

        # Calculate whole shares
        shares = int(math.floor(abs(notional) / price))
        if shares == 0:
            continue

        # Recalculate actual notional based on whole shares
        actual_notional = round(shares * price, 2)

        # Set limit price for LIMIT orders: +0.5% for BUY, -0.5% for SELL
        limit_price: float | None = None
        if order_type == "LIMIT":
            if action == "BUY":
                limit_price = round(price * (1 + LIMIT_PRICE_OFFSET_PCT), 4)
            else:
                limit_price = round(price * (1 - LIMIT_PRICE_OFFSET_PCT), 4)

        orders.append(TradeOrder(
            ticker=ticker,
            action=action,
            shares=shares,
            notional_amount=actual_notional,
            limit_price=limit_price,
            order_type=order_type,
            time_in_force=time_in_force,
            urgency="NORMAL",
            notes=f"weight_delta={trade.get('weight_delta', 0.0):.4f}%",
        ))

    return orders


# -- Trade Summary -----------------------------------------------------------


def compute_trade_summary(
    orders: list[TradeOrder],
    commission_per_share: float = DEFAULT_COMMISSION_PER_SHARE,
    market_impact_bps: float = DEFAULT_MARKET_IMPACT_BPS,
) -> TradeListSummary:
    """Compute aggregate statistics for a list of trade orders.

    Parameters
    ----------
    orders : list[TradeOrder]
        The trade orders to summarize.
    commission_per_share : float
        Estimated commission per share.
    market_impact_bps : float
        Estimated market impact in basis points.

    Returns
    -------
    TradeListSummary
        Counts, notionals, estimated commission and market impact.
    """
    buy_count = 0
    sell_count = 0
    total_buy_notional = 0.0
    total_sell_notional = 0.0
    total_shares = 0

    for order in orders:
        total_shares += order.shares
        if order.action == "BUY":
            buy_count += 1
            total_buy_notional += order.notional_amount
        else:
            sell_count += 1
            total_sell_notional += order.notional_amount

    net_notional = round(total_buy_notional - total_sell_notional, 2)
    total_notional = total_buy_notional + total_sell_notional
    estimated_commission = round(total_shares * commission_per_share, 2)
    estimated_market_impact = round(total_notional * market_impact_bps / 10_000, 2)

    return TradeListSummary(
        total_orders=len(orders),
        buy_count=buy_count,
        sell_count=sell_count,
        total_buy_notional=round(total_buy_notional, 2),
        total_sell_notional=round(total_sell_notional, 2),
        net_notional=net_notional,
        estimated_commission=estimated_commission,
        estimated_market_impact=estimated_market_impact,
    )


# -- CSV Format --------------------------------------------------------------


def format_trade_list_csv(trade_list: TradeList) -> str:
    """Format a trade list as broker-compatible CSV.

    Parameters
    ----------
    trade_list : TradeList
        The complete trade list to format.

    Returns
    -------
    str
        CSV string with header row and one data row per order.
        Columns: ticker, side, quantity, order_type, limit_price,
        time_in_force, notional, notes.
    """
    columns = [
        "ticker", "side", "quantity", "order_type",
        "limit_price", "time_in_force", "notional", "notes",
    ]
    lines: list[str] = [",".join(columns)]

    for order in trade_list.orders:
        row = [
            order.ticker,
            order.action,
            str(order.shares),
            order.order_type,
            str(order.limit_price) if order.limit_price is not None else "",
            order.time_in_force,
            str(order.notional_amount),
            order.notes,
        ]
        lines.append(",".join(row))

    return "\n".join(lines)


# -- FIX Protocol Format -----------------------------------------------------


def format_trade_list_fix(trade_list: TradeList) -> list[dict]:
    """Format a trade list as FIX protocol-style message dicts.

    Each dict contains standard FIX tags for a NewOrderSingle (D) message.

    Parameters
    ----------
    trade_list : TradeList
        The complete trade list to format.

    Returns
    -------
    list[dict]
        One dict per order with FIX tag keys:
        tag_11 (ClOrdID), tag_55 (Symbol), tag_54 (Side),
        tag_38 (OrderQty), tag_40 (OrdType), tag_44 (Price),
        tag_59 (TimeInForce).
    """
    messages: list[dict] = []

    for idx, order in enumerate(trade_list.orders, start=1):
        clord_id = f"{trade_list.portfolio_id}-{idx:04d}"

        msg: dict = {
            "tag_11": clord_id,
            "tag_55": order.ticker,
            "tag_54": FIX_SIDE_MAP.get(order.action, "1"),
            "tag_38": order.shares,
            "tag_40": FIX_ORDTYPE_MAP.get(order.order_type, "1"),
            "tag_44": order.limit_price if order.limit_price is not None else 0.0,
            "tag_59": FIX_TIF_MAP.get(order.time_in_force, "0"),
        }
        messages.append(msg)

    return messages


# -- EMS Format --------------------------------------------------------------


def format_trade_list_ems(trade_list: TradeList) -> list[dict]:
    """Format a trade list for an Execution Management System.

    Parameters
    ----------
    trade_list : TradeList
        The complete trade list to format.

    Returns
    -------
    list[dict]
        One dict per order with EMS-style fields: order_id, symbol,
        side, quantity, order_type, limit_price, tif, urgency,
        notional, account, notes.
    """
    ems_orders: list[dict] = []

    for idx, order in enumerate(trade_list.orders, start=1):
        order_id = f"{trade_list.portfolio_id}-EMS-{idx:04d}"

        ems_orders.append({
            "order_id": order_id,
            "symbol": order.ticker,
            "side": order.action,
            "quantity": order.shares,
            "order_type": order.order_type,
            "limit_price": order.limit_price,
            "tif": order.time_in_force,
            "urgency": order.urgency,
            "notional": order.notional_amount,
            "account": trade_list.portfolio_id,
            "notes": order.notes,
        })

    return ems_orders


# -- Execution Sequence Optimization -----------------------------------------


def optimize_execution_sequence(orders: list[TradeOrder]) -> list[TradeOrder]:
    """Reorder trades for optimal execution.

    Ordering strategy:
    1. Sells before buys (to free up cash for purchases).
    2. Within each side, sort by urgency (HIGH first).
    3. Within same urgency, sort by notional amount descending
       (larger trades first to minimize market impact timing risk).

    Parameters
    ----------
    orders : list[TradeOrder]
        Unordered trade orders.

    Returns
    -------
    list[TradeOrder]
        Reordered trade orders for optimal execution.
    """

    def sort_key(order: TradeOrder) -> tuple:
        # Sells (0) before Buys (1)
        side_rank = 0 if order.action == "SELL" else 1
        urgency_rank = URGENCY_SORT_ORDER.get(order.urgency, 1)
        # Negate notional for descending sort
        return (side_rank, urgency_rank, -order.notional_amount)

    return sorted(orders, key=sort_key)


# -- Full Orchestrator -------------------------------------------------------


def generate_trade_list(
    portfolio_id: str,
    portfolio_name: str,
    rebalance_trades: list[dict],
    positions: list[dict],
    prices: dict,
    portfolio_nav: float,
    order_type: str = "MARKET",
    time_in_force: str = "DAY",
    commission_per_share: float = DEFAULT_COMMISSION_PER_SHARE,
) -> TradeList:
    """Generate a complete trade list from drift engine rebalance suggestions.

    Full orchestrator that converts rebalance trades to orders, optimizes
    execution sequence, computes summary statistics, and assembles the
    final TradeList with metadata.

    Parameters
    ----------
    portfolio_id : str
        Unique portfolio identifier.
    portfolio_name : str
        Human-readable portfolio name.
    rebalance_trades : list[dict]
        Output from drift engine's ``suggest_rebalance_trades``.
        Each dict: {ticker, action, weight_delta, notional_amount}.
    positions : list[dict]
        Current positions: [{ticker, shares, market_value, ...}, ...].
    prices : dict
        Mapping ticker -> current market price.
    portfolio_nav : float
        Total portfolio net asset value.
    order_type : str
        Default order type (MARKET/LIMIT/VWAP/TWAP).
    time_in_force : str
        Default time-in-force (DAY/GTC/IOC).
    commission_per_share : float
        Estimated commission per share.

    Returns
    -------
    TradeList
        Complete trade list with optimized order sequence, summary,
        and metadata.
    """
    # Convert rebalance suggestions to trade orders
    orders = rebalance_trades_to_orders(
        rebalance_trades=rebalance_trades,
        positions=positions,
        prices=prices,
        portfolio_nav=portfolio_nav,
        order_type=order_type,
        time_in_force=time_in_force,
        commission_per_share=commission_per_share,
    )

    # Optimize execution sequence
    orders = optimize_execution_sequence(orders)

    # Compute summary
    summary = compute_trade_summary(
        orders=orders,
        commission_per_share=commission_per_share,
    )

    # Timestamp
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Metadata
    metadata = {
        "source": "drift_rebalance",
        "order_count": len(orders),
        "order_type": order_type,
        "time_in_force": time_in_force,
        "portfolio_nav": portfolio_nav,
        "min_trade_notional": MIN_TRADE_NOTIONAL,
    }

    return TradeList(
        portfolio_id=portfolio_id,
        portfolio_name=portfolio_name,
        generated_at=generated_at,
        orders=orders,
        summary=summary,
        metadata=metadata,
    )
