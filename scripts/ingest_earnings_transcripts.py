"""Ingest earnings call transcripts from Finnhub (Pillar 3 Phase 2).

HONEST SCOPE: verified live that Finnhub's /stock/transcripts endpoints
return 403 on the free-tier FINNHUB_API_KEY configured in .env -- this
connector is correctly wired end-to-end (schema, API routes at
/v3/earnings/{entity_id}/calls already existed before this script) but
will insert 0 rows until the key is upgraded to a paid Finnhub plan, or
another transcript source is added. It stops after the first 403 rather
than burning the whole entity list on a guaranteed-to-fail call.

Usage:
    python -m scripts.ingest_earnings_transcripts --limit 50
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text

from src.database import get_session_factory
from src.ingestion.finnhub_transcripts import FinnhubTranscriptsConnector

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

_TICKER_SUBQUERY = """
    SELECT s.issuer_entity_id AS entity_id, MIN(si.identifier_value) AS ticker
    FROM securities s
    JOIN security_identifiers si
      ON si.security_id = s.security_id AND si.identifier_type = 'TICKER'
    WHERE s.issuer_entity_id IS NOT NULL
    GROUP BY s.issuer_entity_id
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ingest earnings call transcripts from Finnhub")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=50, help="Max entities to attempt")
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    async with get_session_factory()() as session:
        rows = (
            await session.execute(text(f"SELECT entity_id, ticker FROM ({_TICKER_SUBQUERY}) t LIMIT :n"), {"n": args.limit})
        ).all()
        entity_ids = {ticker: entity_id for entity_id, ticker in rows}
        symbols = list(entity_ids.keys())
        logger.info(f"Loaded {len(symbols)} tickers to attempt.")

        connector = FinnhubTranscriptsConnector(symbols=symbols, entity_ids=entity_ids)
        stats = await connector.run(session, dry_run=args.dry_run)
        if not args.dry_run:
            await session.commit()
        logger.info(f"Earnings transcript ingestion complete: {stats}")


if __name__ == "__main__":
    asyncio.run(main())
