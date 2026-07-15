"""Ingest EIA commodity stock/inventory data (real supply/demand signal for R-023)."""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.database import get_session_factory
from src.ingestion.eia_commodity_inventory import EIACommodityInventoryConnector

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Ingest EIA weekly petroleum/natural-gas stock levels"
    )
    parser.add_argument("--api-key", default=None, help="Overrides EIA_API_KEY")
    parser.add_argument(
        "--lookback-periods", type=int, default=52,
        help="Number of most-recent weekly reports to fetch per series",
    )
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing to database")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of stock rows loaded")
    return parser.parse_args()


async def main():
    args = parse_args()
    connector = EIACommodityInventoryConnector(
        api_key=args.api_key, lookback_periods=args.lookback_periods
    )
    async with get_session_factory()() as session:
        logger.info("Starting EIA commodity inventory ingestion...")
        if args.dry_run:
            logger.info("[DRY RUN] No data will be written to the database.")
        stats = await connector.run(session, dry_run=args.dry_run, limit=args.limit)
        if not args.dry_run:
            await session.commit()
        logger.info(f"EIA commodity inventory ingestion complete: {stats}")


if __name__ == "__main__":
    asyncio.run(main())
