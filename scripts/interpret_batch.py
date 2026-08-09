"""Nightly batch job for Layer 1 (Interpreter) — AI_THREE_LAYER_REBUILD_PLAN.md §3.5.

Resumable via the existing ``ingestion_progress`` ledger, the same
keyless-raw-SQL pattern ``scripts/backfill.py`` already uses for every other
resumable batch type (no ORM model exists for this table -- see migration
083). ``data_type="interpreter"``, ``subject_key=str(entity_id)``.

Universe sourcing (the "active universe/watchlists/portfolios" §3.5 calls
for): entities that appear in at least one ``portfolio_watchlist_entries``
row, union any explicit ``--entity-ids``. ``--all`` instead sweeps every
covered entity in ``entity_identifiers`` -- expensive (interprets the
entire company universe, not just watched/held ones), meant for a small
test universe, not a real nightly production run.

NOT yet wired: portfolio HOLDINGS (``positions``). ``Position`` has no
direct ``entity_id`` column (keyed by ticker/security within a portfolio);
joining through to ``Security.issuer_entity_id`` to fold holdings into the
universe is a real, mechanical follow-up, just not done in this pass.

Each entity is processed via ``get_or_compute_entity_interpretation``,
which already skips any LLM call for metrics whose cached row is still
fresh (matching ``analytics_version``) -- so re-running this nightly
against an unchanged entity is cheap, not a full recompute. The
``ingestion_progress`` ledger's role here is resumability across a
time-budgeted run and NO_DATA tracking (entities with no analytics at all
yet), not a second freshness check duplicating the cache's own.

Usage:
    python scripts/interpret_batch.py --status
    python scripts/interpret_batch.py --max-minutes 15
    python scripts/interpret_batch.py --entity-ids <uuid>,<uuid> --dry-run
    python scripts/interpret_batch.py --all --limit 50   # small test universe
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

from sqlalchemy import bindparam, text

from src.ai.client import get_ai_client
from src.ai.interpret.store import get_or_compute_entity_interpretation
from src.database import get_session_factory

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("interpret_batch")

DATA_TYPE = "interpreter"
MAX_ATTEMPTS = 3


async def _watchlist_universe(session) -> list[uuid.UUID]:
    rows = (
        await session.execute(text("SELECT DISTINCT entity_id FROM portfolio_watchlist_entries"))
    ).all()
    return [r[0] for r in rows]


async def _all_covered_entities(session) -> list[uuid.UUID]:
    rows = (
        await session.execute(
            text("SELECT DISTINCT entity_id FROM entity_identifiers WHERE identifier_type = 'CIK'")
        )
    ).all()
    return [r[0] for r in rows]


async def _progress_status(session, subject_keys: list[str]) -> dict[str, dict]:
    """``{subject_key: {status, attempts, last_success_at}}`` for today's runs."""
    if not subject_keys:
        return {}
    query = text(
        """
        SELECT subject_key, status, attempts, last_success_at
        FROM ingestion_progress
        WHERE data_type = :dt AND subject_key IN :keys
        """
    ).bindparams(bindparam("keys", expanding=True))
    rows = (await session.execute(query, {"dt": DATA_TYPE, "keys": subject_keys})).all()
    return {
        r.subject_key: {"status": r.status, "attempts": r.attempts, "last_success_at": r.last_success_at}
        for r in rows
    }


