"""Ingest corporate actions (dividends + splits) from Polygon.io (Domain 5).

Historically this script drove ``Edgar8KConnector``, but that connector's
``load()`` writes ``EightKEvent`` rows (a separate filing-intelligence model
with no ``security_id`` column at all) — it never populated the
``CorporateAction`` table that ``GET /securities/{id}/corporate-actions``
actually reads. 8-K filing-event ingestion still happens (``EightKEvent`` is
populated via ``scripts/backfill.py`` and ``src/services/freshness.py``, both
of which call ``Edgar8KConnector`` directly for filing-intelligence
purposes) — it just no longer runs through this script.

This script now drives ``PolygonCorporateActionsConnector``, which pulls
real structured dividend/split data (with genuine ex/record/pay dates) from
Polygon's reference endpoints, keyed off tickers already in our security
master.
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from src.database import get_session_factory
from src.ingestion.polygon_corporate_actions import PolygonCorporateActionsConnector
from src.models.security import SecurityIdentifier

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Ingest dividend/split corporate actions from Polygon.io"
    )
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing to database")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of tickers to process")
    return parser.parse_args()


async def _load_tickers(session, limit: int | None) -> list[str]:
    """Fetch distinct security tickers to drive the connector, respecting --limit."""
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
        logger.info("Starting Polygon corporate actions ingestion...")
        tickers = await _load_tickers(session, args.limit)
        logger.info(f"Loaded {len(tickers)} tickers from the security master.")
        connector = PolygonCorporateActionsConnector(tickers=tickers)
        if args.dry_run:
            logger.info("[DRY RUN] No data will be written to the database.")
        stats = await connector.run(session, dry_run=args.dry_run)
        if not args.dry_run:
            await session.commit()
        logger.info(f"Corporate actions ingestion complete: {stats}")


if __name__ == "__main__":
    asyncio.run(main())
