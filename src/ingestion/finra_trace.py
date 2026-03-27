"""D11 FI Supplement: FINRA TRACE bond trade ingestion connector.

Stub implementation — will be wired to FINRA TRACE dissemination
service for real-time and historical corporate bond trade data.
"""

import logging
from datetime import date

logger = logging.getLogger(__name__)


class FINRATraceConnector:
    """Ingest TRACE bond trade data from FINRA.

    TRACE (Trade Reporting and Compliance Engine) disseminates
    OTC corporate bond trade information. This connector handles:
      - Historical trade downloads (BTDS)
      - EOD price computation from trades
      - VWAP and liquidity scoring
    """

    def __init__(self, session=None):
        self.session = session

    async def fetch_trades(
        self,
        cusip: str | None = None,
        trade_date: date | None = None,
    ) -> list[dict]:
        """Fetch TRACE trades for a CUSIP on a given date (stub)."""
        logger.info("FINRATraceConnector.fetch_trades: stub — not implemented yet")
        return []

    async def compute_eod_prices(self, trade_date: date) -> int:
        """Compute EOD prices from TRACE trades for all bonds (stub)."""
        logger.info("FINRATraceConnector.compute_eod_prices: stub — not implemented yet")
        return 0

    async def sync_trades(self, start_date: date, end_date: date) -> int:
        """Sync TRACE trades for a date range into the database (stub)."""
        logger.info("FINRATraceConnector.sync_trades: stub — not implemented yet")
        return 0
