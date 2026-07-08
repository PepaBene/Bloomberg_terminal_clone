"""Resumable, rate-limit-aware backfill orchestrator.

The problem this solves: a full backfill of every company is far longer than any
single process can run (rate limits + wall-clock), and a killed run must not lose
work or re-fetch what's already done.

Design:
  * A ``ingestion_progress`` row per (data_type, subject) records SUCCESS /
    NO_DATA / PENDING so work is never repeated and dead-ends aren't retried
    forever.
  * The orchestrator processes only the *next* un-done subjects, commits per
    batch, and stops cleanly once a time budget (``--max-minutes``) elapses — so
    it always exits gracefully before anything external kills it.
  * Run it repeatedly (a loop, cron, or Windows Task Scheduler — see BACKFILL.md)
    and it converges to 100% coverage.

Usage:
    python -m scripts.backfill --status
    python -m scripts.backfill --type xbrl --batch-size 25 --max-minutes 8
    python -m scripts.backfill --type prices --batch-size 6
    python -m scripts.backfill --all --max-minutes 20
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import time
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_session_factory
from src.ingestion.edgar_8k import Edgar8KConnector
from src.ingestion.edgar_esg import EdgarESGConnector
from src.ingestion.edgar_xbrl import EdgarXBRLConnector
from src.ingestion.polygon_eod import PolygonEODConnector

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("backfill")

MAX_ATTEMPTS = 3  # give up on a subject (mark NO_DATA) after this many empty tries


# --------------------------------------------------------------------------- #
# Data-type registry
# --------------------------------------------------------------------------- #
@dataclass
class EntityCikType:
    """A company-scoped, CIK-driven SEC data type."""

    key: str
    connector_cls: type
    kwarg: str              # connector constructor arg name for the CIK list
    target_table: str       # table that gets a row when the subject has data
    target_fk: str          # FK column on that table pointing at the entity
    extra_kwargs: dict = field(default_factory=dict)
    kind: str = "entity_cik"


# Registry is intentionally simple to extend: add a connector + its target table.
ENTITY_TYPES: dict[str, EntityCikType] = {
    "xbrl": EntityCikType(
        "xbrl", EdgarXBRLConnector, "ciks", "financial_periods", "entity_id"
    ),
    "corporate_actions": EntityCikType(
        "corporate_actions", Edgar8KConnector, "ciks", "corporate_actions", "entity_id"
    ),
    "esg": EntityCikType(
        "esg", EdgarESGConnector, "cik_list", "esg_scores", "entity_id"
    ),
}
DATE_TYPES = {"prices"}
ALL_TYPES = list(ENTITY_TYPES.keys()) + list(DATE_TYPES)


# --------------------------------------------------------------------------- #
# Progress helpers
# --------------------------------------------------------------------------- #
async def _record(
    session: AsyncSession,
    data_type: str,
    subject_key: str,
    *,
    entity_id: uuid.UUID | None,
    has_data: bool,
    rows: int = 0,
    error: str | None = None,
) -> None:
    """Upsert a progress row, advancing attempts / status appropriately."""
    now = datetime.now(timezone.utc)
    prior = await session.scalar(
        text(
            "SELECT attempts FROM ingestion_progress "
            "WHERE data_type = :dt AND subject_key = :sk"
        ),
        {"dt": data_type, "sk": subject_key},
    )
    attempts = (prior or 0) + 1
    if has_data:
        status, success_at = "SUCCESS", now
    elif attempts >= MAX_ATTEMPTS:
        status, success_at = "NO_DATA", None
    else:
        status, success_at = "PENDING", None

    await session.execute(
        text(
            """
            INSERT INTO ingestion_progress
                (id, data_type, subject_key, entity_id, status, attempts,
                 rows_ingested, last_attempt_at, last_success_at, error,
                 created_at, updated_at)
            VALUES
                (:id, :dt, :sk, :eid, :status, :attempts, :rows, :now,
                 CAST(:success_at AS timestamptz), :err, :now, :now)
            ON CONFLICT (data_type, subject_key) DO UPDATE SET
                status = :status,
                attempts = :attempts,
                rows_ingested = GREATEST(ingestion_progress.rows_ingested, :rows),
                last_attempt_at = :now,
                last_success_at = COALESCE(
                    CAST(:success_at AS timestamptz), ingestion_progress.last_success_at
                ),
                error = :err,
                updated_at = :now
            """
        ),
        {
            "id": uuid.uuid4(),
            "dt": data_type,
            "sk": subject_key,
            "eid": entity_id,
            "status": status,
            "attempts": attempts,
            "rows": rows,
            "now": now,
            "success_at": success_at,
            "err": (error or None),
        },
    )


async def _pending_entities(
    session: AsyncSession, data_type: str, limit: int
) -> list[tuple[uuid.UUID, str]]:
    """Next batch of (entity_id, cik) not yet done for this data type."""
    rows = await session.execute(
        text(
            """
            SELECT ei.entity_id, ei.identifier_value AS cik
            FROM entity_identifiers ei
            LEFT JOIN ingestion_progress ip
              ON ip.data_type = :dt AND ip.subject_key = ei.entity_id::text
            WHERE ei.identifier_type = 'CIK'
              AND (ip.id IS NULL OR (ip.status = 'PENDING' AND ip.attempts < :max))
            ORDER BY ip.last_attempt_at ASC NULLS FIRST, ei.identifier_value
            LIMIT :n
            """
        ),
        {"dt": data_type, "max": MAX_ATTEMPTS, "n": limit},
    )
    return [(r[0], r[1]) for r in rows.all()]


async def _entity_has_data(
    session: AsyncSession, table: str, fk: str, entity_id: uuid.UUID
) -> bool:
    # table/fk are registry constants (never user input) — safe to interpolate.
    return bool(
        await session.scalar(
            text(f"SELECT EXISTS(SELECT 1 FROM {table} WHERE {fk} = :eid)"),
            {"eid": entity_id},
        )
    )


# --------------------------------------------------------------------------- #
# Backfill drivers
# --------------------------------------------------------------------------- #
async def _run_entity_batch(
    session: AsyncSession, cfg: EntityCikType, batch_size: int
) -> int:
    """Process one batch of a CIK-driven type. Returns subjects processed."""
    subjects = await _pending_entities(session, cfg.key, batch_size)
    if not subjects:
        return 0

    ciks = [cik for _, cik in subjects]
    connector = cfg.connector_cls(**{cfg.kwarg: ciks}, **cfg.extra_kwargs)
    err: str | None = None
    try:
        await connector.run(session)
        await session.commit()
    except Exception as e:  # whole-batch failure (e.g. network) — retry later
        await session.rollback()
        err = f"{type(e).__name__}: {e}"[:400]
        logger.warning("[%s] batch failed: %s", cfg.key, err)

    for entity_id, _cik in subjects:
        has = False if err else await _entity_has_data(
            session, cfg.target_table, cfg.target_fk, entity_id
        )
        await _record(
            session, cfg.key, str(entity_id), entity_id=entity_id,
            has_data=has, error=err,
        )
    await session.commit()
    return len(subjects)


async def _pending_price_dates(
    session: AsyncSession, limit: int, lookback_days: int
) -> list[str]:
    """Next batch of trading days (most recent first) with no prices yet."""
    # Pass real date objects — asyncpg encodes a DATE comparison from a date,
    # not an ISO string.
    yesterday = date.today() - timedelta(days=1)
    earliest = date.today() - timedelta(days=lookback_days)
    rows = await session.execute(
        text(
            """
            SELECT DISTINCT td.date::text AS d
            FROM trading_days td
            LEFT JOIN ingestion_progress ip
              ON ip.data_type = 'prices' AND ip.subject_key = td.date::text
            WHERE td.is_trading_day = true
              AND td.date <= :yst AND td.date >= :earliest
              AND (ip.id IS NULL OR (ip.status = 'PENDING' AND ip.attempts < :max))
            ORDER BY d DESC
            LIMIT :n
            """
        ),
        {"yst": yesterday, "earliest": earliest, "max": MAX_ATTEMPTS, "n": limit},
    )
    return [r[0] for r in rows.all()]


async def _run_price_batch(
    session: AsyncSession, batch_size: int, lookback_days: int, deadline: float
) -> int:
    """Fetch grouped-daily prices for the next un-done trading days."""
    dates = await _pending_price_dates(session, batch_size, lookback_days)
    if not dates:
        return 0

    processed = 0
    for idx, d in enumerate(dates):
        if time.monotonic() > deadline:
            break
        err: str | None = None
        try:
            connector = PolygonEODConnector(target_date=d)
            await connector.run(session)
            await session.commit()
        except Exception as e:
            await session.rollback()
            err = f"{type(e).__name__}: {e}"[:400]
            logger.warning("[prices] %s failed: %s", d, err)

        has = False if err else bool(
            await session.scalar(
                text("SELECT EXISTS(SELECT 1 FROM eod_prices WHERE price_date = :d)"),
                {"d": date.fromisoformat(d)},
            )
        )
        await _record(session, "prices", d, entity_id=None, has_data=has, error=err)
        await session.commit()
        processed += 1
        # Respect Polygon's free-tier limit (~5 req/min) between dates.
        if idx < len(dates) - 1 and time.monotonic() < deadline:
            await asyncio.sleep(13)
    return processed


# --------------------------------------------------------------------------- #
# Reconcile — mark subjects that already have data as SUCCESS (no fetching)
# --------------------------------------------------------------------------- #
async def reconcile(session: AsyncSession) -> None:
    """Seed progress from data already in the DB so we never re-fetch it."""
    for cfg in ENTITY_TYPES.values():
        await session.execute(
            text(
                f"""
                INSERT INTO ingestion_progress
                    (id, data_type, subject_key, entity_id, status, attempts,
                     rows_ingested, last_attempt_at, last_success_at, created_at, updated_at)
                SELECT gen_random_uuid(), :dt, d.eid::text, d.eid, 'SUCCESS', 1, 0,
                       now(), now(), now(), now()
                FROM (SELECT DISTINCT {cfg.target_fk} AS eid FROM {cfg.target_table}
                      WHERE {cfg.target_fk} IS NOT NULL) d
                ON CONFLICT (data_type, subject_key) DO NOTHING
                """
            ),
            {"dt": cfg.key},
        )
    await session.execute(
        text(
            """
            INSERT INTO ingestion_progress
                (id, data_type, subject_key, entity_id, status, attempts,
                 rows_ingested, last_attempt_at, last_success_at, created_at, updated_at)
            SELECT gen_random_uuid(), 'prices', d.pd::text, NULL, 'SUCCESS', 1, 0,
                   now(), now(), now(), now()
            FROM (SELECT DISTINCT price_date AS pd FROM eod_prices) d
            ON CONFLICT (data_type, subject_key) DO NOTHING
            """
        )
    )
    await session.commit()
    logger.info("Reconciled progress from existing data.")


# --------------------------------------------------------------------------- #
# Status
# --------------------------------------------------------------------------- #
async def print_status(session: AsyncSession) -> None:
    total_ciks = await session.scalar(
        text("SELECT count(*) FROM entity_identifiers WHERE identifier_type='CIK'")
    )
    print(f"\nUniverse: {total_ciks} companies (by CIK)\n")
    print(f"{'data_type':20} {'SUCCESS':>9} {'NO_DATA':>9} {'PENDING':>9} {'remaining':>10} {'coverage':>9}")
    print("-" * 72)
    for key in ENTITY_TYPES:
        counts = dict(
            (r[0], r[1])
            for r in (
                await session.execute(
                    text(
                        "SELECT status, count(*) FROM ingestion_progress "
                        "WHERE data_type=:k GROUP BY status"
                    ),
                    {"k": key},
                )
            ).all()
        )
        succ = counts.get("SUCCESS", 0)
        nodata = counts.get("NO_DATA", 0)
        pend = counts.get("PENDING", 0)
        done = succ + nodata
        remaining = (total_ciks or 0) - done
        cov = (done / total_ciks * 100) if total_ciks else 0
        print(f"{key:20} {succ:>9} {nodata:>9} {pend:>9} {remaining:>10} {cov:>8.1f}%")

    # Prices coverage (date-based)
    total_days = await session.scalar(
        text(
            "SELECT count(DISTINCT date) FROM trading_days td "
            "JOIN trading_calendars tc ON tc.calendar_id=td.calendar_id "
            "WHERE td.is_trading_day=true AND td.date <= CURRENT_DATE"
        )
    )
    priced = await session.scalar(
        text("SELECT count(*) FROM ingestion_progress WHERE data_type='prices' AND status='SUCCESS'")
    )
    print(f"{'prices (days)':20} {priced or 0:>9} {'-':>9} {'-':>9} {'-':>10} "
          f"{'(recent window)':>9}")
    print()


# --------------------------------------------------------------------------- #
# Refresh — re-queue companies whose data has gone stale
# --------------------------------------------------------------------------- #
async def reopen_stale(session: AsyncSession, days: int) -> int:
    """Re-queue entity subjects last refreshed more than ``days`` ago.

    Companies file new data continuously, so once the historical backfill is
    complete this keeps it fresh: a SUCCESS row older than the window flips back
    to PENDING and the next pass re-fetches it (dedup skips unchanged periods).
    Price days are immutable history, so they're never reopened.
    """
    result = await session.execute(
        text(
            """
            UPDATE ingestion_progress
            SET status = 'PENDING', attempts = 0, updated_at = now()
            WHERE data_type = ANY(:types)
              AND status = 'SUCCESS'
              AND last_success_at < now() - make_interval(days => :days)
            """
        ),
        {"types": list(ENTITY_TYPES.keys()), "days": days},
    )
    await session.commit()
    logger.info("Reopened %d stale subjects for refresh (older than %dd).",
                result.rowcount or 0, days)
    return result.rowcount or 0


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Resumable backfill orchestrator")
    p.add_argument("--type", choices=ALL_TYPES, help="Backfill a single data type")
    p.add_argument("--all", action="store_true", help="Cycle through all data types")
    p.add_argument("--status", action="store_true", help="Print coverage and exit")
    p.add_argument("--reconcile", action="store_true",
                   help="Mark subjects that already have data as done, then exit")
    p.add_argument("--batch-size", type=int, default=25, help="Subjects per batch")
    p.add_argument("--max-minutes", type=float, default=8.0, help="Wall-clock budget")
    p.add_argument("--prices-lookback-days", type=int, default=120,
                   help="How far back to backfill daily prices")
    p.add_argument("--refresh-days", type=int, default=0,
                   help="Before running, re-queue companies last refreshed more "
                        "than N days ago (0 = disabled)")
    return p.parse_args()


async def _backfill_type(session, key, args, deadline) -> int:
    if key == "prices":
        return await _run_price_batch(
            session, args.batch_size, args.prices_lookback_days, deadline
        )
    return await _run_entity_batch(session, ENTITY_TYPES[key], args.batch_size)


async def main() -> None:
    args = parse_args()
    async with get_session_factory()() as session:
        if args.reconcile:
            await reconcile(session)
            await print_status(session)
            return
        if args.status or (not args.type and not args.all):
            await print_status(session)
            return

        if args.refresh_days > 0:
            await reopen_stale(session, args.refresh_days)

        deadline = time.monotonic() + args.max_minutes * 60
        types = ALL_TYPES if args.all else [args.type]
        totals = {t: 0 for t in types}
        # Round-robin so --all spreads the budget across types.
        idx = 0
        exhausted: set[str] = set()
        while time.monotonic() < deadline and len(exhausted) < len(types):
            key = types[idx % len(types)]
            idx += 1
            if key in exhausted:
                continue
            n = await _backfill_type(session, key, args, deadline)
            totals[key] += n
            if n == 0:
                exhausted.add(key)
                logger.info("[%s] no remaining subjects — complete", key)
            else:
                logger.info("[%s] processed %d (running total %d)", key, n, totals[key])

        elapsed = args.max_minutes * 60 - max(0.0, deadline - time.monotonic())
        logger.info("Backfill chunk done in %.0fs. Processed: %s", elapsed, totals)
        await print_status(session)


if __name__ == "__main__":
    asyncio.run(main())
