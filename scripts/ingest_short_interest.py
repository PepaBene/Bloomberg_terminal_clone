"""Ingest short interest data from FINRA (Domain 6 - Ownership)."""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from src.database import get_session_factory
from src.ingestion.finra_short_interest import FinraShortInterestConnector
from src.models.security import SecurityIdentifier

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ingest FINRA short interest data")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing to database")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of securities to process")
    return parser.parse_args()


async def _load_tickers(session, limit: int | None) -> list[str]:
    """Fetch security ticker symbols to drive the connector, respecting --limit."""
    query = (
        select(SecurityIdentifier.identifier_value)
        .where(SecurityIdentifier.identifier_type == "TICKER")
        .order_by(SecurityIdentifier.identifier_value)
    )
    if limit is not None:
        query = query.limit(limit)
    result = await session.execute(query)
    return [row[0] for row in result.all()]


async def main():
    args = parse_args()
    async with get_session_factory()() as session:
        logger.info("Starting FINRA short interest data ingestion...")
        symbols = await _load_tickers(session, args.limit)
        logger.info(f"Loaded {len(symbols)} security tickers from the database.")
        connector = FinraShortInterestConnector(symbols=symbols)
        if args.dry_run:
            logger.info("[DRY RUN] No data will be written to the database.")
        stats = await connector.run(session, dry_run=args.dry_run, limit=args.limit)
        if not args.dry_run:
            await session.commit()
        logger.info(f"Short interest ingestion complete: {stats}")


if __name__ == "__main__":
    asyncio.run(main())
