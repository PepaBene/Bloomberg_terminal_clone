"""Populate equity_details.shares_outstanding from ingested XBRL fundamentals.

The dedicated dei cover-page fetch (edgar_securities.py) left this null for every
row, but the XBRL fundamentals we already ingested carry basic/diluted shares on
each income statement. This fills equity_details.shares_outstanding from the most
recent period's shares (preferring basic, falling back to diluted) so market cap,
factor exposures, Merton inputs, and market-cap multiples work.

Idempotent: re-running just refreshes to the latest value.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text

from src.database import get_session_factory

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("compute_shares")

# For each equity_details row, take the newest period's shares for that security's
# issuer entity (basic preferred, else diluted), and write it onto equity_details.
UPDATE_SQL = text(
    """
    WITH latest AS (
        SELECT DISTINCT ON (s.security_id)
               s.security_id,
               COALESCE(i.basic_shares_outstanding, i.diluted_shares_outstanding) AS shares
        FROM securities s
        JOIN financial_periods fp ON fp.entity_id = s.issuer_entity_id
        JOIN income_statements i ON i.period_id = fp.period_id
        WHERE COALESCE(i.basic_shares_outstanding, i.diluted_shares_outstanding) IS NOT NULL
        ORDER BY s.security_id, fp.period_end_date DESC
    )
    UPDATE equity_details ed
    SET shares_outstanding = latest.shares
    FROM latest
    WHERE ed.security_id = latest.security_id
      AND latest.shares IS NOT NULL
    """
)


async def main() -> None:
    async with get_session_factory()() as session:
        result = await session.execute(UPDATE_SQL)
        await session.commit()
        count = await session.scalar(
            text("SELECT count(*) FROM equity_details WHERE shares_outstanding IS NOT NULL")
        )
        logger.info("Updated %s equity_details rows; %s now have shares_outstanding.",
                    result.rowcount, count)


if __name__ == "__main__":
    asyncio.run(main())
