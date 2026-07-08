"""Compute + persist debt maturity profiles from ingested debt tranches.

Reads ``debt_tranches`` (populated by the capital-structure ingestion
workstream), buckets each entity's debt by maturity year, and writes
``debt_maturity_profiles`` + ``maturity_buckets``. Pure computation — no
external data source required.

Usage:
    python -m scripts.compute_debt_maturity
    python -m scripts.compute_debt_maturity --as-of 2026-01-01
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.database import get_session_factory
from src.engines.debt_maturity_engine import compute_and_persist_profiles

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compute debt maturity profiles")
    parser.add_argument("--as-of", type=str, default=None, help="As-of date (YYYY-MM-DD)")
    parser.add_argument("--dry-run", action="store_true", help="Compute but do not commit")
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    as_of = date.fromisoformat(args.as_of) if args.as_of else None

    async with get_session_factory()() as session:
        logger.info("Computing debt maturity profiles (as_of=%s)...", as_of or date.today())
        counts = await compute_and_persist_profiles(session, as_of_date=as_of)
        if args.dry_run:
            await session.rollback()
            logger.info("[DRY RUN] rolled back — would have written: %s", counts)
        else:
            await session.commit()
            logger.info("Debt maturity computation complete: %s", counts)


if __name__ == "__main__":
    asyncio.run(main())
