"""Ingest primary-market corporate bond issuances into ``bond_issuances``.

Primary path: SEC EDGAR full-text search over 424B2/424B3/424B5/FWP filings
for a list of issuer CIKs loaded from the database (mirroring
``scripts/ingest_esg.py``'s CIK-loading pattern), with free-text regex
extraction of pricing terms from each matching filing. See
``src/ingestion/bond_issuances.py`` for the accuracy caveats — this has not
been validated against live EDGAR data.

Fallback path: a configurable JSON feed via --feed-url / BOND_ISSUANCES_FEED_URL
(a future paid new-issue monitor). If set, it takes priority over EDGAR and no
CIKs are needed. Issuers are resolved against existing entities; unresolved
deals are skipped (never fabricated).

Usage:
    python -m scripts.ingest_bond_issuances --days-back 180 --limit 50
    python -m scripts.ingest_bond_issuances --feed-url https://...
    python -m scripts.ingest_bond_issuances --dry-run
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from src.database import get_session_factory
from src.ingestion.bond_issuances import BondIssuancesConnector
from src.models.entity import EntityIdentifier

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ingest primary-market bond issuances")
    parser.add_argument("--feed-url", default=None, help="Configurable JSON feed override")
    parser.add_argument("--api-key", default=None)
    parser.add_argument(
        "--days-back", type=int, default=180,
        help="EDGAR full-text search lookback window in days (default: 180)",
    )
    parser.add_argument(
        "--cik-limit", type=int, default=None,
        help="Limit number of entity CIKs pulled from the DB to drive EDGAR search",
    )
    parser.add_argument("--limit", type=int, default=None, help="Limit number of records loaded")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


async def _load_ciks(session, limit: int | None) -> list[str]:
    """Fetch entity CIK numbers to drive the connector, respecting --cik-limit."""
    query = (
        select(EntityIdentifier.identifier_value)
        .where(EntityIdentifier.identifier_type == "CIK")
        .order_by(EntityIdentifier.identifier_value)
    )
    if limit is not None:
        query = query.limit(limit)
    result = await session.execute(query)
    return [row[0] for row in result.all()]


async def main() -> None:
    args = parse_args()
    async with get_session_factory()() as session:
        logger.info("Starting bond issuance ingestion...")

        ciks: list[str] = []
        if not args.feed_url:
            ciks = await _load_ciks(session, args.cik_limit)
            logger.info(f"Loaded {len(ciks)} entity CIKs from the database.")

        connector = BondIssuancesConnector(
            ciks=ciks,
            days_back=args.days_back,
            feed_url=args.feed_url,
            api_key=args.api_key,
        )
        if args.dry_run:
            logger.info("[DRY RUN] No data will be written to the database.")
        stats = await connector.run(session, dry_run=args.dry_run, limit=args.limit)
        if not args.dry_run:
            await session.commit()
        logger.info(f"Bond issuance ingestion complete: {stats}")


if __name__ == "__main__":
    asyncio.run(main())
