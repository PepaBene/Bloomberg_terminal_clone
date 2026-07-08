"""Ingest ESG controversies from a configurable JSON feed (Pillar 1).

FLAG: No default feed ships with this connector. Pass --feed-url or set
ESG_CONTROVERSY_FEED_URL. Choosing/licensing a real ESG-controversy source is
an outstanding data-source decision (see the connector module docstring).
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.database import get_session_factory
from src.ingestion.edgar_esg_controversies import EsgControversiesConnector

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ingest ESG controversies")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    parser.add_argument("--feed-url", default=None, help="Controversy JSON feed URL")
    return parser.parse_args()


async def main():
    args = parse_args()
    async with get_session_factory()() as session:
        logger.info("Starting ESG controversies ingestion...")
        connector = EsgControversiesConnector(feed_url=args.feed_url)
        if not connector.feed_url:
            logger.warning("No feed URL configured — nothing to ingest (FLAG).")
        stats = await connector.run(session, dry_run=args.dry_run)
        if not args.dry_run:
            await session.commit()
        logger.info(f"ESG controversies ingestion complete: {stats}")


if __name__ == "__main__":
    asyncio.run(main())
