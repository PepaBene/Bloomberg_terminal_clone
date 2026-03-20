"""Ingest company fundamentals from SEC EDGAR XBRL filings (Domain 3)."""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.database import get_session_factory
from src.ingestion.edgar_xbrl import EdgarXBRLConnector

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ingest EDGAR XBRL fundamentals data")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing to database")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of filings to process")
    return parser.parse_args()


async def main():
    args = parse_args()
    connector = EdgarXBRLConnector()
    async with get_session_factory()() as session:
        logger.info("Starting EDGAR XBRL fundamentals ingestion...")
        if args.dry_run:
            logger.info("[DRY RUN] No data will be written to the database.")
        stats = await connector.run(session, dry_run=args.dry_run, limit=args.limit)
        if not args.dry_run:
            await session.commit()
        logger.info(f"EDGAR XBRL ingestion complete: {stats}")


if __name__ == "__main__":
    asyncio.run(main())
