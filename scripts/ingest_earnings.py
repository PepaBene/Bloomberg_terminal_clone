"""Ingest earnings surprises (actual vs consensus EPS) from Finnhub.

Uses Finnhub's free-tier ``/stock/earnings`` feed to populate the
``earnings_surprises`` (entity-keyed) and ``estimate_surprises`` (security-keyed,
metric='EPS') read models with real reported-vs-consensus EPS surprises.

Ticker/entity/security resolution mirrors ``src/services/freshness.py``:
``security_identifiers`` (identifier_type='TICKER') joined to ``securities``.

Usage:
    python -m scripts.ingest_earnings --tickers AAPL,MSFT,NVDA   # targeted (test)
    python -m scripts.ingest_earnings --limit 50                 # first N ticker'd entities
    python -m scripts.ingest_earnings                            # all ticker'd entities

NOTE: forward-looking consensus estimates (`consensus_estimates`) and company
guidance (`company_guidance` / `guidance_tracking`) are NOT populated here —
Finnhub's free tier returns 403 for `/stock/price-target` and `/stock/eps-estimate`.
Those tables need a premium plan or another provider.
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text

from src.database import get_session_factory
from src.ingestion.finnhub_earnings import FinnhubEarningsConnector

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


async def _resolve_targets(session, tickers: list[str] | None, limit: int | None):
    """Return list of (ticker, security_id, entity_id) for ticker'd entities."""
    sql = (
        "SELECT si.identifier_value AS ticker, s.security_id, s.issuer_entity_id "
        "FROM securities s "
        "JOIN security_identifiers si ON si.security_id = s.security_id "
        "  AND si.identifier_type = 'TICKER' "
        "WHERE s.issuer_entity_id IS NOT NULL "
    )
    params: dict = {}
    if tickers:
        sql += "AND si.identifier_value = ANY(:tickers) "
        params["tickers"] = tickers
    sql += "ORDER BY si.identifier_value "
    if limit is not None:
        sql += "LIMIT :limit"
        params["limit"] = limit
    rows = (await session.execute(text(sql), params)).all()
    return [(r.ticker, r.security_id, r.issuer_entity_id) for r in rows]


async def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest earnings surprises from Finnhub")
    parser.add_argument("--tickers", type=str, default=None, help="Comma-separated tickers (e.g. AAPL,MSFT)")
    parser.add_argument("--limit", type=int, default=None, help="Cap number of ticker'd entities")
    args = parser.parse_args()

    tickers = [t.strip().upper() for t in args.tickers.split(",") if t.strip()] if args.tickers else None

    connector = FinnhubEarningsConnector()
    totals = {"surprises_inserted": 0, "surprises_updated": 0, "estimate_surprises": 0, "companies": 0}

    async with get_session_factory()() as session:
        targets = await _resolve_targets(session, tickers, args.limit)
        logger.info("Resolved %d ticker'd companies to ingest", len(targets))
        for ticker, security_id, entity_id in targets:
            try:
                stats = await connector.fetch_for_entity(session, entity_id, security_id, ticker)
                await session.commit()
                totals["companies"] += 1
                for k in ("surprises_inserted", "surprises_updated", "estimate_surprises"):
                    totals[k] += stats.get(k, 0)
            except Exception:
                await session.rollback()
                logger.exception("Failed to ingest earnings for %s", ticker)

    logger.info("Earnings ingestion complete: %s", totals)


if __name__ == "__main__":
    asyncio.run(main())
