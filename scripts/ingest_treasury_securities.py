"""Ingest U.S. Treasury marketable securities (Fiscal Data API, keyless).

Pulls per-CUSIP Treasury reference + auction data from the free U.S. Treasury
Fiscal Data ``auctions_query`` dataset into the ``treasury_securities`` table.

Usage:
    python -m scripts.ingest_treasury_securities
    python -m scripts.ingest_treasury_securities --start-date 2024-01-01
    python -m scripts.ingest_treasury_securities --max-pages 2 --dry-run
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.database import get_session_factory
from src.ingestion.treasury_securities import TreasurySecuritiesConnector

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


async def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest Treasury securities (Fiscal Data)")
    parser.add_argument("--start-date", default=None, help="ISO auction_date lower bound")
    parser.add_argument("--page-size", type=int, default=1000)
    parser.add_argument("--max-pages", type=int, default=5)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    connector = TreasurySecuritiesConnector(
        page_size=args.page_size,
        max_pages=args.max_pages,
        start_date=args.start_date,
    )
    async with get_session_factory()() as session:
        logger.info("Ingesting Treasury securities...")
        stats = await connector.run(session, dry_run=args.dry_run, limit=args.limit)
        await session.commit()
        logger.info("Treasury securities ingestion complete: %s", stats)


if __name__ == "__main__":
    asyncio.run(main())
