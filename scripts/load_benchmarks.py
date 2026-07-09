"""Load market-benchmark ETFs (SPY, etc.) as securities with EOD price history.

Beta (WACC, quant, risk) regresses a security's returns against a market proxy —
``settings.ANALYTICS_MARKET_BENCHMARK_TICKER`` (SPY). But SPY is an ETF, not one
of our EDGAR issuer entities, so the entity-driven OpenFIGI/EOD pipeline never
created it and beta was null everywhere. This script creates the benchmark ETFs
directly and pulls their daily bars from Polygon's per-ticker aggregates endpoint.

Idempotent: existing securities/prices are reused (prices upserted by date).
"""

from __future__ import annotations

import asyncio
import logging
import sys
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text

from src.config import settings
from src.database import get_session_factory
from src.ingestion.rate_limiter import RateLimiter

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("load_benchmarks")

# Common broad-market / index ETFs. SPY is the beta benchmark; the rest are handy
# reference series. All are ETFs with no issuer entity.
BENCHMARKS = {
    "SPY": "SPDR S&P 500 ETF Trust",
    "QQQ": "Invesco QQQ Trust (Nasdaq-100)",
    "DIA": "SPDR Dow Jones Industrial Average ETF",
    "IWM": "iShares Russell 2000 ETF",
}
AGGS_URL = "https://api.polygon.io/v2/aggs/ticker/{ticker}/range/1/day/{frm}/{to}"


async def _ensure_security(session, ticker: str, name: str) -> uuid.UUID:
    existing = await session.scalar(
        text(
            "SELECT security_id FROM security_identifiers "
            "WHERE identifier_type='TICKER' AND identifier_value=:t"
        ),
        {"t": ticker},
    )
    if existing:
        return existing
    security_id = uuid.uuid4()
    await session.execute(
        text(
            """
            INSERT INTO securities (security_id, security_type, name, short_name,
                                    status, asset_class, primary_currency)
            VALUES (:id, 'ETF', :name, :ticker, 'ACTIVE', 'EQUITY', 'USD')
            """
        ),
        {"id": security_id, "name": name, "ticker": ticker},
    )
    await session.execute(
        text(
            """
            INSERT INTO security_identifiers (id, security_id, identifier_type,
                                              identifier_value, source)
            VALUES (:iid, :sid, 'TICKER', :t, 'BENCHMARK_LOADER')
            """
        ),
        {"iid": uuid.uuid4(), "sid": security_id, "t": ticker},
    )
    await session.commit()
    logger.info("Created benchmark security %s (%s)", ticker, name)
    return security_id


async def _load_prices(session, security_id: uuid.UUID, ticker: str,
                       limiter: RateLimiter, frm: str, to: str) -> int:
    if not settings.POLYGON_API_KEY:
        logger.warning("POLYGON_API_KEY not set — cannot load %s", ticker)
        return 0
    await limiter.acquire()
    url = AGGS_URL.format(ticker=ticker, frm=frm, to=to)
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(url, params={"adjusted": "true", "sort": "asc",
                                             "limit": 50000, "apiKey": settings.POLYGON_API_KEY})
        resp.raise_for_status()
        results = resp.json().get("results", []) or []

    inserted = 0
    for bar in results:
        ts = bar.get("t")
        if ts is None:
            continue
        pdate = datetime.fromtimestamp(ts / 1000, timezone.utc).date()
        await session.execute(
            text(
                """
                INSERT INTO eod_prices (security_id, price_date, open, high, low,
                                        close, close_adjusted, volume, currency, source)
                VALUES (:sid, :d, :o, :h, :l, :c, :c, :v, 'USD', 'POLYGON')
                ON CONFLICT (security_id, price_date) DO UPDATE SET
                    close = EXCLUDED.close, close_adjusted = EXCLUDED.close_adjusted,
                    volume = EXCLUDED.volume
                """
            ),
            {"sid": security_id, "d": pdate, "o": bar.get("o"), "h": bar.get("h"),
             "l": bar.get("l"), "c": bar.get("c"), "v": bar.get("v")},
        )
        inserted += 1
    await session.commit()
    logger.info("%s: loaded %d daily bars", ticker, inserted)
    return inserted


async def main() -> None:
    to = date.today() - timedelta(days=1)
    frm = to - timedelta(days=450)
    limiter = RateLimiter(max_requests=getattr(settings, "POLYGON_RATE_LIMIT", 5), per_seconds=60.0)
    async with get_session_factory()() as session:
        total = 0
        for ticker, name in BENCHMARKS.items():
            sid = await _ensure_security(session, ticker, name)
            total += await _load_prices(session, sid, ticker, limiter,
                                        frm.isoformat(), to.isoformat())
        logger.info("Benchmark load complete: %d total bars across %d ETFs",
                    total, len(BENCHMARKS))


if __name__ == "__main__":
    asyncio.run(main())
