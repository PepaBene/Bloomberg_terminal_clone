"""Ingest FINRA TRACE corporate bond trades from a local Academic/Historical
TRACE bulk dissemination file (Fixed Income Domain 11).

Live-feed credentials are not available in most environments — FINRA TRACE
(Academic/BTDS) is registration-gated. This driver ingests a bulk extract a
human has already downloaded after registering via FINRA's Academic/BTDS
TRACE program (e.g. through WRDS or direct FINRA registration), rather than
calling a live API.
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import settings
from src.database import get_session_factory
from src.ingestion.finra_trace import FINRATraceConnector

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Ingest FINRA TRACE corporate bond trades from a local "
        "Academic/Historical TRACE bulk file"
    )
    parser.add_argument(
        "--file",
        type=str,
        default=None,
        help="Path to a local Academic/Historical TRACE bulk dissemination file "
        "(pipe/comma/tab-delimited). Falls back to settings.FINRA_TRACE_LOCAL_FILE.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing to database")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of trade rows processed")
    return parser.parse_args()


async def main():
    args = parse_args()
    local_file = args.file or settings.FINRA_TRACE_LOCAL_FILE
    if not local_file:
        logger.error(
            "No --file given and settings.FINRA_TRACE_LOCAL_FILE is unset — nothing to ingest. "
            "Obtain a bulk extract via FINRA's Academic/BTDS TRACE registration first."
        )
        return

    async with get_session_factory()() as session:
        logger.info("Starting FINRA TRACE ingestion from local file: %s", local_file)
        connector = FINRATraceConnector(local_file=local_file)
        if args.dry_run:
            logger.info("[DRY RUN] No data will be written to the database.")
        stats = await connector.run(session, dry_run=args.dry_run, limit=args.limit)
        if not args.dry_run:
            await session.commit()
        logger.info("FINRA TRACE ingestion complete: %s", stats)


if __name__ == "__main__":
    asyncio.run(main())
