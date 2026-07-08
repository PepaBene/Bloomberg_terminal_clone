"""Ingest U.S. federal-agency / GSE bond reference data into ``agency_bonds``.

FLAG: No single clean keyless public feed exists for the full agency universe.
Supply a configurable JSON feed URL via --feed-url / AGENCY_BONDS_FEED_URL.
Without a configured feed this no-ops.

Usage:
    python -m scripts.ingest_agency_bonds --feed-url https://...
    python -m scripts.ingest_agency_bonds --dry-run
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.database import get_session_factory
from src.ingestion.agency_bonds import AgencyBondsConnector

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


async def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest agency/GSE bonds")
    parser.add_argument("--feed-url", default=None)
    parser.add_argument("--api-key", default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    connector = AgencyBondsConnector(feed_url=args.feed_url, api_key=args.api_key)
    async with get_session_factory()() as session:
        logger.info("Ingesting agency/GSE bonds...")
        stats = await connector.run(session, dry_run=args.dry_run, limit=args.limit)
        await session.commit()
        logger.info("Agency bond ingestion complete: %s", stats)


if __name__ == "__main__":
    asyncio.run(main())
