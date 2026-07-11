"""Batch worker for Pillar 2 Supplement backtesting.

``POST /v2/analytics/backtest`` (``src/api/routers/backtesting.py``) only
ever inserted a PENDING ``BacktestRun`` row -- the docstring on that
endpoint described a batch worker that would advance it to COMPLETED, but
no such worker existed anywhere in ``scripts/`` or ``src/scheduler/``, so
every run stayed PENDING forever. This script is that worker.

What it does
------------
Polls for PENDING ``BacktestRun`` rows and, for each one:

1. Runs ``strategy_definition`` (filters + optional ranking) through the
   real E4 ``ScreeningEngine`` (``run_screen_from_dict``) to select the
   strategy's basket of securities.
2. Builds portfolio weights via the requested ``weighting_method``
   (EQUAL / MARKET_CAP / SCORE) using the real weighting functions in
   ``src/engines/backtester.py``.
3. Simulates the basket day-by-day over ``[start_date, end_date]`` using
   real ``EODPrice`` history: positions drift with daily returns and are
   reset back to target weights at each rebalance date (per
   ``rebalance_frequency``), with transaction costs charged on the
   turnover at each rebalance.
4. Computes real performance metrics (Sharpe, Sortino, max drawdown, beta,
   tracking error, information ratio, ...) via the exact same
   ``compute_performance_metrics`` used by the technical backtester.
5. Persists a ``BacktestResult`` row and flips the run to COMPLETED, or to
   FAILED on any error / no-data condition.

Known simplification: there is no point-in-time historical fundamentals
store in this codebase, so the basket is screened once against today's
live ``AnalyticsResult`` data rather than being re-screened at each
historical rebalance date the way a full point-in-time backtest would be.
Everything downstream of basket selection (weighting, simulation,
transaction costs, performance math) is real, not stubbed.

``BacktestRun`` has no error-message column (and this script does not
touch models/migrations), so on failure the error is recorded in the
paired ``BacktestResult.sector_attribution`` JSON field as
``{"error": "..."}`` instead.

Usage:
    python -m scripts.run_backtest_worker              # poll until idle, then exit
    python -m scripts.run_backtest_worker --loop        # poll forever
    python -m scripts.run_backtest_worker --once         # single pass, exit immediately
    python -m scripts.run_backtest_worker --status       # print run counts by status

Not wired into ``src/scheduler/batch_config.py`` or the ``Makefile`` by
this change -- both are outside this task's touched-file allowlist.
Whoever owns those should register a recurring job equivalent to:
    python -m scripts.run_backtest_worker --once
"""

from __future__ import annotations

import argparse
import asyncio
import calendar
import logging
import sys
import time
from datetime import date, timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

sys.path.insert(0, ".")

from src.config import settings  # noqa: E402
from src.database import get_session_factory  # noqa: E402
from src.engines.backtester import (  # noqa: E402
    compute_performance_metrics,
    equal_weight_portfolio,
    market_cap_weight_portfolio,
    score_based_weight_portfolio,
)
from src.engines.e4_screening import ScreeningEngine  # noqa: E402
from src.models.analytics import AnalyticsResult  # noqa: E402
from src.models.backtesting import BacktestResult, BacktestRun  # noqa: E402
from src.models.security import EODPrice, SecurityIdentifier  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("backtest_worker")

DEFAULT_POLL_LIMIT = 5
DEFAULT_SLEEP_SECONDS = 20.0

# Common benchmark labels -> tradeable ETF ticker with real EODPrice history.
_BENCHMARK_TICKER_MAP: dict[str, str] = {
    "SP500": "SPY",
    "SPX": "SPY",
    "S&P500": "SPY",
    "NASDAQ100": "QQQ",
    "NASDAQ": "QQQ",
    "RUSSELL1000": "IWB",
    "RUSSELL2000": "IWM",
    "DOW": "DIA",
    "DJIA": "DIA",
}

