"""Ingest forward consensus EPS estimates from Alpha Vantage (Domain 4).

Alpha Vantage's free tier is tight: 5 requests/minute, 25 requests/day. Each
configured ticker costs exactly one request. --limit therefore defaults to a
small number so a single run doesn't blow through the *daily* cap (the
connector's RateLimiter only enforces the per-minute cap; it has no notion of
a rolling daily budget, so keeping --limit conservative is on the caller).
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from src.database import get_session_factory
from src.ingestion.alphavantage_estimates import AlphaVantageEstimatesConnector
from src.models.security import SecurityIdentifier

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Ingest forward consensus EPS estimates from Alpha Vantage"
    )
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing to database")
    parser.add_argument(
        "--limit",
        type=int,
        default=25,
        help=(
            "Max number of tickers to fetch this run (default 25). Alpha "
            "Vantage's free tier allows only 25 requests/day TOTAL and this "
            "connector issues one request per ticker — do not raise this "
            "past your remaining daily quota."
        ),
    )
    return parser.parse_args()


async def _load_equity_tickers(session, limit: int | None) -> list[str]:
    """Fetch distinct equity ticker symbols to drive the connector, respecting --limit."""
    query = (
        select(SecurityIdentifier.identifier_value)
        .where(SecurityIdentifier.identifier_type == "TICKER")
        .distinct()
        .order_by(SecurityIdentifier.identifier_value)
    )
    if limit is not None:
        query = query.limit(limit)
    result = await session.execute(query)
    return [row[0] for row in result.all()]


async def main():
    args = parse_args()
    async with get_session_factory()() as session:
        logger.info("Starting Alpha Vantage consensus estimates ingestion...")
        tickers = await _load_equity_tickers(session, args.limit)
        logger.info(f"Loaded {len(tickers)} equity tickers from the database.")
        connector = AlphaVantageEstimatesConnector(tickers=tickers)
        if args.dry_run:
            logger.info("[DRY RUN] No data will be written to the database.")
        stats = await connector.run(session, dry_run=args.dry_run)
        if not args.dry_run:
            await session.commit()
        logger.info(f"Consensus estimates ingestion complete: {stats}")


if __name__ == "__main__":
    asyncio.run(main())
