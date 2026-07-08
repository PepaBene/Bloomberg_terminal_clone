"""Ingest FOMC rate decisions derived from FRED target-range series (Pillar 1)."""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.database import get_session_factory
from src.ingestion.fomc_meetings import FomcMeetingsConnector

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Ingest FOMC rate decisions from FRED target-range series"
    )
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    parser.add_argument("--start-date", default="2000-01-01", help="FRED observation_start")
    return parser.parse_args()


async def main():
    args = parse_args()
    async with get_session_factory()() as session:
        logger.info("Starting FOMC (FRED) ingestion...")
        connector = FomcMeetingsConnector(start_date=args.start_date)
        stats = await connector.run(session, dry_run=args.dry_run)
        if not args.dry_run:
            await session.commit()
        logger.info(f"FOMC ingestion complete: {stats}")


if __name__ == "__main__":
    asyncio.run(main())
