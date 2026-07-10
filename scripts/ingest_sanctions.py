"""Ingest US OFAC SDN sanctions entries from the keyless CSV download.

Free, keyless source. Loads into the ``sanctions_entries`` table.

Usage:
    python -m scripts.ingest_sanctions                 # full SDN list
    python -m scripts.ingest_sanctions --max-entries 100
    python -m scripts.ingest_sanctions --limit 50
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.database import get_session_factory
from src.ingestion.sanctions_entries import SanctionsEntriesConnector

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


async def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest OFAC SDN sanctions")
    parser.add_argument("--max-entries", type=int, default=None,
                        help="Cap rows fetched from the SDN CSV")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    connector = SanctionsEntriesConnector(max_entries=args.max_entries)
    async with get_session_factory()() as session:
        logger.info("Ingesting OFAC SDN sanctions...")
        stats = await connector.run(session, limit=args.limit)
        await session.commit()
        logger.info("Sanctions ingestion complete: %s", stats)


if __name__ == "__main__":
    asyncio.run(main())
