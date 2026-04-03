"""Pillar 4 Phase 1 — Corporate Action Processing Engine.

Pure computation engine for dividends, splits, spin-offs, mergers,
and transaction cash impact calculations.

No database access — all functions accept and return plain data.
"""

from __future__ import annotations

from dataclasses import dataclass


# ── Dataclasses ─────────────────────────────────────────────────────────


@dataclass
class DividendResult:
    """Result of a dividend calculation."""
    cash_amount: float
    drip_shares: float | None  # if DRIP enabled
    drip_cost_basis: float | None
    is_drip: bool


@dataclass
class SplitResult:
    """Result of a stock split or reverse split."""
    new_shares: float
    new_cost_per_share: float
    split_ratio: float


@dataclass
class SpinOffResult:
    """Result of a spin-off calculation."""
    parent_new_cost: float
    child_ticker: str
    child_shares: float
    child_cost_basis: float


@dataclass
class MergerResult:
    """Result of a merger calculation."""
    result_type: str  # CASH / STOCK / MIXED
    cash_received: float
    new_ticker: str | None
    new_shares: float | None
    close_parent: bool


# ── Dividend Processing ────────────────────────────────────────────────


def process_cash_dividend(
    shares: float,
    dividend_per_share: float,
    drip_enabled: bool = False,
    current_price: float | None = None,
) -> DividendResult:
    """Process a cash dividend, optionally reinvesting via DRIP.

    Parameters
    ----------
    shares : float
        Number of shares held.
    dividend_per_share : float
        Dividend amount per share.
    drip_enabled : bool
        Whether dividend reinvestment plan is active.
    current_price : float | None
        Current share price (required if DRIP enabled).

    Returns
    -------
    DividendResult
    """
    if shares < 0:
        raise ValueError(f"shares must be >= 0, got {shares}")
    if dividend_per_share < 0:
        raise ValueError(f"dividend_per_share must be >= 0, got {dividend_per_share}")

    cash_amount = shares * dividend_per_share

    if drip_enabled and current_price is not None and current_price > 0:
        drip_shares = cash_amount / current_price
        return DividendResult(
            cash_amount=0.0,
            drip_shares=round(drip_shares, 6),
            drip_cost_basis=round(cash_amount, 2),
            is_drip=True,
        )

    return DividendResult(
        cash_amount=round(cash_amount, 2),
        drip_shares=None,
        drip_cost_basis=None,
        is_drip=False,
    )


# ── Stock Split Processing ─────────────────────────────────────────────


def process_stock_split(
    shares: float,
    cost_basis_per_share: float,
    split_ratio: float,
) -> SplitResult:
    """Process a forward stock split.

    A 2-for-1 split: split_ratio=2.0
    A 3-for-1 split: split_ratio=3.0
    A 4-for-3 split: split_ratio=4/3
    """
    if split_ratio <= 0:
        raise ValueError(f"split_ratio must be positive, got {split_ratio}")
    new_shares = shares * split_ratio
    new_cost_per_share = cost_basis_per_share / split_ratio

    return SplitResult(
        new_shares=round(new_shares, 6),
        new_cost_per_share=round(new_cost_per_share, 6),
        split_ratio=split_ratio,
    )


def process_reverse_split(
    shares: float,
    cost_basis_per_share: float,
    reverse_ratio: float,
) -> SplitResult:
    """Process a reverse stock split.

    A 1-for-10 reverse split: reverse_ratio=10
    A 1-for-4 reverse split: reverse_ratio=4
    """
    if reverse_ratio <= 0:
        raise ValueError(f"reverse_ratio must be positive, got {reverse_ratio}")
    new_shares = shares / reverse_ratio
    new_cost_per_share = cost_basis_per_share * reverse_ratio

    return SplitResult(
        new_shares=round(new_shares, 6),
        new_cost_per_share=round(new_cost_per_share, 6),
        split_ratio=1.0 / reverse_ratio,
    )


# ── Spin-Off Processing ────────────────────────────────────────────────


