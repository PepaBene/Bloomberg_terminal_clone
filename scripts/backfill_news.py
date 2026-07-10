"""Pillar 3: Resumable Finnhub news backfill — one company at a time.

Fetches company news from Finnhub for every entity that has a stock TICKER and
links it into ``news_articles`` + ``article_entity_links``. Mirrors the
resumable-backfill design of ``scripts.backfill``:

  * A ``ingestion_progress`` row per (data_type='news', subject=entity_id)
    records SUCCESS / NO_DATA / PENDING so work is never repeated and dead-ends
    aren't retried forever.
  * Processes only the *next* un-done entities, commits per small batch, and
    stops cleanly once ``--max-minutes`` elapses — so it always exits gracefully
    before anything external kills it.
  * Finnhub's free tier is ~60 req/min; the connector carries an internal
    RateLimiter (30/60s). We create ONE connector instance and reuse it across
    every entity so that limiter throttles the whole run — calls are strictly
    SEQUENTIAL (never parallelized).

Run it repeatedly (or via scripts.run_news_loop) and it converges to full
coverage.

Usage:
    python -m scripts.backfill_news --status
    python -m scripts.backfill_news --batch-size 20 --max-minutes 8 --days 30
    python -m scripts.backfill_news --refresh-days 3   # re-queue stale entities
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

from src.database import get_session_factory  # noqa: E402
from src.ingestion.finnhub_news import FinnhubNewsConnector  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("backfill_news")

DATA_TYPE = "news"
MAX_ATTEMPTS = 3  # give up on an entity (mark NO_DATA) after this many failures


# --------------------------------------------------------------------------- #
# Subject set + progress helpers
# --------------------------------------------------------------------------- #
# One (entity_id, ticker) per issuer entity. An entity may back several
# securities/tickers; MIN() picks a single deterministic ticker to query.
_TICKER_SUBQUERY = """
    SELECT s.issuer_entity_id AS entity_id, MIN(si.identifier_value) AS ticker
    FROM securities s
    JOIN security_identifiers si
      ON si.security_id = s.security_id AND si.identifier_type = 'TICKER'
    WHERE s.issuer_entity_id IS NOT NULL
    GROUP BY s.issuer_entity_id