async def _record(session, entity_id: uuid.UUID, *, has_data: bool, error: str | None = None) -> None:
    """Upsert one entity's progress row, advancing attempts/status."""
    subject_key = str(entity_id)
    now = datetime.now(timezone.utc)
    prior = await session.scalar(
        text(
            "SELECT attempts FROM ingestion_progress WHERE data_type = :dt AND subject_key = :sk"
        ),
        {"dt": DATA_TYPE, "sk": subject_key},
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
                 rows_ingested, last_attempt_at, last_success_at, error, created_at, updated_at)
            VALUES
                (:id, :dt, :sk, :eid, :status, :attempts, :rows, :now,
                 CAST(:success_at AS timestamptz), :err, :now, :now)
            ON CONFLICT (data_type, subject_key) DO UPDATE SET
                status = :status,
                attempts = :attempts,
                rows_ingested = ingestion_progress.rows_ingested + :rows,
                last_attempt_at = :now,
                last_success_at = COALESCE(CAST(:success_at AS timestamptz), ingestion_progress.last_success_at),
                error = :err,
                updated_at = :now
            """
        ),
        {
            "id": uuid.uuid4(), "dt": DATA_TYPE, "sk": subject_key, "eid": entity_id,
            "status": status, "attempts": attempts, "rows": 1 if has_data else 0,
            "now": now, "success_at": success_at, "err": (error or None),
        },
    )


async def print_status(session, universe: list[uuid.UUID]) -> None:
    keys = [str(e) for e in universe]
    progress = await _progress_status(session, keys)
    succ = sum(1 for p in progress.values() if p["status"] == "SUCCESS")
    nodata = sum(1 for p in progress.values() if p["status"] == "NO_DATA")
    pend = len(universe) - succ - nodata
    print(f"\nInterpreter universe: {len(universe)} entities")
    print(f"  SUCCESS: {succ}  NO_DATA: {nodata}  PENDING/unattempted: {pend}\n")


async def run_batch(
    universe: list[uuid.UUID],
    *,
    max_minutes: float,
    dry_run: bool,
) -> dict[str, int]:
    deadline = time.monotonic() + max_minutes * 60
    client = get_ai_client()
    stats = {"processed": 0, "interpreted": 0, "no_data": 0, "errors": 0}

    async with get_session_factory()() as session:
        keys = [str(e) for e in universe]
        progress = await _progress_status(session, keys)
        pending = [
            e for e in universe
            if progress.get(str(e), {}).get("status") != "SUCCESS"
            and progress.get(str(e), {}).get("attempts", 0) < MAX_ATTEMPTS
        ]
        logger.info(
            "[%s] %d/%d entities pending (already SUCCESS today or NO_DATA excluded)",
            DATA_TYPE, len(pending), len(universe),
        )

        for entity_id in pending:
            if time.monotonic() > deadline:
                logger.info("[%s] time budget exhausted, stopping", DATA_TYPE)
                break
            stats["processed"] += 1
            try:
                result = await get_or_compute_entity_interpretation(session, client, entity_id)
                has_data = bool(result["metrics"])
                if dry_run:
                    await session.rollback()
                else:
                    await _record(session, entity_id, has_data=has_data)
                    await session.commit()
                if has_data:
                    stats["interpreted"] += 1
                else:
                    stats["no_data"] += 1
            except Exception as e:  # noqa: BLE001
                logger.warning("[%s] failed for entity %s: %s", DATA_TYPE, entity_id, e)
                await session.rollback()
                if not dry_run:
                    await _record(session, entity_id, has_data=False, error=f"{type(e).__name__}: {e}"[:400])
                    await session.commit()
                stats["errors"] += 1

    return stats


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Nightly Layer 1 Interpreter batch")
    p.add_argument("--status", action="store_true", help="Print coverage and exit")
    p.add_argument("--max-minutes", type=float, default=20.0, help="Wall-clock budget")
    p.add_argument("--dry-run", action="store_true", help="Compute but don't persist progress/interpretations")
    p.add_argument("--entity-ids", type=str, default=None, help="Comma-separated entity UUIDs (overrides watchlist universe)")
    p.add_argument("--all", action="store_true", help="Sweep every covered entity, not just the watchlist universe")
    p.add_argument("--limit", type=int, default=None, help="Cap the universe size (mainly for --all test runs)")
    return p.parse_args()


async def main() -> None:
    args = parse_args()
    async with get_session_factory()() as session:
        if args.entity_ids:
            universe = [uuid.UUID(s.strip()) for s in args.entity_ids.split(",") if s.strip()]
        elif args.all:
            universe = await _all_covered_entities(session)
        else:
            universe = await _watchlist_universe(session)
        if args.limit is not None:
            universe = universe[: args.limit]

        if args.status:
            await print_status(session, universe)
            return

    logger.info("[%s] universe size: %d", DATA_TYPE, len(universe))
    stats = await run_batch(universe, max_minutes=args.max_minutes, dry_run=args.dry_run)
    logger.info("[%s] batch complete: %s", DATA_TYPE, stats)


if __name__ == "__main__":
    asyncio.run(main())