_FREQ_MONTHS: dict[str, int] = {
    "MONTHLY": 1,
    "QUARTERLY": 3,
    "SEMIANNUAL": 6,
    "SEMIANNUALLY": 6,
    "ANNUAL": 12,
    "ANNUALLY": 12,
    "YEARLY": 12,
}


# ---------------------------------------------------------------------------
# Data loading helpers
# ---------------------------------------------------------------------------

async def _pending_runs(session: AsyncSession, limit: int) -> list[BacktestRun]:
    stmt = (
        select(BacktestRun)
        .where(BacktestRun.status == "PENDING")
        .order_by(BacktestRun.created_at.asc())
        .limit(limit)
    )
    return list((await session.execute(stmt)).scalars().all())


async def _security_id_for_ticker(session: AsyncSession, ticker: str) -> UUID | None:
    return (
        await session.execute(
            select(SecurityIdentifier.security_id).where(
                SecurityIdentifier.identifier_type == "TICKER",
                SecurityIdentifier.identifier_value == ticker,
            ).limit(1)
        )
    ).scalar_one_or_none()


async def _price_series(
    session: AsyncSession,
    security_ids: list[UUID],
    start_date: date,
    end_date: date,
) -> dict[UUID, dict[date, float]]:
    """Load ``{security_id: {price_date: close_adjusted_or_close}}`` for the range."""
    if not security_ids:
        return {}
    rows = (
        await session.execute(
            select(
                EODPrice.security_id, EODPrice.price_date,
                EODPrice.close_adjusted, EODPrice.close,
            ).where(
                EODPrice.security_id.in_(security_ids),
                EODPrice.price_date >= start_date,
                EODPrice.price_date <= end_date,
            ).order_by(EODPrice.security_id, EODPrice.price_date)
        )
    ).all()
    series: dict[UUID, dict[date, float]] = {}
    for sid, pdate, close_adj, close in rows:
        px = float(close_adj) if close_adj is not None else (float(close) if close is not None else None)
        if px is None or px <= 0:
            continue
        series.setdefault(sid, {})[pdate] = px
    return series


async def _bulk_latest_metric(
    session: AsyncSession, security_ids: list[UUID], metric_name: str,
) -> dict[UUID, float]:
    """Most recent non-null ``AnalyticsResult`` value per security for one metric."""
    if not security_ids:
        return {}
    ranked = (
        select(
            AnalyticsResult.security_id,
            AnalyticsResult.value,
            func.row_number().over(
                partition_by=AnalyticsResult.security_id,
                order_by=AnalyticsResult.as_of_date.desc(),
            ).label("rn"),
        ).where(
            AnalyticsResult.security_id.in_(security_ids),
            AnalyticsResult.metric_name == metric_name,
            AnalyticsResult.value.isnot(None),
        ).subquery()
    )
    rows = (
        await session.execute(
            select(ranked.c.security_id, ranked.c.value).where(ranked.c.rn == 1)
        )
    ).all()
    return {sid: float(val) for sid, val in rows}


# ---------------------------------------------------------------------------
# Pure computation helpers (no DB access -- easy to unit test / dry-run)
# ---------------------------------------------------------------------------

def rebalance_dates(start: date, end: date, frequency: str) -> list[date]:
    """Generate rebalance dates from ``start`` to ``end`` at ``frequency``.

    ``start`` is always included (initial portfolio construction). Supports
    DAILY, WEEKLY, MONTHLY, QUARTERLY, SEMIANNUAL, ANNUAL; unrecognized
    frequencies fall back to QUARTERLY.
    """
    freq = (frequency or "QUARTERLY").upper()
    dates: list[date] = [start]

    if freq == "DAILY":
        d = start + timedelta(days=1)
        while d <= end:
            dates.append(d)
            d += timedelta(days=1)
        return dates

    if freq == "WEEKLY":
        d = start + timedelta(days=7)
        while d <= end:
            dates.append(d)
            d += timedelta(days=7)
        return dates

    months = _FREQ_MONTHS.get(freq, 3)
    d = start
    while True:
        month_total = d.month - 1 + months
        year = d.year + month_total // 12
        month = month_total % 12 + 1
        day = min(d.day, calendar.monthrange(year, month)[1])
        d = date(year, month, day)
        if d > end:
            break
        dates.append(d)
    return dates


