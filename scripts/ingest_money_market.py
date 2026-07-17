"""Ingest money market rates from FRED (SOFR, effective fed funds, T-bills, etc.).

No CIK/ticker list needed — FredMoneyMarketConnector pulls a fixed set of
FRED series (see ``FRED_SERIES_MAP``) directly into ``money_market_rates``,
which backs ``GET /v1/macro/money-markets``.
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.database import get_session_factory
from src.ingestion.fred_money_market import FredMoneyMarketConnector

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ingest money market rates from FRED")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    parser.add_argument("--start-date", default=None, help="FRED observation_start (YYYY-MM-DD)")
    return parser.parse_args()


async def main():
    args = parse_args()
    async with get_session_factory()() as session:
        logger.info("Starting FRED money market ingestion...")
        connector = FredMoneyMarketConnector(start_date=args.start_date)
        if args.dry_run:
            logger.info("[DRY RUN] No data will be written to the database.")
        stats = await connector.run(session, dry_run=args.dry_run)
        if not args.dry_run:
            await session.commit()
        logger.info(f"Money market ingestion complete: {stats}")


if __name__ == "__main__":
    asyncio.run(main())
