"""Ingest U.S. federal-agency / GSE bond reference data into ``agency_bonds``.

Primary path: FHLB Office of Finance's free, keyless consolidated-obligation
debt-issuance download (--fhlb-url / FHLB_OF_DATA_URL), parsed as CSV or
JSON. See src/ingestion/agency_bonds.py for the column-mapping caveats — the
live URL and column names must be confirmed against the real file before
this is trusted for production use.

Fallback path: a configurable JSON feed (--feed-url / AGENCY_BONDS_FEED_URL)
for a future consolidated paid feed covering the full agency universe. If
set, it takes priority over the FHLB path.

Agency bonds are not CIK-scoped (unlike issuer-driven connectors such as
ingest_esg.py) — the connector is instantiated directly with no entity list.

Usage:
    python -m scripts.ingest_agency_bonds
    python -m scripts.ingest_agency_bonds --fhlb-url https://...
    python -m scripts.ingest_agency_bonds --feed-url https://...
    python -m scripts.ingest_agency_bonds --dry-run
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.database import get_session_factory
from src.ingestion.agency_bonds import AgencyBondsConnector

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


async def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest agency/GSE bonds")
    parser.add_argument("--fhlb-url", default=None, help="FHLB Office of Finance data URL override")
    parser.add_argument("--feed-url", default=None, help="Configurable JSON feed override")
    parser.add_argument("--api-key", default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    connector = AgencyBondsConnector(
        feed_url=args.feed_url, api_key=args.api_key, fhlb_url=args.fhlb_url
    )
    async with get_session_factory()() as session:
        logger.info("Ingesting agency/GSE bonds...")
        stats = await connector.run(session, dry_run=args.dry_run, limit=args.limit)
        await session.commit()
        logger.info("Agency bond ingestion complete: %s", stats)


if __name__ == "__main__":
    asyncio.run(main())
