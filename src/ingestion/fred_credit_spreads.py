"""D11 FI Supplement: FRED credit spread indices ingestion connector.

Stub implementation — will be wired to FRED API for BofA/ICE
credit spread index data (OAS for IG, HY, and rating sub-indices).
"""

import logging
from datetime import date

logger = logging.getLogger(__name__)

# BofA ICE indices available via FRED
FRED_SPREAD_SERIES = {
    "BAMLC0A0CM": "ICE BofA US Corporate Master OAS",
    "BAMLC0A1CAAA": "ICE BofA US Corporate AAA OAS",
    "BAMLC0A2CAA": "ICE BofA US Corporate AA OAS",
    "BAMLC0A3CA": "ICE BofA US Corporate A OAS",
    "BAMLC0A4CBBB": "ICE BofA US Corporate BBB OAS",
    "BAMLH0A0HYM2": "ICE BofA US High Yield Master OAS",
    "BAMLH0A1HYBB": "ICE BofA US High Yield BB OAS",
    "BAMLH0A2HYB": "ICE BofA US High Yield B OAS",
    "BAMLH0A3HYC": "ICE BofA US High Yield CCC & Lower OAS",
    "BAMLC0A0CMEY": "ICE BofA US Corporate Effective Yield",
    "BAMLH0A0HYM2EY": "ICE BofA US High Yield Effective Yield",
}


class FREDCreditSpreadsConnector:
    """Ingest credit spread indices from FRED.

    Uses the existing FRED API key and httpx session from
    FredMacroConnector infrastructure.
    """

    FRED_BASE = "https://api.stlouisfed.org/fred/series/observations"

    def __init__(self, api_key: str | None = None, session=None):
        self.api_key = api_key
        self.session = session

    async def fetch_series(
        self,
        series_id: str,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[dict]:
        """Fetch a single FRED spread series (stub)."""
        logger.info(
            "FREDCreditSpreadsConnector.fetch_series(%s): stub — not implemented yet",
            series_id,
        )
        return []

    async def sync_all_spreads(
        self,
        start_date: date | None = None,
    ) -> int:
        """Sync all 11 spread series from FRED (stub)."""
        logger.info("FREDCreditSpreadsConnector.sync_all_spreads: stub — not implemented yet")
        return 0
