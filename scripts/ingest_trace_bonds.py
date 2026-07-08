"""Ingest FINRA TRACE corporate bond trades into the bond master + pricing tables.

FLAG: The real FINRA TRACE feed requires registration + credentials. Supply the
credentialed endpoint via --endpoint-url / FINRA_TRACE_FEED_URL and the API key
via --api-key / FINRA_TRACE_API_KEY. Without a configured endpoint this no-ops.

Usage:
    python -m scripts.ingest_trace_bonds --endpoint-url https://... --api-key KEY
    python -m scripts.ingest_trace_bonds --dry-run
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.database import get_session_factory
from src.ingestion.finra_trace import FINRATraceConnector

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


async def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest FINRA TRACE bond trades")
    parser.add_argument("--endpoint-url", default=None)
    parser.add_argument("--api-key", default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    connector = FINRATraceConnector(
        endpoint_url=args.endpoint_url,
        api_key=args.api_key,
    )
    async with get_session_factory()() as session:
        logger.info("Ingesting FINRA TRACE bond trades...")
        stats = await connector.run(session, dry_run=args.dry_run, limit=args.limit)
        await session.commit()
        logger.info("TRACE bond ingestion complete: %s", stats)


if __name__ == "__main__":
    asyncio.run(main())
