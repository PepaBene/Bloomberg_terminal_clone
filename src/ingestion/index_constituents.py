"""Index constituent ingestion: S&P 500 (Finnhub) + Russell 1000 (Wikipedia)."""

import logging
import re
from datetime import date

import httpx
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.ingestion.base import BaseConnector
from src.ingestion.rate_limiter import RateLimiter
from src.models.screening import SavedScreen
from src.models.security import Security

logger = logging.getLogger(__name__)


class IndexConstituentConnector(BaseConnector):
    """Fetches index membership and seeds universe tables."""

    name = "Index Constituents"
    connector_type = "BATCH_API"
    data_domain = "UNIVERSE"

    def __init__(self):
        self.rate_limiter = RateLimiter(max_requests=1, per_seconds=1.0)

    # ── S&P 500 via Finnhub ────────────────────────────────────────

    async def _fetch_sp500_finnhub(self) -> list[str]:
        """Fetch S&P 500 constituent tickers from Finnhub API."""
        if not settings.FINNHUB_API_KEY:
            logger.warning("FINNHUB_API_KEY not set; skipping S&P 500 fetch")
            return []

        url = "https://finnhub.io/api/v1/index/constituents"
        params = {"symbol": "^GSPC", "token": settings.FINNHUB_API_KEY}

        async with httpx.AsyncClient(timeout=30) as client:
            await self.rate_limiter.acquire()
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()

        tickers = data.get("constituents", [])
        logger.info("Finnhub returned %d S&P 500 constituents", len(tickers))
        return tickers

    # ── Russell 1000 via Wikipedia ─────────────────────────────────

    async def _fetch_russell1000_wikipedia(self) -> list[str]:
        """Scrape Russell 1000 constituent tickers from Wikipedia."""
        url = "https://en.wikipedia.org/wiki/Russell_1000_Index"

        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            html = resp.text

        # Wikipedia tables have ticker symbols in cells.
        # Extract tickers from the constituent table.
        # The table rows contain ticker symbols typically in <td> elements.
        tickers: list[str] = []

        # Find all tables, then look for the one with stock tickers
        # Wikipedia Russell 1000 page has ticker symbols in table cells
        # Pattern: look for NYSE/NASDAQ style ticker symbols in table data
        table_pattern = re.compile(
            r'<table[^>]*class="[^"]*wikitable[^"]*sortable[^"]*"[^>]*>(.*?)</table>',
            re.DOTALL,
        )
        tables = table_pattern.findall(html)

        for table_html in tables:
            # Check if this looks like a constituents table (has "Ticker" header)
            if "Ticker" not in table_html and "ticker" not in table_html.lower():
                continue

            # Extract ticker from each row
            row_pattern = re.compile(r"<tr>(.*?)</tr>", re.DOTALL)
            rows = row_pattern.findall(table_html)

            for row in rows:
                cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.DOTALL)
                if len(cells) >= 2:
                    # Ticker is typically in the second column
                    # Strip HTML tags to get clean text
                    ticker_cell = re.sub(r"<[^>]+>", "", cells[1]).strip()
                    # Valid ticker: 1-5 uppercase letters, optionally with dots
                    if re.match(r"^[A-Z]{1,5}(\.[A-Z])?$", ticker_cell):
                        tickers.append(ticker_cell)

        logger.info("Wikipedia returned %d Russell 1000 constituents", len(tickers))
        return tickers

    # ── Resolve tickers to security IDs ────────────────────────────

    async def _resolve_tickers(
        self, session: AsyncSession, tickers: list[str]
    ) -> list[str]:
        """Map ticker symbols to security_id UUIDs in our database."""
        if not tickers:
            return []

        result = await session.execute(
            select(Security.security_id, Security.ticker_symbol).where(
                Security.ticker_symbol.in_(tickers),
                Security.status == "ACTIVE",
            )
        )
        rows = result.all()
        resolved = [str(r.security_id) for r in rows]
        unresolved = set(tickers) - {r.ticker_symbol for r in rows}
        if unresolved:
            logger.warning(
                "%d tickers not found in DB: %s",
                len(unresolved),
                sorted(unresolved)[:20],
            )
        return resolved

    # ── Seed universe ──────────────────────────────────────────────

    async def _seed_universe(
        self,
        session: AsyncSession,
        name: str,
        security_ids: list[str],
    ) -> None:
        """Create or update a SavedScreen universe record."""
        existing = await session.execute(
            select(SavedScreen).where(
                SavedScreen.screen_type == "UNIVERSE",
                SavedScreen.name == name,
            )
        )
        screen = existing.scalar_one_or_none()

        definition = {"security_ids": security_ids, "source_date": str(date.today())}

        if screen:
            screen.definition = definition
            screen.result_count = len(security_ids)
            logger.info(
                "Updated universe '%s' with %d securities", name, len(security_ids)
            )
        else:
            import uuid

            screen = SavedScreen(
                screen_id=uuid.uuid4(),
                name=name,
                description=f"{name} index constituents (auto-seeded)",
                screen_type="UNIVERSE",
                is_prebuilt=True,
                definition=definition,
                universe="US_EQUITIES",
                result_count=len(security_ids),
            )
            session.add(screen)
            logger.info(
                "Created universe '%s' with %d securities", name, len(security_ids)
            )

        await session.commit()

    # ── BaseConnector abstract methods (not used — run() is overridden) ──

    async def extract(self) -> list[dict]:
        """Not used; this connector overrides run() directly."""
        return []

    async def validate(self, records: list[dict]) -> list[dict]:
        """Not used; this connector overrides run() directly."""
        return records

    async def transform(self, records: list[dict]) -> list[dict]:
        """Not used; this connector overrides run() directly."""
        return records

    async def load(self, records: list[dict], session: AsyncSession) -> dict[str, int]:
        """Not used; this connector overrides run() directly."""
        return {"inserted": 0, "updated": 0, "skipped": 0, "errors": 0}

    # ── Main entry point ───────────────────────────────────────────

    async def run(self, session: AsyncSession, **kwargs) -> dict:
        """Fetch and seed both S&P 500 and Russell 1000 universes."""
        stats = {
            "sp500_fetched": 0,
            "sp500_resolved": 0,
            "russell1000_fetched": 0,
            "russell1000_resolved": 0,
        }

        # S&P 500
        try:
            sp500_tickers = await self._fetch_sp500_finnhub()
            stats["sp500_fetched"] = len(sp500_tickers)
            if sp500_tickers:
                sp500_ids = await self._resolve_tickers(session, sp500_tickers)
                stats["sp500_resolved"] = len(sp500_ids)
                if sp500_ids:
                    await self._seed_universe(session, "S&P 500", sp500_ids)
        except Exception as exc:
            logger.error("S&P 500 ingestion failed: %s", exc)

        # Russell 1000
        try:
            r1000_tickers = await self._fetch_russell1000_wikipedia()
            stats["russell1000_fetched"] = len(r1000_tickers)
            if r1000_tickers:
                r1000_ids = await self._resolve_tickers(session, r1000_tickers)
                stats["russell1000_resolved"] = len(r1000_ids)
                if r1000_ids:
                    await self._seed_universe(session, "Russell 1000", r1000_ids)
        except Exception as exc:
            logger.error("Russell 1000 ingestion failed: %s", exc)

        return stats