def weights_for_method(
    method: str,
    security_ids: list[str],
    market_caps: dict[str, float],
    scores: dict[str, float],
) -> dict[str, float]:
    """Build target weights using the real weighting functions in backtester.py."""
    m = (method or "EQUAL").upper()
    if m == "MARKET_CAP":
        caps = [market_caps.get(sid, 0.0) for sid in security_ids]
        w = market_cap_weight_portfolio(security_ids, caps)
        if w:
            return w
    elif m == "SCORE":
        sc = [scores.get(sid, 0.0) for sid in security_ids]
        w = score_based_weight_portfolio(security_ids, sc)
        if w:
            return w
    return equal_weight_portfolio(security_ids)


def simulate_basket(
    trading_dates: list[date],
    price_series: dict[UUID, dict[date, float]],
    target_weights: dict[str, float],
    rebalance_set: set[date],
    transaction_cost_bps: float,
) -> tuple[list[float], float, int]:
    """Day-by-day buy-and-hold-with-periodic-rebalance simulation.

    Returns ``(daily_returns, total_turnover, total_trades)``. Weights drift
    with each holding's daily return; at each date in ``rebalance_set`` the
    portfolio is reset to ``target_weights`` and a transaction-cost drag
    (``turnover * cost_bps``) is applied to that day's return.
    """
    cost_factor = transaction_cost_bps / 10000.0
    weights = dict(target_weights)
    prev_prices: dict[str, float] = {}
    daily_returns: list[float] = []
    total_turnover = 0.0
    total_trades = 0

    for i, d in enumerate(trading_dates):
        if i == 0:
            for sid_str in weights:
                px = price_series.get(UUID(sid_str), {}).get(d)
                if px is not None:
                    prev_prices[sid_str] = px
            daily_returns.append(0.0)
            continue

        day_return = 0.0
        grown: dict[str, float] = {}
        total_after = 0.0
        for sid_str, w in weights.items():
            sid = UUID(sid_str)
            px_today = price_series.get(sid, {}).get(d)
            px_prev = prev_prices.get(sid_str)
            r = 0.0
            if px_today is not None and px_prev is not None and px_prev > 0:
                r = (px_today - px_prev) / px_prev
            if px_today is not None:
                prev_prices[sid_str] = px_today
            day_return += w * r
            g = w * (1 + r)
            grown[sid_str] = g
            total_after += g

        if total_after > 0:
            weights = {k: v / total_after for k, v in grown.items()}
        else:
            weights = grown

        if d in rebalance_set:
            all_sids = set(weights) | set(target_weights)
            turnover = sum(
                abs(weights.get(s, 0.0) - target_weights.get(s, 0.0)) for s in all_sids
            ) / 2.0
            if turnover > 1e-6:
                day_return -= turnover * cost_factor
                total_turnover += turnover
                total_trades += len(target_weights)
            weights = dict(target_weights)

        daily_returns.append(day_return)

    return daily_returns, total_turnover, total_trades


def benchmark_daily_returns(dates: list[date], series: dict[date, float]) -> list[float]:
    """Daily simple returns of ``series`` aligned to ``dates`` (0.0 where unknown)."""
    returns = [0.0]
    prev = series.get(dates[0]) if dates else None
    for d in dates[1:]:
        px = series.get(d)
        if px is not None and prev is not None and prev > 0:
            returns.append((px - prev) / prev)
            prev = px
        else:
            returns.append(0.0)
            if px is not None:
                prev = px
    return returns


def compound_return(returns: list[float]) -> float:
    cum = 1.0
    for r in returns:
        cum *= (1 + r)
    return cum - 1.0


