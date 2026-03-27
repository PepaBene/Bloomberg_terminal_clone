"""D11 FI Supplement: Treasury securities ingestion connector (TreasuryDirect API).

Stub implementation — will be wired to TreasuryDirect API for
auction results, outstanding amounts, and security details.
"""

import logging
from datetime import date

logger = logging.getLogger(__name__)


class TreasurySecuritiesConnector:
    """Ingest Treasury security reference data from TreasuryDirect API.

    API docs: https://api.fiscaldata.treasury.gov/services/api
    Endpoints used:
      - /v1/accounting/od/auctions — auction results
      - /v2/accounting/od/securities_outstanding — outstanding amounts
    """

    BASE_URL = "https://api.fiscaldata.treasury.gov/services/api/fiscal_service"

    def __init__(self, session=None):
        self.session = session

    async def fetch_auction_results(
        self,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[dict]:
        """Fetch auction results from TreasuryDirect (stub)."""
        logger.info("TreasurySecuritiesConnector.fetch_auction_results: stub — not implemented yet")
        return []

    async def fetch_outstanding_securities(self) -> list[dict]:
        """Fetch currently outstanding Treasury securities (stub)."""
        logger.info("TreasurySecuritiesConnector.fetch_outstanding_securities: stub — not implemented yet")
        return []

    async def sync_securities(self) -> int:
        """Sync Treasury securities into the database (stub)."""
        logger.info("TreasurySecuritiesConnector.sync_securities: stub — not implemented yet")
        return 0