"""


async def _total_subjects(session: AsyncSession) -> int:
    return int(
        await session.scalar(text(f"SELECT count(*) FROM ({_TICKER_SUBQUERY}) t")) or 0
    )


async def _pending(
    session: AsyncSession, limit: int
) -> list[tuple[uuid.UUID, str]]:
    """Next batch of (entity_id, ticker) not yet done for news."""
    rows = await session.execute(
        text(
            f"""
            SELECT t.entity_id, t.ticker
            FROM ({_TICKER_SUBQUERY}) t
            LEFT JOIN ingestion_progress ip
              ON ip.data_type = :dt AND ip.subject_key = t.entity_id::text
            WHERE (ip.id IS NULL OR (ip.status = 'PENDING' AND ip.attempts < :max))
            ORDER BY ip.last_attempt_at ASC NULLS FIRST, t.ticker
            LIMIT :n
            """
        ),
        {"dt": DATA_TYPE, "max": MAX_ATTEMPTS, "n": limit},
    )
    return [(r[0], r[1]) for r in rows.all()]


async def _record(
    session: AsyncSession,
    entity_id: uuid.UUID,
    *,
    success: bool,
    rows: int = 0,
    error: str | None = None,
) -> None:
    """Upsert a progress row.

    On a clean fetch (no exception) the entity is marked SUCCESS regardless of
    article count — a company that legitimately has zero recent headlines must
    not be retried forever. Only an actual fetch/commit *error* leaves it
    PENDING (retried until MAX_ATTEMPTS, then NO_DATA).
    """
    now = datetime.now(timezone.utc)
    sk = str(entity_id)
    prior = await session.scalar(
        text(
            "SELECT attempts FROM ingestion_progress "
            "WHERE data_type = :dt AND subject_key = :sk"
        ),
        {"dt": DATA_TYPE, "sk": sk},
    )
    attempts = (prior or 0) + 1
    if success:
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
            "dt": DATA_TYPE,
            "sk": sk,
            "eid": entity_id,
            "status": status,
            "attempts": attempts,
            "rows": rows,
            "now": now,
            "success_at": success_at,
            "err": (error or None)[:400] if error else None,
        },
    )


# --------------------------------------------------------------------------- #
# Backfill driver
# --------------------------------------------------------------------------- #
async def run(
    *, batch_size: int, max_minutes: float, days: int, refresh_days: int
) -> None:
    deadline = time.monotonic() + max_minutes * 60
    # ONE connector → its internal RateLimiter throttles the entire run.
    connector = FinnhubNewsConnector()
    if not connector.api_key:
        logger.warning(
            "FINNHUB_API_KEY not set — fetches will no-op (0 articles). "
            "Entities are still marked done so the ledger converges."
        )

    async with get_session_factory()() as session:
        if refresh_days > 0:
            await reopen_stale(session, refresh_days)

        processed = 0
        new_articles = 0
        while time.monotonic() < deadline:
            batch = await _pending(session, batch_size)
            if not batch:
                logger.info("No remaining entities — news backfill complete.")
                break
            for entity_id, ticker in batch:
                if time.monotonic() > deadline:
                    break
                err: str | None = None
                count = 0
                try:
                    # fetch_for_entity commits its own article/link writes.
                    count = await connector.fetch_for_entity(
                        session, entity_id, ticker, days=days
                    )
                except Exception as e:  # network / DB — retry this entity later
                    await session.rollback()
                    err = f"{type(e).__name__}: {e}"
                    logger.warning("[news] %s (%s) failed: %s", ticker, entity_id, err)
                await _record(
                    session, entity_id,
                    success=(err is None), rows=count, error=err,
                )
                await session.commit()
                processed += 1
                new_articles += count
                if processed % batch_size == 0:
                    logger.info(
                        "[news] processed %d entities (%d new articles so far)",
                        processed, new_articles,
                    )

        logger.info(
            "News chunk done: %d entities processed, %d new articles this run.",
            processed, new_articles,
        )
        await print_status(session)


# --------------------------------------------------------------------------- #
# Refresh — re-queue entities whose news has gone stale
# --------------------------------------------------------------------------- #
async def reopen_stale(session: AsyncSession, days: int) -> int:
    """Flip SUCCESS/NO_DATA rows older than ``days`` back to PENDING so the next
    pass re-fetches fresh headlines (dedup by source_url keeps it idempotent)."""
    result = await session.execute(
        text(
            """
            UPDATE ingestion_progress
            SET status = 'PENDING', attempts = 0, updated_at = now()
            WHERE data_type = :dt
              AND status IN ('SUCCESS', 'NO_DATA')
              AND COALESCE(last_success_at, last_attempt_at)
                  < now() - make_interval(days => :days)
            """
        ),
        {"dt": DATA_TYPE, "days": days},
    )
    await session.commit()
    n = result.rowcount or 0
    logger.info("Reopened %d stale news subjects for refresh (older than %dd).", n, days)
    return n


# --------------------------------------------------------------------------- #
# Status
# --------------------------------------------------------------------------- #
async def print_status(session: AsyncSession) -> None:
    total = await _total_subjects(session)
    counts = dict(
        (r[0], r[1])
        for r in (
            await session.execute(
                text(
                    "SELECT status, count(*) FROM ingestion_progress "
                    "WHERE data_type=:dt GROUP BY status"
                ),
                {"dt": DATA_TYPE},
            )
        ).all()
    )
    succ = counts.get("SUCCESS", 0)
    nodata = counts.get("NO_DATA", 0)
    pend = counts.get("PENDING", 0)
    done = succ + nodata
    remaining = total - done
    cov = (done / total * 100) if total else 0.0
    articles = await session.scalar(text("SELECT count(*) FROM news_articles")) or 0
    links = await session.scalar(
        text("SELECT count(*) FROM article_entity_links")
    ) or 0
    print(f"\nNews universe: {total} entities with a TICKER\n")
    print(f"{'SUCCESS':>9} {'NO_DATA':>9} {'PENDING':>9} {'remaining':>10} {'coverage':>9}")
    print("-" * 50)
    print(f"{succ:>9} {nodata:>9} {pend:>9} {remaining:>10} {cov:>8.1f}%")
    print(f"\nnews_articles rows: {articles}   article_entity_links: {links}")
    print("STATUS: COMPLETE" if remaining <= 0 and total > 0 else "STATUS: in progress")
    print()


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Resumable Finnhub news backfill")
    p.add_argument("--status", action="store_true", help="Print coverage and exit")
    p.add_argument("--batch-size", type=int, default=20,
                   help="Entities per commit batch / log interval")
    p.add_argument("--max-minutes", type=float, default=8.0, help="Wall-clock budget")
    p.add_argument("--days", type=int, default=30,
                   help="Look-back window of news to fetch per entity")
    p.add_argument("--refresh-days", type=int, default=0,
                   help="Before running, re-queue entities last refreshed more "
                        "than N days ago (0 = disabled)")
    return p.parse_args()


async def _main() -> None:
    args = parse_args()
    if args.status:
        async with get_session_factory()() as session:
            await print_status(session)
        return
    await run(
        batch_size=args.batch_size,
        max_minutes=args.max_minutes,
        days=args.days,
        refresh_days=args.refresh_days,
    )


if __name__ == "__main__":
    asyncio.run(_main())
