"""Ingest DEF 14A proxy governance data from SEC EDGAR (Pillar 3).

Populates ``proxy_filings`` (reliable) plus best-effort
``executive_compensation`` / ``board_members`` / ``shareholder_proposals``.
CIK-driven, following the ``ingest_edgar_xbrl`` / ``ingest_executives`` pattern.
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from src.database import get_session_factory
from src.ingestion.edgar_proxy import EdgarProxyConnector
from src.models.entity import EntityIdentifier

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ingest EDGAR DEF 14A proxy governance data")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of CIKs")
    parser.add_argument(
        "--ciks", type=str, default=None,
        help="Comma-separated CIKs to ingest (overrides DB lookup; e.g. 320193,789019)",
    )
    parser.add_argument(
        "--max-filings-per-cik", type=int, default=5,
        help="Cap DEF 14A filings recorded per CIK (most recent first)",
    )
    parser.add_argument(
        "--max-body-parse-per-cik", type=int, default=2,
        help="Cap proxy HTML bodies downloaded per CIK for best-effort parsing",
    )
    parser.add_argument(
        "--no-bodies", action="store_true",
        help="Skip body downloads (proxy_filings only, no comp/board/proposals)",
    )
    return parser.parse_args()


async def _load_ciks(session, limit: int | None) -> list[str]:
    query = (
        select(EntityIdentifier.identifier_value)
        .where(EntityIdentifier.identifier_type == "CIK")
        .order_by(EntityIdentifier.identifier_value)
    )
    if limit is not None:
        query = query.limit(limit)
    result = await session.execute(query)
    return [row[0] for row in result.all()]


async def main():
    args = parse_args()
    async with get_session_factory()() as session:
        logger.info("Starting EDGAR DEF 14A proxy ingestion...")
        if args.ciks:
            ciks = [c.strip() for c in args.ciks.split(",") if c.strip()]
            logger.info(f"Using {len(ciks)} CIK(s) from --ciks.")
        else:
            ciks = await _load_ciks(session, args.limit)
            logger.info(f"Loaded {len(ciks)} entity CIKs from the database.")

        connector = EdgarProxyConnector(
            ciks=ciks,
            max_filings_per_cik=args.max_filings_per_cik,
            parse_bodies=not args.no_bodies,
            max_body_parse_per_cik=args.max_body_parse_per_cik,
        )
        stats = await connector.run(session, dry_run=args.dry_run)
        if not args.dry_run:
            await session.commit()
        logger.info(f"Proxy ingestion complete: {stats}")


if __name__ == "__main__":
    asyncio.run(main())
