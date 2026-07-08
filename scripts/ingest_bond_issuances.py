"""Ingest primary-market corporate bond issuances into ``bond_issuances``.

FLAG: Primary-market new-issue data has no clean free public feed. Supply a
configurable JSON feed URL via --feed-url / BOND_ISSUANCES_FEED_URL. Without a
configured feed this no-ops. Issuers are resolved against existing entities;
unresolved deals are skipped (never fabricated).

Usage:
    python -m scripts.ingest_bond_issuances --feed-url https://...
    python -m scripts.ingest_bond_issuances --dry-run
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.database import get_session_factory
from src.ingestion.bond_issuances import BondIssuancesConnector

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


async def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest bond issuances")
    parser.add_argument("--feed-url", default=None)
    parser.add_argument("--api-key", default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    connector = BondIssuancesConnector(feed_url=args.feed_url, api_key=args.api_key)
    async with get_session_factory()() as session:
        logger.info("Ingesting bond issuances...")
        stats = await connector.run(session, dry_run=args.dry_run, limit=args.limit)
        await session.commit()
        logger.info("Bond issuance ingestion complete: %s", stats)


if __name__ == "__main__":
    asyncio.run(main())
