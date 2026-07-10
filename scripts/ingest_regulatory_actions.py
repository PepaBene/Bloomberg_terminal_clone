"""Ingest recent US regulatory actions from the Federal Register API.

Free, keyless source. Loads into the ``regulatory_actions`` table.

Usage:
    python -m scripts.ingest_regulatory_actions
    python -m scripts.ingest_regulatory_actions --per-page 50 --limit 20
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.database import get_session_factory
from src.ingestion.regulatory_actions import RegulatoryActionsConnector

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


async def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest regulatory actions")
    parser.add_argument("--per-page", type=int, default=50)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    connector = RegulatoryActionsConnector(per_page=args.per_page)
    async with get_session_factory()() as session:
        logger.info("Ingesting regulatory actions...")
        stats = await connector.run(session, limit=args.limit)
        await session.commit()
        logger.info("Regulatory actions ingestion complete: %s", stats)


if __name__ == "__main__":
    asyncio.run(main())
