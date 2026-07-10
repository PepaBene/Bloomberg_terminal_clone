"""Pillar 3: Resumable sentiment builder — news_articles → sentiment_scores +
sentiment_aggregates.

This is the batch form of the ``refresh_sentiment`` API endpoint. For each
entity that HAS ingested news it runs the *exact same* two helpers the endpoint
uses (imported, not reimplemented):

  * ``_score_entity_news``   — scores linked news_articles into sentiment_scores
                               via the keyword engine (idempotent).
  * ``_rebuild_aggregate``   — rolls those scores into a persisted
                               sentiment_aggregates row via
                               ``compute_aggregate_sentiment``.

The keyword scorer needs no LLM, so an empty ANTHROPIC_API_KEY is a non-issue —
this path never touches the LLM client and cannot crash on a missing key.

Resumable like the other batch runners: per-entity progress in
``ingestion_progress`` (data_type='sentiment'), commit + mark done per chunk,
skip already-done entities, honor ``--max-minutes``.

Usage:
    python -m scripts.compute_sentiment --status
    python -m scripts.compute_sentiment --max-minutes 10
    python -m scripts.compute_sentiment --timeframes ROLLING_30D
    python -m scripts.compute_sentiment --refresh-days 3
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
# Reuse the endpoint's own producers verbatim — do NOT reimplement scoring.
from src.api.routers.sentiment import (  # noqa: E402
    _rebuild_aggregate,
    _score_entity_news,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("compute_sentiment")

DATA_TYPE = "sentiment"
MAX_ATTEMPTS = 3
CHUNK_SIZE = 50
DEFAULT_TIMEFRAMES = ["ROLLING_7D", "ROLLING_30D", "ROLLING_90D"]


# --------------------------------------------------------------------------- #
# Subject set + progress helpers
# --------------------------------------------------------------------------- #
async def _total_subjects(session: AsyncSession) -> int:
    return int(
        await session.scalar(
            text("SELECT count(DISTINCT entity_id) FROM article_entity_links")
        )
        or 0
    )


async def _pending(session: AsyncSession, limit: int) -> list[uuid.UUID]:
    """Next batch of entity_ids that HAVE news but aren't done for sentiment."""
    rows = await session.execute(
        text(
            """
            SELECT DISTINCT ael.entity_id
            FROM article_entity_links ael
            LEFT JOIN ingestion_progress ip
              ON ip.data_type = :dt AND ip.subject_key = ael.entity_id::text
            WHERE (ip.id IS NULL OR (ip.status = 'PENDING' AND ip.attempts < :max))
            ORDER BY ael.entity_id
            LIMIT :n
            """
        ),
        {"dt": DATA_TYPE, "max": MAX_ATTEMPTS, "n": limit},
    )
    return [r[0] for r in rows.all()]


async def _record(
    session: AsyncSession,
    entity_id: uuid.UUID,
    *,
    success: bool,
    rows: int = 0,
    error: str | None = None,
) -> None:
    """Upsert a progress row (SUCCESS on clean run, else PENDING→NO_DATA)."""
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
# Compute driver
# --------------------------------------------------------------------------- #
async def _process_entity(
    session: AsyncSession, entity_id: uuid.UUID, timeframes: list[str]
) -> int:
    """Replicate refresh_sentiment for one entity: score its news, then rebuild
    each timeframe's aggregate. Returns count of newly-scored articles."""
    scored = await _score_entity_news(session, entity_id)
    for tf in timeframes:
        await _rebuild_aggregate(session, entity_id, tf)
    return scored


async def run(
    *, max_minutes: float, timeframes: list[str], refresh_days: int
) -> None:
    deadline = time.monotonic() + max_minutes * 60
    async with get_session_factory()() as session:
        if refresh_days > 0:
            await reopen_stale(session, refresh_days)

        processed = 0
        total_scored = 0
        while time.monotonic() < deadline:
            batch = await _pending(session, CHUNK_SIZE)
            if not batch:
                logger.info("No remaining entities — sentiment build complete.")
                break
            for entity_id in batch:
                if time.monotonic() > deadline:
                    break
                err: str | None = None
                scored = 0
                try:
                    scored = await _process_entity(session, entity_id, timeframes)
                except Exception as e:  # per-entity failure — retry later
                    await session.rollback()
                    err = f"{type(e).__name__}: {e}"
                    logger.warning("[sentiment] %s failed: %s", entity_id, err)
                await _record(
                    session, entity_id,
                    success=(err is None), rows=scored, error=err,
                )
                await session.commit()
                processed += 1
                total_scored += scored
            logger.info(
                "[sentiment] processed %d entities (%d scores created so far)",
                processed, total_scored,
            )

        logger.info(
            "Sentiment chunk done: %d entities, %d new scores this run.",
            processed, total_scored,
        )
        await print_status(session)


async def reopen_stale(session: AsyncSession, days: int) -> int:
    """Re-queue entities whose sentiment was last built more than ``days`` ago,
    so newly-ingested news gets re-scored and aggregates refreshed."""
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
    logger.info("Reopened %d stale sentiment subjects (older than %dd).", n, days)
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
    scores = await session.scalar(text("SELECT count(*) FROM sentiment_scores")) or 0
    aggs = await session.scalar(text("SELECT count(*) FROM sentiment_aggregates")) or 0
    print(f"\nSentiment universe: {total} entities with news\n")
    print(f"{'SUCCESS':>9} {'NO_DATA':>9} {'PENDING':>9} {'remaining':>10} {'coverage':>9}")
    print("-" * 50)
    print(f"{succ:>9} {nodata:>9} {pend:>9} {remaining:>10} {cov:>8.1f}%")
    print(f"\nsentiment_scores rows: {scores}   sentiment_aggregates rows: {aggs}")
    print("STATUS: COMPLETE" if remaining <= 0 and total > 0 else "STATUS: in progress")
    print()


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Resumable sentiment score/aggregate builder")
    p.add_argument("--status", action="store_true", help="Print coverage and exit")
    p.add_argument("--max-minutes", type=float, default=10.0, help="Wall-clock budget")
    p.add_argument("--timeframes", nargs="+", default=DEFAULT_TIMEFRAMES,
                   choices=["ROLLING_7D", "ROLLING_30D", "ROLLING_90D"],
                   help="Aggregate timeframes to (re)build per entity")
    p.add_argument("--refresh-days", type=int, default=0,
                   help="Before running, re-queue entities last built more than "
                        "N days ago (0 = disabled)")
    return p.parse_args()


async def _main() -> None:
    args = parse_args()
    if args.status:
        async with get_session_factory()() as session:
            await print_status(session)
        return
    await run(
        max_minutes=args.max_minutes,
        timeframes=args.timeframes,
        refresh_days=args.refresh_days,
    )


if __name__ == "__main__":
    asyncio.run(_main())
