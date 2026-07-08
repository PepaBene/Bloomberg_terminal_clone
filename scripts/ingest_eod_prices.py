"""Ingest end-of-day price data from Polygon.io.

The Polygon "grouped daily" endpoint returns every US stock's EOD bar for a
single date, so one request == one trading day. This script fetches a short
history of recent weekdays (skipping weekends; market holidays simply come back
empty) so downstream analytics have a real price series to work with.
"""

import argparse
import asyncio
import logging
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.database import get_session_factory
from src.ingestion.polygon_eod import PolygonEODConnector

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ingest EOD price data from Polygon.io")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing to database")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of securities per date")
    parser.add_argument("--date", default=None, help="Fetch a single date (YYYY-MM-DD)")
    parser.add_argument("--days", type=int, default=5, help="Number of recent weekdays to fetch")
    return parser.parse_args()


def _recent_weekdays(n: int) -> list[str]:
    """Return the last ``n`` weekday dates (most recent first), ending yesterday."""
    out: list[str] = []
    d = date.today() - timedelta(days=1)
    while len(out) < n:
        if d.weekday() < 5:  # Mon-Fri
            out.append(d.isoformat())
        d -= timedelta(days=1)
    return out


async def main():
    args = parse_args()
    dates = [args.date] if args.date else _recent_weekdays(args.days)
    logger.info("Fetching EOD prices for %d date(s): %s", len(dates), dates)

    totals = {"inserted": 0, "updated": 0, "skipped": 0, "errors": 0}
    async with get_session_factory()() as session:
        for idx, d in enumerate(dates):
            connector = PolygonEODConnector(target_date=d)
            if args.dry_run:
                logger.info("[DRY RUN] %s", d)
            stats = await connector.run(session, dry_run=args.dry_run, limit=args.limit)
            if not args.dry_run:
                await session.commit()
            for k in totals:
                totals[k] += stats.get(k, 0)
            logger.info("  %s: %s", d, stats)
            # Respect the free-tier rate limit (5 req/min) between dates.
            if idx < len(dates) - 1:
                await asyncio.sleep(13)

    logger.info(f"EOD price ingestion complete: {totals}")


if __name__ == "__main__":
    asyncio.run(main())
