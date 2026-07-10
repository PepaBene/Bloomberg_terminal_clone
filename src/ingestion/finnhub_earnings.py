"""Finnhub earnings connector: real actual-vs-consensus EPS surprises.

Finnhub's free-tier ``/stock/earnings`` endpoint returns, per historical
quarter, BOTH the reported ``actual`` EPS and the pre-report consensus
``estimate`` (plus the surprise and surprise-percent). That single feed is
enough to populate two read-model tables with genuinely real data:

* ``earnings_surprises`` (entity-keyed, ``EarningsSurprise``) — via the existing
  :class:`~src.ingestion.earnings_surprises_ingest.EarningsSurprisesConnector`,
  which we simply *feed* real actual/consensus pairs (its surprise math and
  upsert/load path were already implemented and unit-tested but had no source).
* ``estimate_surprises`` (security-keyed, ``EstimateSurprise``, ``metric='EPS'``)
  — written directly here.

HONEST SCOPE — what the Finnhub *free* tier does NOT provide (verified 403):
    * ``/stock/price-target``  (consensus price target) → ``consensus_estimates``
    * ``/stock/eps-estimate``  (forward consensus EPS)  → ``consensus_estimates``
    Forward-looking consensus estimates and detailed company *guidance*
    (``company_guidance`` / ``guidance_tracking``) therefore remain UNfilled by
    this connector — they need a premium Finnhub plan or another provider. This
    connector never fabricates those; it only writes the historical
    actual/consensus surprises that the free feed actually returns.
"""

from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.ingestion.earnings_surprises_ingest import EarningsSurprisesConnector
from src.ingestion.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)

FINNHUB_EARNINGS_URL = "https://finnhub.io/api/v1/stock/earnings"


class FinnhubEarningsConnector:
    """Pull historical earnings surprises from Finnhub for one company at a time."""

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or getattr(settings, "FINNHUB_API_KEY", "")
        # Finnhub free tier allows 60 req/min; stay comfortably under.
        self.rate_limiter = RateLimiter(max_requests=30, per_seconds=60.0)

    async def _fetch_earnings(self, symbol: str) -> list[dict]:
        if not self.api_key:
            logger.warning("FINNHUB_API_KEY not set — skipping earnings fetch")
            return []
        await self.rate_limiter.acquire()
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get(
                FINNHUB_EARNINGS_URL,
                params={"symbol": symbol, "token": self.api_key},
            )
            if resp.status_code in (401, 403):
                logger.warning(
                    "Finnhub earnings for %s returned %s (premium/forbidden) — skipping",
                    symbol,
                    resp.status_code,
                )
                return []
            resp.raise_for_status()
            data = resp.json()
            return data if isinstance(data, list) else []

    @staticmethod
    def _period_end(item: dict) -> date | None:
        p = item.get("period")
        if not p:
            return None
        try:
            return date.fromisoformat(str(p)[:10])
        except ValueError:
            return None

    async def fetch_for_entity(
        self,
        session: AsyncSession,
        entity_id: uuid.UUID,
        security_id: uuid.UUID | None,
        symbol: str,
    ) -> dict[str, int]:
        """Fetch earnings surprises for ``symbol`` and write both read models.

        Populates ``earnings_surprises`` (entity-keyed, via the surprise
        connector) and ``estimate_surprises`` (security-keyed, ``metric='EPS'``).
        Idempotent: existing rows for the same (entity, fiscal_year,
        fiscal_quarter) / (security, year, quarter, metric) are updated in place.
        Does NOT commit — the driver owns the transaction.
        """
        stats = {"surprises_inserted": 0, "surprises_updated": 0, "estimate_surprises": 0}
        if not symbol:
            return stats

        try:
            items = await self._fetch_earnings(symbol)
        except Exception as e:  # network / rate-limit / bad symbol — non-fatal
            logger.warning("Finnhub earnings fetch failed for %s: %s", symbol, e)
            return stats

        pairs: list[dict] = []
        for it in items:
            year = it.get("year")
            quarter = it.get("quarter")
            actual = it.get("actual")
            estimate = it.get("estimate")
            if year is None or quarter is None:
                continue
            if actual is None or estimate is None:
                # Need both to have a real actual-vs-consensus pair; skip.
                continue
            period_end = self._period_end(it)
            pairs.append(
                {
                    "entity_id": entity_id,
                    "security_id": security_id,
                    "fiscal_year": int(year),
                    "fiscal_quarter": int(quarter),
                    "period_end_date": period_end,
                    "actual_eps": float(actual),
                    "consensus_eps": float(estimate),
                }
            )

        if not pairs:
            return stats

        # 1) earnings_surprises (entity-keyed) — reuse the tested surprise
        #    connector's compute + upsert/load path with real pairs.
        surprise_stats = await EarningsSurprisesConnector(records=pairs).run(session)
        stats["surprises_inserted"] = surprise_stats.get("inserted", 0)
        stats["surprises_updated"] = surprise_stats.get("updated", 0)

        # 2) estimate_surprises (security-keyed, metric='EPS') — direct upsert.
        if security_id is not None:
            stats["estimate_surprises"] = await self._load_estimate_surprises(
                session, security_id, items
            )

        logger.info(
            "Finnhub earnings %s → surprises(+%d/~%d), estimate_surprises %d",
            symbol,
            stats["surprises_inserted"],
            stats["surprises_updated"],
            stats["estimate_surprises"],
        )
        return stats

    async def _load_estimate_surprises(
        self, session: AsyncSession, security_id: uuid.UUID, items: list[dict]
    ) -> int:
        from src.models.estimates import EstimateSurprise

        written = 0
        for it in items:
            year = it.get("year")
            quarter = it.get("quarter")
            actual = it.get("actual")
            estimate = it.get("estimate")
            if year is None or quarter is None or actual is None or estimate is None:
                continue

            surprise = it.get("surprise")
            surprise_pct = it.get("surprisePercent")
            ann_date = self._period_end(it)  # report period end (no separate ann. date on free feed)

            existing = (
                await session.execute(
                    select(EstimateSurprise).where(
                        EstimateSurprise.security_id == security_id,
                        EstimateSurprise.fiscal_year == int(year),
                        EstimateSurprise.fiscal_quarter == int(quarter),
                        EstimateSurprise.metric == "EPS",
                    )
                )
            ).scalar_one_or_none()

            fields = dict(
                period_type="QUARTER",
                consensus_estimate=float(estimate),
                actual_value=float(actual),
                surprise=float(surprise) if surprise is not None else None,
                surprise_percent=float(surprise_pct) if surprise_pct is not None else None,
                announcement_date=ann_date,
            )

            if existing is not None:
                for k, v in fields.items():
                    setattr(existing, k, v)
            else:
                session.add(
                    EstimateSurprise(
                        surprise_id=uuid.uuid4(),
                        security_id=security_id,
                        fiscal_year=int(year),
                        fiscal_quarter=int(quarter),
                        metric="EPS",
                        **fields,
                    )
                )
            written += 1

        await session.flush()
        return written
