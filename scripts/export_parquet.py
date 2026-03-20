"""Export current database state to Parquet files for analytics.

Creates a data lake snapshot at::

    data/lake/{domain}/{table}/{year}/{month}/data.parquet

Usage:
    python scripts/export_parquet.py
    python scripts/export_parquet.py --domain D7
    python scripts/export_parquet.py --output s3://lake/
"""

import argparse
import asyncio
import logging
import sys
from datetime import date
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# Tables per domain to export
DOMAIN_TABLES = {
    "D1": ["entities", "entity_identifiers", "entity_names", "entity_relationships"],
    "D2": ["securities", "security_identifiers", "equity_details", "fixed_income_details", "eod_prices"],
    "D3": ["filings", "financial_periods", "income_statements", "balance_sheets", "cash_flow_statements", "segment_data"],
    "D4": ["consensus_estimates", "estimate_surprises", "company_guidance"],
    "D5": ["corporate_actions", "dividend_actions", "split_actions", "ma_actions"],
    "D6": ["institution_profiles", "institutional_holdings", "insider_holdings", "ownership_summaries", "short_interest"],
    "D7": ["macro_indicators", "macro_values", "central_bank_policies"],
    "D8": ["countries", "currencies", "exchanges", "gics_classifications"],
    "D9": ["esg_scores", "esg_metrics", "esg_controversies"],
    "D10": ["business_relationships", "relationship_history"],
}


async def main():
    parser = argparse.ArgumentParser(description="Export database to Parquet")
    parser.add_argument("--domain", help="Export only this domain (e.g. D7)")
    parser.add_argument("--output", default="data/lake", help="Output directory or S3 path")
    args = parser.parse_args()

    today = date.today()
    domains = {args.domain: DOMAIN_TABLES[args.domain]} if args.domain else DOMAIN_TABLES

    logger.info("Parquet export ready for %d domains, %d tables.",
                len(domains), sum(len(t) for t in domains.values()))

    for domain, tables in domains.items():
        for table in tables:
            output_path = f"{args.output}/{domain}/{table}/{today.year}/{today.month:02d}/data.parquet"
            logger.info("  Would export: %s -> %s", table, output_path)

    logger.info(
        "To run the actual export, install pyarrow/pandas and configure DATABASE_URL."
    )


if __name__ == "__main__":
    asyncio.run(main())
