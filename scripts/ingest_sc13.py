"""Ingest SEC EDGAR Schedule 13D / 13G beneficial-ownership filings (Domain 6).

Drives Edgar13D13GConnector over a keyless daily-index sweep -- unlike
ingest_ownership.py / ingest_form4.py this does NOT source a CIK list from
entity_identifiers first: the reporting person on a 13D/13G is frequently
not a pre-existing covered entity, so the connector discovers filings by
form type + date range instead. See src/ingestion/edgar_13d13g.py's module
docstring for the full "FLAG — UNTESTED AGAINST LIVE DATA" caveats.
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.database import get_session_factory
from src.ingestion.edgar_13d13g import (
    ALL_SCHEDULE_13_FORMS,
    SCHEDULE_13D_FORMS,
    SCHEDULE_13G_FORMS,
    Edgar13D13GConnector,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Ingest SEC EDGAR Schedule 13D/13G beneficial ownership filings"
    )
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing to database")
    parser.add_argument("--days-back", type=int, default=10, help="Days of daily-index history to sweep")
    parser.add_argument("--limit", type=int, default=None, help="Max filings to process")
    parser.add_argument(
        "--schedule", choices=["13d", "13g", "both"], default="both",
        help="Restrict to only 13D (activist) or only 13G (passive) filings",
    )
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    forms = {
        "13d": SCHEDULE_13D_FORMS,
        "13g": SCHEDULE_13G_FORMS,
        "both": ALL_SCHEDULE_13_FORMS,
    }[args.schedule]

    async with get_session_factory()() as session:
        connector = Edgar13D13GConnector(
            days_back=args.days_back, forms=forms, max_filings=args.limit,
        )
        stats = await connector.run(session, dry_run=args.dry_run, limit=None)
        if not args.dry_run:
            await session.commit()
        logger.info(f"Schedule 13D/13G ingestion complete: {stats}")


if __name__ == "__main__":
    asyncio.run(main())