def process_spin_off(
    parent_shares: float,
    parent_cost_total: float,
    allocation_pct: float,
    child_ticker: str,
    shares_per_parent: float = 1.0,
) -> SpinOffResult:
    """Process a spin-off corporate action.

    Parameters
    ----------
    parent_shares : float
        Number of parent shares held.
    parent_cost_total : float
        Total cost basis of parent position.
    allocation_pct : float
        Percentage of cost basis allocated to child (0-100).
    child_ticker : str
        Ticker of the spun-off entity.
    shares_per_parent : float
        Child shares received per parent share.

    Returns
    -------
    SpinOffResult
    """
    if not (0 <= allocation_pct <= 100):
        raise ValueError(f"allocation_pct must be between 0 and 100, got {allocation_pct}")

    child_cost_basis = parent_cost_total * (allocation_pct / 100.0)
    parent_new_cost = parent_cost_total - child_cost_basis
    child_shares = parent_shares * shares_per_parent

    return SpinOffResult(
        parent_new_cost=round(parent_new_cost, 2),
        child_ticker=child_ticker,
        child_shares=round(child_shares, 6),
        child_cost_basis=round(child_cost_basis, 2),
    )


# ── Merger Processing ──────────────────────────────────────────────────


def process_merger_cash(
    shares: float,
    merger_price_per_share: float,
) -> MergerResult:
    """Process an all-cash merger."""
    cash_received = shares * merger_price_per_share
    return MergerResult(
        result_type="CASH",
        cash_received=round(cash_received, 2),
        new_ticker=None,
        new_shares=None,
        close_parent=True,
    )


def process_merger_stock(
    shares: float,
    exchange_ratio: float,
    acquirer_ticker: str,
) -> MergerResult:
    """Process an all-stock merger."""
    new_shares = shares * exchange_ratio
    return MergerResult(
        result_type="STOCK",
        cash_received=0.0,
        new_ticker=acquirer_ticker,
        new_shares=round(new_shares, 6),
        close_parent=True,
    )


def process_merger_mixed(
    shares: float,
    cash_per_share: float,
    stock_ratio: float,
    acquirer_ticker: str,
) -> MergerResult:
    """Process a mixed cash-and-stock merger."""
    cash_received = shares * cash_per_share
    new_shares = shares * stock_ratio
    return MergerResult(
        result_type="MIXED",
        cash_received=round(cash_received, 2),
        new_ticker=acquirer_ticker,
        new_shares=round(new_shares, 6),
        close_parent=True,
    )


# ── Sell Validation ────────────────────────────────────────────────────


def validate_sell(
    current_shares: float,
    sell_shares: float,
) -> tuple[bool, str]:
    """Validate whether a sell order can be filled.

    Returns
    -------
    tuple[bool, str]
        (True, "OK") if valid, (False, reason) otherwise.
    """
    if sell_shares <= 0:
        return False, "Sell quantity must be positive"
    if sell_shares > current_shares:
        return (
            False,
            f"Cannot sell {sell_shares} shares, only {current_shares} held",
        )
    return True, "OK"


# ── Transaction Cash Impact ─────────────────────────────────────────────


def compute_transaction_cash_impact(
    txn_type: str,
    shares: float,
    price: float,
    commission: float = 0.0,
) -> float:
    """Compute net cash impact of a transaction.

    Parameters
    ----------
    txn_type : str
        BUY, SELL, DIVIDEND, CASH_DEPOSIT, CASH_WITHDRAWAL.
    shares : float
        Number of shares (or amount for DIVIDEND/CASH).
    price : float
        Price per share (or 1.0 for fixed-amount types).
    commission : float
        Trading commission.

    Returns
    -------
    float
        Positive = cash inflow, negative = cash outflow.
    """
    txn_upper = txn_type.upper()

    if txn_upper == "BUY":
        return round(-(shares * price + commission), 2)
    elif txn_upper == "SELL":
        return round(shares * price - commission, 2)
    elif txn_upper == "DIVIDEND":
        return round(shares * price, 2)
    elif txn_upper == "CASH_DEPOSIT":
        return round(shares * price, 2)
    elif txn_upper == "CASH_WITHDRAWAL":
        return round(-(shares * price), 2)
    else:
        return 0.0
