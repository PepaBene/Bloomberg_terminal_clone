"""Ingest recent US congressional bills from the GovInfo bills RSS feed.

Free, keyless source. Loads into the ``legislative_bills`` table.

Usage:
    python -m scripts.ingest_legislative_bills
    python -m scripts.ingest_legislative_bills --limit 20
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.database import get_session_factory
from src.ingestion.legislative_bills import LegislativeBillsConnector

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


async def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest legislative bills")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    connector = LegislativeBillsConnector()
    async with get_session_factory()() as session:
        logger.info("Ingesting legislative bills...")
        stats = await connector.run(session, limit=args.limit)
        await session.commit()
        logger.info("Legislative bills ingestion complete: %s", stats)


if __name__ == "__main__":
    asyncio.run(main())
