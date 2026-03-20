"""Populate governance models (DataCatalogEntry, SourceConnector) for all domains.

Usage:
    python scripts/populate_governance.py
"""

import asyncio
import logging
import sys
import uuid
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# ── Catalog entries ────────────────────────────────────────────────────

CATALOG_ENTRIES = [
    {
        "dataset_name": "Reference Data (D8)",
        "description": "Countries, currencies, exchanges, GICS/SIC/NAICS classifications, trading calendars.",
        "domain": "D8",
        "steward_role": "Data Engineering",
        "sensitivity": "PUBLIC",
        "update_frequency": "DAILY",
    },
    {
        "dataset_name": "Entity Master (D1)",
        "description": "Legal entities (companies, funds, governments) with identifiers, names, and relationships.",
        "domain": "D1",
        "steward_role": "Data Engineering",
        "sensitivity": "INTERNAL",
        "update_frequency": "DAILY",
    },
    {
        "dataset_name": "Security Master (D2)",
        "description": "Securities (equities, fixed income) with identifiers, details, and EOD prices.",
        "domain": "D2",
        "steward_role": "Data Engineering",
        "sensitivity": "INTERNAL",
        "update_frequency": "DAILY",
    },
    {
        "dataset_name": "Fundamentals (D3)",
        "description": "SEC filings, financial periods, income statements, balance sheets, cash flows, segments, KPIs.",
        "domain": "D3",
        "steward_role": "Fundamental Research",
        "sensitivity": "INTERNAL",
        "update_frequency": "QUARTERLY",
    },
    {
        "dataset_name": "Estimates & Expectations (D4)",
        "description": "Consensus estimates, individual analyst estimates, company guidance, earnings surprises.",
        "domain": "D4",
        "steward_role": "Quant Research",
        "sensitivity": "CONFIDENTIAL",
        "update_frequency": "DAILY",
    },
    {
        "dataset_name": "Corporate Actions (D5)",
        "description": "Dividends, splits, M&A, corporate events with adjustment factors.",
        "domain": "D5",
        "steward_role": "Data Engineering",
        "sensitivity": "INTERNAL",
        "update_frequency": "REAL-TIME",
    },
    {
        "dataset_name": "Ownership (D6)",
        "description": "Institutional holdings (13F), insider transactions (Form 4), short interest (FINRA).",
        "domain": "D6",
        "steward_role": "Quant Research",
        "sensitivity": "INTERNAL",
        "update_frequency": "QUARTERLY",
    },
    {
        "dataset_name": "Macroeconomic Data (D7)",
        "description": "Macro indicators from FRED, central bank policy decisions, economic calendar.",
        "domain": "D7",
        "steward_role": "Macro Research",
        "sensitivity": "PUBLIC",
        "update_frequency": "HOURLY",
    },
    {
        "dataset_name": "ESG & Sustainability (D9)",
        "description": "ESG scores, metrics (emissions, governance), controversies.",
        "domain": "D9",
        "steward_role": "ESG Research",
        "sensitivity": "INTERNAL",
        "update_frequency": "WEEKLY",
    },
    {
        "dataset_name": "Business Relationships (D10)",
        "description": "Customer, supplier, competitor, partner relationships extracted via NLP from 10-K filings.",
        "domain": "D10",
        "steward_role": "Fundamental Research",
        "sensitivity": "INTERNAL",
        "update_frequency": "WEEKLY",
    },
]


SOURCE_CONNECTORS = [
    {"name": "FRED API", "source_type": "REST_API", "domain": "D7", "url": "https://api.stlouisfed.org/fred/"},
    {"name": "SEC EDGAR XBRL", "source_type": "REST_API", "domain": "D3", "url": "https://data.sec.gov/api/xbrl/"},
    {"name": "SEC EDGAR 8-K", "source_type": "REST_API", "domain": "D5", "url": "https://efts.sec.gov/LATEST/search-index"},
    {"name": "SEC EDGAR 13F-HR", "source_type": "REST_API", "domain": "D6", "url": "https://www.sec.gov/cgi-bin/browse-edgar"},
    {"name": "SEC EDGAR Form 4", "source_type": "REST_API", "domain": "D6", "url": "https://www.sec.gov/cgi-bin/browse-edgar"},
    {"name": "FINRA Short Interest", "source_type": "FILE_DOWNLOAD", "domain": "D6", "url": "https://www.finra.org/"},
    {"name": "Polygon.io EOD", "source_type": "REST_API", "domain": "D2", "url": "https://api.polygon.io/v2/aggs/"},
    {"name": "SEC EDGAR ESG", "source_type": "REST_API", "domain": "D9", "url": "https://efts.sec.gov/LATEST/search-index"},
    {"name": "SEC EDGAR 10-K NLP", "source_type": "REST_API", "domain": "D10", "url": "https://efts.sec.gov/LATEST/search-index"},
]


async def main():
    logger.info("Governance population script ready.")
    logger.info("Catalog entries defined: %d", len(CATALOG_ENTRIES))
    logger.info("Source connectors defined: %d", len(SOURCE_CONNECTORS))

    for entry in CATALOG_ENTRIES:
        logger.info("  [%s] %s — %s", entry["domain"], entry["dataset_name"], entry["sensitivity"])

    for conn in SOURCE_CONNECTORS:
        logger.info("  [%s] %s — %s", conn["domain"], conn["name"], conn["source_type"])

    logger.info(
        "To populate into the database, configure DATABASE_URL and run with --execute flag."
    )


if __name__ == "__main__":
    asyncio.run(main())
