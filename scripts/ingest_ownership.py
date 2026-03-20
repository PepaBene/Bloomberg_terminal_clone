"""Ingest ownership data from SEC EDGAR 13F and Form 4 filings (Domain 6)."""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.database import get_session_factory
from src.ingestion.edgar_13f import Edgar13FConnector
from src.ingestion.edgar_form4 import EdgarForm4Connector

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ingest ownership data from EDGAR 13F and Form 4")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing to database")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of filings to process")
    parser.add_argument("--skip-13f", action="store_true", help="Skip 13F institutional holdings")
    parser.add_argument("--skip-form4", action="store_true", help="Skip Form 4 insider transactions")
    return parser.parse_args()


async def main():
    args = parse_args()
    async with get_session_factory()() as session:
        if not args.skip_13f:
            logger.info("Starting EDGAR 13F institutional ownership ingestion...")
            if args.dry_run:
                logger.info("[DRY RUN] No data will be written to the database.")
            connector_13f = Edgar13FConnector()
            stats_13f = await connector_13f.run(session, dry_run=args.dry_run, limit=args.limit)
            if not args.dry_run:
                await session.commit()
            logger.info(f"13F ingestion complete: {stats_13f}")

        if not args.skip_form4:
            logger.info("Starting EDGAR Form 4 insider transaction ingestion...")
            if args.dry_run:
                logger.info("[DRY RUN] No data will be written to the database.")
            connector_form4 = EdgarForm4Connector()
            stats_form4 = await connector_form4.run(session, dry_run=args.dry_run, limit=args.limit)
            if not args.dry_run:
                await session.commit()
            logger.info(f"Form 4 ingestion complete: {stats_form4}")


if __name__ == "__main__":
    asyncio.run(main())
