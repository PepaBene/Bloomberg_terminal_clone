"""Compute and persist per-security OwnershipSummary rollups (Spec 8.4).

Aggregates already-ingested InstitutionalHolding / InsiderHolding /
ShortInterest rows into the ``ownership_summaries`` table read by the E4
screening engine. Pure computation — no external API calls.

Usage:
    python -m scripts.compute_ownership_summary
    python -m scripts.compute_ownership_summary --limit 50
    python -m scripts.compute_ownership_summary --dry-run
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path
from uuid import UUID

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from src.database import get_session_factory
from src.engines.ownership_summary_engine import compute_for_security
from src.models.ownership import OwnershipSummary
from src.models.security import Security

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("compute_ownership_summary")


async def _upsert(session, values: dict) -> None:
    existing = await session.get(
        OwnershipSummary, (values["security_id"], values["report_date"])
    )
    if existing is None:
        session.add(OwnershipSummary(**values))
    else:
        for key, val in values.items():
            setattr(existing, key, val)


async def run(dry_run: bool = False, limit: int | None = None) -> None:
    factory = get_session_factory()
    async with factory() as session:
        query = select(Security.security_id).where(Security.status == "ACTIVE")
        if limit:
            query = query.limit(limit)
        security_ids: list[UUID] = [row[0] for row in (await session.execute(query)).all()]
        logger.info("Computing ownership summaries for %d securities", len(security_ids))

        if not security_ids:
            logger.warning("No active securities found — nothing to compute.")
            return

        computed = 0
        for security_id in security_ids:
            try:
                rollup = await compute_for_security(session, security_id)
                if rollup is None:
                    continue
                if not dry_run:
                    await _upsert(session, rollup.as_summary_values(security_id))
                    await session.commit()
                computed += 1
            except Exception:
                logger.exception("Failed to compute ownership for %s", security_id)
                if not dry_run:
                    await session.rollback()
                continue

        logger.info(
            "Ownership summary run complete: %d summaries %s",
            computed,
            "computed (dry-run, not persisted)" if dry_run else "persisted",
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Compute OwnershipSummary rollups")
    parser.add_argument("--dry-run", action="store_true", help="Compute but don't persist")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of securities")
    args = parser.parse_args()
    asyncio.run(run(dry_run=args.dry_run, limit=args.limit))


if __name__ == "__main__":
    main()