def monthly_returns_from_daily(dates: list[date], returns: list[float]) -> dict[str, float]:
    buckets: dict[str, float] = {}
    for d, r in zip(dates, returns):
        key = d.strftime("%Y-%m")
        buckets[key] = (1 + buckets[key]) * (1 + r) - 1 if key in buckets else r
    return {k: round(v, 6) for k, v in buckets.items()}


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

async def _fail_run(
    session: AsyncSession, run: BacktestRun, message: str,
) -> None:
    logger.warning("Backtest %s failed: %s", run.backtest_id, message)
    session.add(BacktestResult(
        backtest_id=run.backtest_id,
        sector_attribution={"error": message[:2000]},
    ))
    run.status = "FAILED"
    await session.commit()


async def process_backtest_run(session: AsyncSession, run: BacktestRun) -> None:
    """Compute and persist real results for one PENDING ``BacktestRun``."""
    try:
        strategy = run.strategy_definition or {}
        engine = ScreeningEngine()
        limit = run.max_positions or 30
        screen_result = await engine.run_screen_from_dict(session, strategy, limit=limit)
        securities = screen_result.securities
        if not securities:
            await _fail_run(session, run, "No securities matched the strategy filters.")
            return

        security_ids = [s.security_id for s in securities]
        sid_strs = [str(sid) for sid in security_ids]
        name_map = {str(s.security_id): s.name for s in securities}
        score_map = {
            str(s.security_id): s.composite_score for s in securities
            if s.composite_score is not None
        }

        market_caps_raw = await _bulk_latest_metric(session, security_ids, "market_cap")
        market_cap_map = {str(sid): v for sid, v in market_caps_raw.items()}

        target_weights = weights_for_method(
            run.weighting_method, sid_strs, market_cap_map, score_map,
        )
        if not target_weights:
            await _fail_run(session, run, "Could not compute portfolio weights for the selected securities.")
            return

        price_series = await _price_series(session, security_ids, run.start_date, run.end_date)

        benchmark_ticker = _BENCHMARK_TICKER_MAP.get(
            (run.benchmark or "").upper(), (run.benchmark or settings.ANALYTICS_MARKET_BENCHMARK_TICKER).upper(),
        )
        bench_sid = await _security_id_for_ticker(session, benchmark_ticker)
        bench_series: dict[date, float] = {}
        if bench_sid is not None:
            bench_series = (await _price_series(session, [bench_sid], run.start_date, run.end_date)).get(bench_sid, {})

        if bench_series:
            trading_dates = sorted(d for d in bench_series if run.start_date <= d <= run.end_date)
        else:
            all_dates: set[date] = set()
            for s in price_series.values():
                all_dates.update(s.keys())
            trading_dates = sorted(d for d in all_dates if run.start_date <= d <= run.end_date)

        if len(trading_dates) < 2:
            await _fail_run(
                session, run,
                "Insufficient EOD price history for the requested date range.",
            )
            return

        rb_dates = [d for d in rebalance_dates(run.start_date, run.end_date, run.rebalance_frequency) if d in trading_dates]
        rebalance_set = set(rb_dates) | {trading_dates[0]}

        daily_returns, total_turnover, total_trades = simulate_basket(
            trading_dates, price_series, target_weights, rebalance_set,
            float(run.transaction_cost_bps) if run.transaction_cost_bps is not None else 10.0,
        )
        bench_returns = benchmark_daily_returns(trading_dates, bench_series) if bench_series else None

        performance = compute_performance_metrics(daily_returns, bench_returns)

        benchmark_return = compound_return(bench_returns) if bench_returns else None
        excess_return = (
            performance.total_return - benchmark_return if benchmark_return is not None else None
        )
        years = len(trading_dates) / 252.0
        turnover_annual = round(total_turnover / years, 4) if years > 0 else None

        holdings_snapshot = [
            {"security_id": sid, "weight": round(w, 6), "name": name_map.get(sid)}
            for sid, w in target_weights.items()
        ]
        period_holdings = {d.isoformat(): holdings_snapshot for d in rb_dates}

        result = BacktestResult(
            backtest_id=run.backtest_id,
            total_return=performance.total_return,
            annualized_return=performance.annualized_return,
            benchmark_return=round(benchmark_return, 6) if benchmark_return is not None else None,
            excess_return=round(excess_return, 6) if excess_return is not None else None,
            sharpe_ratio=performance.sharpe_ratio,
            sortino_ratio=performance.sortino_ratio,
            max_drawdown=performance.max_drawdown,
            max_drawdown_duration_days=performance.max_drawdown_duration_days,
            annualized_volatility=performance.annualized_volatility,
            beta=performance.beta,
            tracking_error=performance.tracking_error,
            information_ratio=performance.information_ratio,
            win_rate=performance.win_rate,
            avg_win=performance.avg_win,
            avg_loss=performance.avg_loss,
            turnover_annual=turnover_annual,
            total_trades=total_trades,
            monthly_returns=monthly_returns_from_daily(trading_dates, daily_returns),
            period_holdings=period_holdings,
        )
        session.add(result)
        run.status = "COMPLETED"
        await session.commit()
        logger.info(
            "Backtest %s completed: %d securities, %d trading days, total_return=%.2f%%",
            run.backtest_id, len(securities), len(trading_dates), performance.total_return * 100,
        )
    except Exception as exc:
        logger.exception("Backtest %s raised an exception", run.backtest_id)
        await session.rollback()
        await _fail_run(session, run, f"{type(exc).__name__}: {exc}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

async def poll_once(limit: int = DEFAULT_POLL_LIMIT) -> int:
    """Process up to ``limit`` PENDING runs. Returns the number processed."""
    async with get_session_factory()() as session:
        runs = await _pending_runs(session, limit)
        for run in runs:
            await process_backtest_run(session, run)
        return len(runs)


async def print_status() -> None:
    async with get_session_factory()() as session:
        rows = (
            await session.execute(
                select(BacktestRun.status, func.count()).group_by(BacktestRun.status)
            )
        ).all()
        print("\nBacktestRun status counts:")
        if not rows:
            print("  (no backtest runs)")
        for status, count in rows:
            print(f"  {status:12} {count}")
        print()


async def run_loop(limit: int, sleep_seconds: float, max_minutes: float | None, loop_forever: bool) -> None:
    start = time.monotonic()
    deadline = start + max_minutes * 60 if max_minutes else None
    while True:
        if deadline and time.monotonic() > deadline:
            logger.info("Time budget reached — stopping.")
            return
        processed = await poll_once(limit)
        if processed:
            logger.info("Processed %d pending backtest run(s).", processed)
        elif not loop_forever:
            logger.info("No pending backtest runs — exiting.")
            return
        else:
            await asyncio.sleep(sleep_seconds)


def main() -> None:
    parser = argparse.ArgumentParser(description="Backtest batch worker (advances PENDING BacktestRun rows)")
    parser.add_argument("--status", action="store_true", help="Print run counts by status and exit")
    parser.add_argument("--once", action="store_true", help="Process a single batch of pending runs and exit")
    parser.add_argument("--loop", action="store_true", help="Poll forever (until --max-minutes, if set)")
    parser.add_argument("--limit", type=int, default=DEFAULT_POLL_LIMIT, help="Max pending runs per poll")
    parser.add_argument("--sleep-seconds", type=float, default=DEFAULT_SLEEP_SECONDS)
    parser.add_argument("--max-minutes", type=float, default=None, help="Wall-clock budget for --loop")
    args = parser.parse_args()

    if args.status:
        asyncio.run(print_status())
        return
    if args.once:
        processed = asyncio.run(poll_once(args.limit))
        logger.info("Processed %d pending backtest run(s).", processed)
        return
    asyncio.run(run_loop(args.limit, args.sleep_seconds, args.max_minutes, args.loop))


if __name__ == "__main__":
    main()
