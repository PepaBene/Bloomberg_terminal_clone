"""Ingest non-US global macro + composite country-risk scores from World Bank.

Source: World Bank Indicators API (keyless). Populates ``global_macro_indicators``
(non-US rows, source=WORLD_BANK), ``country_profiles`` (reference), and
``country_risk_scores`` (deterministic composite economic risk).

Usage:
    python -m scripts.ingest_country_risk
    python -m scripts.ingest_country_risk --countries US,CN,DE --start-year 2018
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.database import get_session_factory
from src.ingestion.worldbank_country_risk import WorldBankCountryRiskConnector

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


async def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest World Bank country risk + macro")
    parser.add_argument("--countries", type=str, default=None,
                        help="Comma-separated ISO2 codes (default: ~18 major economies)")
    parser.add_argument("--start-year", type=int, default=2015)
    parser.add_argument("--end-year", type=int, default=None)
    args = parser.parse_args()

    countries = args.countries.split(",") if args.countries else None
    connector = WorldBankCountryRiskConnector(
        countries=countries, start_year=args.start_year, end_year=args.end_year
    )
    async with get_session_factory()() as session:
        logger.info("Starting World Bank country-risk / macro ingestion...")
        stats = await connector.run(session)
        # BaseConnector.run only flushes — commit or the data is rolled back.
        await session.commit()
        logger.info("World Bank ingestion complete: %s", stats)


if __name__ == "__main__":
    asyncio.run(main())
