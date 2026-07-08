"""Ingest credit spread indices (BofA/ICE OAS) from FRED (Pillar 1 Supplement).

FRED OAS series are keyless-ish (a free FRED_API_KEY is required, same as the
macro ingestion). No CIK list is needed — the connector fetches a fixed set of
named FRED series.
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.database import get_session_factory
from src.ingestion.fred_credit_spreads import FREDCreditSpreadsConnector

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Ingest credit spread indices from FRED"
    )
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing to database")
    parser.add_argument("--start-date", default=None, help="Earliest observation date (YYYY-MM-DD)")
    parser.add_argument(
        "--no-percentiles",
        action="store_true",
        help="Skip computing historical spread percentiles",
    )
    return parser.parse_args()


async def main():
    args = parse_args()
    async with get_session_factory()() as session:
        logger.info("Starting FRED credit spread ingestion...")
        connector = FREDCreditSpreadsConnector(
            start_date=args.start_date,
            compute_percentiles=not args.no_percentiles,
        )
        if args.dry_run:
            logger.info("[DRY RUN] No data will be written to the database.")
        stats = await connector.run(session, dry_run=args.dry_run)
        if not args.dry_run:
            await session.commit()
        logger.info(f"Credit spread ingestion complete: {stats}")


if __name__ == "__main__":
    asyncio.run(main())
