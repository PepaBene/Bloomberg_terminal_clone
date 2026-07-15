"""Backfill historical DAILY + MONTHLY PerformanceSnapshot rows (Pillar 4 Phase 2).

Gap (DATA_WIRING_AUDIT.md §7): the only writer of ``performance_snapshots``
is ``portfolio_performance._compute_and_persist_performance``, invoked on
each live request. It writes a single "since-inception-to-date" DAILY row
whose ``period_end`` tracks "today" — so DAILY rows *do* accumulate one per
calendar day, but only from whenever a portfolio started being queried
regularly, and MONTHLY rows are never written at all. GET
.../performance/returns/calendar and .../returns/rolling query MONTHLY and
DAILY period types respectively, so both returned empty grids for any
portfolio whose NAV history predates that point (or that's rarely queried).

This script re-derives history from data already in the DB (no external
calls) by walking each portfolio's existing NAVSnapshot rows and persisting:

  * One DAILY row per NAV date (index >= 1) — period_start = inception
    date, period_end = that day, exactly mirroring what the live endpoint
    computes for "today" (cumulative since-inception TWR/risk metrics).
  * One MONTHLY row per calendar month present in the NAV history —
    period_start = the previous month's last NAV date (the return
    baseline) or, for the very first month, that month's own first NAV
    date (there's no earlier data point anywhere in the system to diff
    against, so that first day's own return is necessarily 0);
    period_end = that month's last NAV date. twr_return on a MONTHLY row
    is therefore the *single month's* return, not cumulative — the
    convention GET .../returns/calendar expects, since it reads one
    snapshot per month and assigns its twr_return straight to that
    calendar month's grid cell.

All return/risk math is delegated to
performance_engine.build_performance_summary() via the same
_summary_to_fields()/_upsert_performance_snapshot() helpers the live
endpoint uses (src.api.routers.portfolio_performance), so both paths write
identical column semantics — this script does not reimplement any return
or risk math.

Design note on cost: the DAILY loop recomputes the full since-inception
summary at each day (O(n) work per day => O(n^2) overall for an n-day
history). For the portfolio lifetimes this app models (single-digit years
of daily snapshots) that's a trivial amount of arithmetic; if some future
portfolio accumulates enough history for this to matter, switch to an
incremental TWR/drawdown accumulator instead of re-deriving from scratch
each day.

Usage:
    python -m scripts.backfill_performance_snapshots
    python -m scripts.backfill_performance_snapshots --portfolio-id <uuid>
    python -m scripts.backfill_performance_snapshots --dry-run
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from datetime import date
from pathlib import Path
from uuid import UUID

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.routers.portfolio_performance import (
    _build_benchmark_history,
    _resolve_benchmark_security_id,
    _summary_to_fields,
    _upsert_performance_snapshot,
)
from src.database import get_session_factory
from src.engines import performance_engine
from src.models.nav_snapshot import NAVSnapshot
from src.models.portfolio import Portfolio

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("backfill_performance_snapshots")


async def _backfill_portfolio(
    session: AsyncSession, portfolio: Portfolio, dry_run: bool
) -> tuple[int, int]:
    """Backfill DAILY + MONTHLY rows for one portfolio. Returns (daily_count,
    monthly_count) rows computed (whether or not persisted, for --dry-run).
    """
    nav_rows = (
        await session.execute(
            select(NAVSnapshot)
            .where(NAVSnapshot.portfolio_id == portfolio.id)
            .order_by(NAVSnapshot.snapshot_date.asc())
        )
    ).scalars().all()
    if len(nav_rows) < 2:
        return 0, 0

    # Resolve the benchmark security once per portfolio (not once per day) —
    # ticker -> security_id never changes across the backfill window.
    benchmark_security_id = None
    if portfolio.benchmark_id:
        benchmark_security_id = await _resolve_benchmark_security_id(
            session, portfolio.benchmark_id
        )

    cash_flows = None
    if portfolio.initial_cash is not None and float(portfolio.initial_cash) > 0:
        cash_flows = [{"date_offset": 0, "amount": -float(portfolio.initial_cash)}]

    async def _benchmark_history_for(rows: list[NAVSnapshot]) -> list[dict] | None:
        if benchmark_security_id is None:
            return None
        return await _build_benchmark_history(
            session, benchmark_security_id, [r.snapshot_date for r in rows]
        )

    # ── DAILY: one "since inception through day i" row per day ─────────
    daily_count = 0
    for i in range(1, len(nav_rows)):
        slice_rows = nav_rows[: i + 1]
        nav_history = [
            {"date": r.snapshot_date.isoformat(), "nav": float(r.nav)} for r in slice_rows
        ]
        benchmark_history = await _benchmark_history_for(slice_rows)
        summary = performance_engine.build_performance_summary(
            nav_history, benchmark_history=benchmark_history, cash_flows=cash_flows
        )
        fields = _summary_to_fields(summary)
        if not dry_run:
            await _upsert_performance_snapshot(
                session,
                portfolio.id,
                "DAILY",
                slice_rows[0].snapshot_date,
                slice_rows[-1].snapshot_date,
                fields,
            )
        daily_count += 1

    # ── MONTHLY: one single-month-return row per calendar month ────────
    months: dict[tuple[int, int], list[NAVSnapshot]] = {}
    for r in nav_rows:
        months.setdefault((r.snapshot_date.year, r.snapshot_date.month), []).append(r)

    monthly_count = 0
    prev_month_last_row: NAVSnapshot | None = None
    for key in sorted(months.keys()):
        month_rows = months[key]
        is_first_month = prev_month_last_row is None
        slice_rows = month_rows if is_first_month else [prev_month_last_row] + month_rows
        period_start: date = slice_rows[0].snapshot_date
        period_end: date = month_rows[-1].snapshot_date

        nav_history = [
            {"date": r.snapshot_date.isoformat(), "nav": float(r.nav)} for r in slice_rows
        ]
        benchmark_history = await _benchmark_history_for(slice_rows)
        summary = performance_engine.build_performance_summary(
            nav_history, benchmark_history=benchmark_history, cash_flows=None
        )
        fields = _summary_to_fields(summary)
        if not dry_run:
            await _upsert_performance_snapshot(
                session, portfolio.id, "MONTHLY", period_start, period_end, fields
            )
        monthly_count += 1
        prev_month_last_row = month_rows[-1]

    return daily_count, monthly_count


async def run(dry_run: bool = False, portfolio_id: UUID | None = None) -> None:
    factory = get_session_factory()
    async with factory() as session:
        query = select(Portfolio)
        if portfolio_id is not None:
            query = query.where(Portfolio.id == portfolio_id)
        portfolios = (await session.execute(query)).scalars().all()
        logger.info("Backfilling performance snapshots for %d portfolio(s)", len(portfolios))

        if not portfolios:
            logger.warning("No portfolios found — nothing to backfill.")
            return

        total_daily = total_monthly = 0
        for portfolio in portfolios:
            try:
                d, m = await _backfill_portfolio(session, portfolio, dry_run)
                total_daily += d
                total_monthly += m
                if d or m:
                    logger.info(
                        "Portfolio %s: %d DAILY + %d MONTHLY rows", portfolio.id, d, m
                    )
            except Exception:
                logger.exception("Failed to backfill portfolio %s", portfolio.id)
                continue

        if not dry_run:
            await session.commit()
        logger.info(
            "Backfill complete: %d DAILY + %d MONTHLY rows %s",
            total_daily,
            total_monthly,
            "computed (dry-run, not persisted)" if dry_run else "persisted",
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Backfill historical DAILY/MONTHLY performance snapshots from NAV history"
    )
    parser.add_argument("--dry-run", action="store_true", help="Compute but don't persist")
    parser.add_argument(
        "--portfolio-id", type=str, default=None, help="Backfill a single portfolio by UUID"
    )
    args = parser.parse_args()
    pid = UUID(args.portfolio_id) if args.portfolio_id else None
    asyncio.run(run(dry_run=args.dry_run, portfolio_id=pid))


if __name__ == "__main__":
    main()
