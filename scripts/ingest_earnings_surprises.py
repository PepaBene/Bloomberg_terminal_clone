"""Ingest earnings surprises (actual vs consensus).

FLAG: This driver is a documented skeleton. It reads consensus EPS from the
``consensus_estimates`` table, but there is currently no ingested source for
*actual* EPS/revenue (would come from XBRL fundamentals) and no free
consensus-estimate feed. Until both sources are wired, this driver assembles no
actual/consensus pairs and the connector writes nothing. See the module
docstring of ``src/ingestion/earnings_surprises_ingest.py``.
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.database import get_session_factory
from src.ingestion.earnings_surprises_ingest import EarningsSurprisesConnector

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ingest earnings surprises")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    return parser.parse_args()


async def _assemble_pairs(session) -> list[dict]:
    """Assemble actual+consensus pairs.

    FLAG: not yet wired — needs an actual-EPS source (XBRL) and a
    consensus-estimate ingestion source. Returns [] until those exist.
    """
    logger.warning(
        "Earnings-surprise actuals/consensus pairing is not wired "
        "(needs actual-EPS XBRL source + consensus-estimate feed). "
        "No records will be produced."
    )
    return []


async def main():
    args = parse_args()
    async with get_session_factory()() as session:
        logger.info("Starting earnings-surprise ingestion...")
        pairs = await _assemble_pairs(session)
        connector = EarningsSurprisesConnector(records=pairs)
        stats = await connector.run(session, dry_run=args.dry_run)
        if not args.dry_run:
            await session.commit()
        logger.info(f"Earnings-surprise ingestion complete: {stats}")


if __name__ == "__main__":
    asyncio.run(main())
