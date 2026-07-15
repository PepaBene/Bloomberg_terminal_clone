"""Alpha Vantage forward consensus-estimate connector (EPS).

Ingests forward-looking consensus EPS figures from Alpha Vantage's free
``EARNINGS`` endpoint into ``ConsensusEstimate``. Unlike most connectors in
this package (which resolve by CIK), Alpha Vantage's ``EARNINGS`` function is
keyed by exchange ticker symbol, so this connector is ticker-driven.

FLAG — UNTESTED AGAINST LIVE DATA
----------------------------------
Outbound network access to Alpha Vantage is blocked in the sandbox this
connector was written in, so it has **not** been exercised against a live
``https://www.alphavantage.co/query?function=EARNINGS`` response. The
extract/validate/transform/load logic here is written to match Alpha
Vantage's publicly documented response shape for the ``EARNINGS`` function
(``{"symbol": ..., "annualEarnings": [...], "quarterlyEarnings": [...]}``)
and is unit-tested against a realistic mocked fixture of that shape — but it
must be validated against the live endpoint (auth, rate-limit headers, edge
cases in the real payload) before being trusted in production. No estimate
rows are fabricated: tickers that don't resolve to an existing ``Security``
are skipped and logged, not invented, and rows with missing/placeholder
consensus figures are dropped in ``validate()``.

Known data limitations (see inline comments in ``transform()``):
  * The free ``EARNINGS`` endpoint exposes only a single consensus EPS
    figure (``estimatedEPS``) per fiscal quarter — no high/low/median/std-dev
    spread and no analyst count. Those ``ConsensusEstimate`` fields are left
    ``None`` rather than guessed.
  * The endpoint returns the *current* consensus snapshot only; it does not
    expose historical estimate-revision vintages. ``as_of_date`` is therefore
    set to the date this connector runs, not a true point-in-time date of
    when the estimate was originally published.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.ingestion.base import BaseConnector
from src.ingestion.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)

ALPHA_VANTAGE_URL = "https://www.alphavantage.co/query"

# Alpha Vantage uses the literal string "None" (not null/absent) for missing
# numeric fields in the EARNINGS response.
_MISSING_SENTINELS = {"none", "", "n/a", "null"}


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and value.strip().lower() in _MISSING_SENTINELS:
        return True
    return False


def _fiscal_quarter_from_month(month: int) -> int:
    """Derive a 1-4 fiscal quarter from a fiscal-period-end month.

    Alpha Vantage doesn't report a fiscal quarter number directly, only
    ``fiscalDateEnding``. This assumes a standard 3-month quarter cadence
    ending on ``fiscalDateEnding`` (true for the vast majority of issuers,
    including those with non-calendar fiscal years).
    """
    return ((month - 1) // 3) + 1


class AlphaVantageEstimatesConnector(BaseConnector):
    """Ingest forward consensus EPS estimates from Alpha Vantage's EARNINGS endpoint."""

    name = "Alpha Vantage Consensus Estimates"
    connector_type = "BATCH_API"
    data_domain = "ESTIMATES"

    def __init__(
        self,
        api_key: str | None = None,
        tickers: list[str] | None = None,
    ):
        self.api_key = api_key or getattr(settings, "ALPHA_VANTAGE_API_KEY", "")
        self.tickers = tickers or []
        # Free tier: 5 requests/minute, 25/day. The rate limiter enforces the
        # per-minute cap; the daily cap is the caller's responsibility (see
        # scripts/ingest_consensus_estimates.py's small default --limit).
        rate = getattr(settings, "ALPHA_VANTAGE_RATE_LIMIT", 5)
        self.rate_limiter = RateLimiter(max_requests=rate, per_seconds=60.0)
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def _fetch_earnings(self, ticker: str) -> dict[str, Any] | None:
        """Fetch the raw EARNINGS payload for one ticker (rate-limited)."""
        await self.rate_limiter.acquire()
        client = await self._get_client()
        params = {"function": "EARNINGS", "symbol": ticker, "apikey": self.api_key}
        try:
            resp = await client.get(ALPHA_VANTAGE_URL, params=params)
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:  # pragma: no cover - network
            logger.warning("[%s] failed to fetch EARNINGS for %s: %s", self.name, ticker, exc)
            return None

    @staticmethod
    def _extract_quarterly_rows(data: dict[str, Any], fallback_symbol: str) -> list[dict[str, Any]]:
        """Flatten one EARNINGS response into per-quarter row dicts. Pure (no I/O).

        Handles Alpha Vantage's documented error-response shapes
        (``{"Note": ...}`` for rate-limit throttling, ``{"Error Message": ...}``
        for unknown symbols, ``{"Information": ...}`` for other API notices) by
        returning no rows rather than raising.
        """
        if not isinstance(data, dict):
            return []
        if "Note" in data or "Error Message" in data or "Information" in data:
            logger.warning(
                "AlphaVantage EARNINGS API notice for %s: %s",
                fallback_symbol,
                data.get("Note") or data.get("Error Message") or data.get("Information"),
            )
            return []

        symbol = data.get("symbol") or fallback_symbol
        out: list[dict[str, Any]] = []
        for row in data.get("quarterlyEarnings", []):
            out.append(
                {
                    "symbol": symbol,
                    "fiscalDateEnding": row.get("fiscalDateEnding"),
                    "reportedDate": row.get("reportedDate"),
                    "reportedEPS": row.get("reportedEPS"),
                    "estimatedEPS": row.get("estimatedEPS"),
                    "surprise": row.get("surprise"),
                    "surprisePercentage": row.get("surprisePercentage"),
                }
            )
        return out

    async def extract(self) -> list[dict[str, Any]]:
        if not self.tickers:
            logger.warning("[%s] no tickers configured — skipping extraction", self.name)
            return []
        if not self.api_key:
            logger.warning("[%s] ALPHA_VANTAGE_API_KEY not set — skipping extraction", self.name)
            return []

        records: list[dict[str, Any]] = []
        for ticker in self.tickers:
            data = await self._fetch_earnings(ticker)
            if data is None:
                continue
            rows = self._extract_quarterly_rows(data, ticker)
            logger.info("[%s] %s — %d quarterly earnings rows", self.name, ticker, len(rows))
            records.extend(rows)
        return records

    async def validate(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Drop rows missing symbol/fiscalDateEnding, or with no usable estimatedEPS."""
        valid: list[dict[str, Any]] = []
        for r in records:
            if _is_missing(r.get("symbol")) or _is_missing(r.get("fiscalDateEnding")):
                continue
            if _is_missing(r.get("estimatedEPS")):
                continue
            try:
                float(r["estimatedEPS"])
            except (TypeError, ValueError):
                continue
            valid.append(r)
        return valid

    async def transform(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Map validated EARNINGS rows into ConsensusEstimate field dicts. Pure."""
        out: list[dict[str, Any]] = []
        today = date.today()
        for r in records:
            try:
                period_end_date = date.fromisoformat(r["fiscalDateEnding"])
            except (ValueError, TypeError):
                continue

            out.append(
                {
                    "ticker": str(r["symbol"]).upper(),
                    "metric": "EPS",
                    "period_end_date": period_end_date,
                    "as_of_date": today,
                    "fiscal_year": period_end_date.year,
                    "fiscal_quarter": _fiscal_quarter_from_month(period_end_date.month),
                    "period_type": "QUARTERLY",
                    # Alpha Vantage doesn't report the estimate's denomination
                    # currency; guessing would risk a wrong value for non-USD
                    # ADRs, so we leave it unset rather than fabricate it.
                    "currency": None,
                    "mean": float(r["estimatedEPS"]),
                    # The free EARNINGS endpoint only exposes a single
                    # consensus mean — no high/low/median/std-dev spread and
                    # no analyst count are available from this source.
                    "median": None,
                    "high": None,
                    "low": None,
                    "standard_deviation": None,
                    "num_estimates": None,
                    "num_revisions_up": None,
                    "num_revisions_down": None,
                }
            )
        logger.info("[%s] transformed %d consensus estimate rows", self.name, len(out))
        return out

    async def load(
        self, records: list[dict[str, Any]], session: AsyncSession
    ) -> dict[str, int]:
        from src.models.estimates import ConsensusEstimate
        from src.models.security import SecurityIdentifier

        stats = {"inserted": 0, "updated": 0, "skipped": 0, "errors": 0}
        if getattr(self, "dry_run", False):
            return stats

        # Resolve ticker -> security_id via the established SecurityIdentifier
        # (identifier_type="TICKER") lookup pattern used by openfigi_securities.py
        # / polygon_eod.py.
        ticker_map: dict[str, Any] = {}
        tickers_needed = {r["ticker"] for r in records}
        if tickers_needed:
            result = await session.execute(
                select(SecurityIdentifier).where(
                    SecurityIdentifier.identifier_type == "TICKER",
                    SecurityIdentifier.identifier_value.in_(tickers_needed),
                )
            )
            for row in result.scalars().all():
                ticker_map[row.identifier_value.upper()] = row.security_id

        for rec in records:
            try:
                ticker = rec["ticker"]
                security_id = ticker_map.get(ticker)
                if security_id is None:
                    logger.info(
                        "[%s] skipping %s — no existing Security for this ticker "
                        "(no fabricated security created)",
                        self.name,
                        ticker,
                    )
                    stats["skipped"] += 1
                    continue

                fields = {k: v for k, v in rec.items() if k != "ticker"}

                existing = (
                    await session.execute(
                        select(ConsensusEstimate).where(
                            ConsensusEstimate.security_id == security_id,
                            ConsensusEstimate.metric == fields["metric"],
                            ConsensusEstimate.period_end_date == fields["period_end_date"],
                            ConsensusEstimate.as_of_date == fields["as_of_date"],
                        )
                    )
                ).scalar_one_or_none()

                if existing:
                    for key, val in fields.items():
                        setattr(existing, key, val)
                    stats["updated"] += 1
                else:
                    session.add(ConsensusEstimate(security_id=security_id, **fields))
                    stats["inserted"] += 1
            except Exception:  # pragma: no cover - defensive
                logger.exception("[%s] failed to load estimate row", self.name)
                stats["errors"] += 1

        await session.flush()
        return stats

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None
