"""Polygon.io corporate actions connector — dividends + splits (Domain 5).

Fetches structured dividend and stock-split data from Polygon.io's reference
endpoints and writes them into the canonical ``CorporateAction`` table (plus
the ``DividendAction`` / ``SplitAction`` subtype tables) — the table actually
read by ``GET /v1/securities/{security_id}/corporate-actions``.

Why Polygon instead of EDGAR 8-K text:
    SEC 8-K filings announce dividends/splits in free-text prose (Item 8.01/
    5.03) with no guaranteed structured ex/record/payment-date fields — any
    connector built by regex-scraping that prose would either miss most real
    events or risk mis-parsing dates. Polygon's ``/v3/reference/dividends``
    and ``/v3/reference/splits`` endpoints, by contrast, return exactly the
    structured fields ``CorporateAction``/``DividendAction``/``SplitAction``
    need (cash amount, frequency, ex/record/pay dates, split ratio) and are
    already the data source this codebase uses for EOD prices
    (``polygon_eod.py``), so this connector reuses the same API key / rate
    limiter pattern.

M&A events are intentionally NOT written here — ``edgar_ma_deals.py`` already
covers those into the separate ``MADeals`` model.
"""

from __future__ import annotations

import logging
import uuid
from datetime import date
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.ingestion.base import BaseConnector
from src.ingestion.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)

POLYGON_BASE_URL = "https://api.polygon.io"
DIVIDENDS_URL = f"{POLYGON_BASE_URL}/v3/reference/dividends"
SPLITS_URL = f"{POLYGON_BASE_URL}/v3/reference/splits"

# Polygon dividend_type -> our DividendAction.dividend_type vocabulary.
_DIVIDEND_TYPE_MAP = {
    "CD": "REGULAR",       # regular cash dividend
    "SC": "SPECIAL",       # special cash dividend
    "LT": "CAPITAL_GAIN",  # long-term capital gain distribution
    "ST": "CAPITAL_GAIN",  # short-term capital gain distribution
}

# Polygon frequency (payments/year) -> our DividendAction.frequency vocabulary.
_FREQUENCY_MAP = {
    0: "IRREGULAR",
    1: "ANNUAL",
    2: "SEMI_ANNUAL",
    4: "QUARTERLY",
    12: "MONTHLY",
    24: "SEMI_MONTHLY",
    52: "WEEKLY",
    365: "DAILY",
}


class PolygonCorporateActionsConnector(BaseConnector):
    """Ingest real dividend + split corporate actions from Polygon.io."""

    name = "Polygon Corporate Actions"
    connector_type = "BATCH_API"
    data_domain = "CORPORATE_ACTIONS"

    def __init__(
        self,
        tickers: list[str] | None = None,
        api_key: str | None = None,
    ) -> None:
        self.tickers = tickers or []
        self.api_key = api_key or getattr(settings, "POLYGON_API_KEY", "")
        polygon_rate_limit = getattr(settings, "POLYGON_RATE_LIMIT", 5)
        # POLYGON_RATE_LIMIT is calls-per-MINUTE (free tier: 5/min) — per_seconds
        # must be 60.0, not 1.0, or every request past the first 5/min gets a
        # real 429 from Polygon (confirmed live 2026-07-22: 100% 429 rate at
        # per_seconds=1.0, silently logged as "0 dividends/splits" per ticker).
        self.rate_limiter = RateLimiter(max_requests=polygon_rate_limit, per_seconds=60.0)
        self._client: httpx.AsyncClient | None = None
        # ticker -> (security_id, entity_id), populated during load()
        self._security_map: dict[str, tuple[uuid.UUID, uuid.UUID | None]] = {}

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def _polygon_get(self, url: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        """Rate-limited GET against a Polygon reference endpoint, paginated."""
        results: list[dict[str, Any]] = []
        client = await self._get_client()
        next_url: str | None = url
        next_params: dict[str, Any] | None = {**params, "apiKey": self.api_key}
        page_guard = 0
        while next_url and page_guard < 20:
            page_guard += 1
            await self.rate_limiter.acquire()
            try:
                resp = await client.get(next_url, params=next_params)
                resp.raise_for_status()
                data = resp.json()
            except httpx.HTTPStatusError as e:
                logger.warning("Polygon corporate actions request failed: %s", e)
                break
            except Exception as e:  # noqa: BLE001
                logger.error("Unexpected error calling Polygon (%s): %s", next_url, e)
                break
            results.extend(data.get("results", []) or [])
            cursor_url = data.get("next_url")
            if cursor_url:
                next_url = cursor_url
                # next_url already carries its own query string; apiKey must
                # still be appended since Polygon strips it from next_url.
                next_params = {"apiKey": self.api_key}
            else:
                next_url = None
        return results

    async def extract(self) -> list[dict[str, Any]]:
        """Pull raw dividend + split records per configured ticker."""
        if not self.api_key:
            logger.warning("POLYGON_API_KEY not set — skipping corporate actions extraction")
            return []
        if not self.tickers:
            logger.warning("No tickers configured — skipping corporate actions extraction")
            return []

        records: list[dict[str, Any]] = []
        for ticker in self.tickers:
            divs = await self._polygon_get(DIVIDENDS_URL, {"ticker": ticker, "limit": 100})
            for d in divs:
                records.append({"kind": "DIVIDEND", "ticker": ticker, **d})

            splits = await self._polygon_get(SPLITS_URL, {"ticker": ticker, "limit": 100})
            for s in splits:
                records.append({"kind": "SPLIT", "ticker": ticker, **s})

            logger.info(
                "  Polygon CA: %s — %d dividends, %d splits",
                ticker, len(divs), len(splits),
            )
        return records

    async def validate(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Drop records missing the fields required to build a CorporateAction."""
        valid = []
        for rec in records:
            if not rec.get("ticker"):
                continue
            if rec["kind"] == "DIVIDEND":
                if not rec.get("ex_dividend_date") or rec.get("cash_amount") is None:
                    continue
            elif rec["kind"] == "SPLIT":
                if not rec.get("execution_date"):
                    continue
                if not rec.get("split_from") or not rec.get("split_to"):
                    continue
            valid.append(rec)
        return valid

    async def transform(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Normalize Polygon dividend/split payloads into CorporateAction shape."""
        today = date.today()
        transformed: list[dict[str, Any]] = []

        for rec in records:
            ticker = rec["ticker"]

            if rec["kind"] == "DIVIDEND":
                ex_date = _parse_date(rec.get("ex_dividend_date"))
                if ex_date is None:
                    continue
                status = "COMPLETED" if ex_date <= today else "ANNOUNCED"
                transformed.append({
                    "kind": "DIVIDEND",
                    "ticker": ticker,
                    "action_type": "CASH_DIVIDEND",
                    "status": status,
                    "announcement_date": _parse_date(rec.get("declaration_date")),
                    "ex_date": ex_date,
                    "record_date": _parse_date(rec.get("record_date")),
                    "payment_date": _parse_date(rec.get("pay_date")),
                    "description": f"{ticker} cash dividend of {rec['cash_amount']} per share",
                    "source": "POLYGON",
                    "dividend_type": _DIVIDEND_TYPE_MAP.get(
                        rec.get("dividend_type"), "REGULAR"
                    ),
                    "frequency": _FREQUENCY_MAP.get(rec.get("frequency"), None),
                    "gross_amount": float(rec["cash_amount"]),
                    "currency": (rec.get("currency") or "USD").upper()[:3],
                })
            elif rec["kind"] == "SPLIT":
                exec_date = _parse_date(rec.get("execution_date"))
                if exec_date is None:
                    continue
                split_from = int(rec["split_from"])
                split_to = int(rec["split_to"])
                if split_from <= 0:
                    continue
                status = "COMPLETED" if exec_date <= today else "ANNOUNCED"
                action_type = "STOCK_SPLIT" if split_to >= split_from else "REVERSE_SPLIT"
                transformed.append({
                    "kind": "SPLIT",
                    "ticker": ticker,
                    "action_type": action_type,
                    "status": status,
                    "ex_date": exec_date,
                    "description": f"{ticker} {split_to}-for-{split_from} split",
                    "source": "POLYGON",
                    "split_ratio_from": split_from,
                    "split_ratio_to": split_to,
                    "split_factor": round(split_to / split_from, 6),
                    "adjustment_factor": round(split_from / split_to, 10),
                })

        logger.info("Transformed %d corporate action records", len(transformed))
        return transformed

    async def load(
        self, records: list[dict[str, Any]], session: AsyncSession
    ) -> dict[str, int]:
        """Write CorporateAction (+ DividendAction/SplitAction) rows."""
        from src.models.corporate_actions import CorporateAction, DividendAction, SplitAction
        from src.models.security import Security, SecurityIdentifier

        stats = {"inserted": 0, "updated": 0, "skipped": 0, "errors": 0}

        if not self._security_map:
            result = await session.execute(
                select(
                    SecurityIdentifier.identifier_value,
                    Security.security_id,
                    Security.issuer_entity_id,
                )
                .join(Security, Security.security_id == SecurityIdentifier.security_id)
                .where(SecurityIdentifier.identifier_type == "TICKER")
            )
            for ticker_val, security_id, issuer_entity_id in result.all():
                self._security_map[ticker_val.upper()] = (security_id, issuer_entity_id)
            logger.info(
                "  Polygon CA: built ticker map with %d securities", len(self._security_map)
            )

        for rec in records:
            try:
                ticker = rec["ticker"].upper()
                mapping = self._security_map.get(ticker)
                if mapping is None:
                    # Unknown ticker — not in our security master. Never
                    # fabricate a security_id; just skip.
                    stats["skipped"] += 1
                    continue
                security_id, entity_id = mapping

                # De-dupe on (security_id, action_type, ex_date) — Polygon
                # re-serves the same historical dividend/split on every call.
                existing = await session.execute(
                    select(CorporateAction).where(
                        CorporateAction.security_id == security_id,
                        CorporateAction.action_type == rec["action_type"],
                        CorporateAction.ex_date == rec["ex_date"],
                    )
                )
                if existing.scalar_one_or_none() is not None:
                    stats["skipped"] += 1
                    continue

                action = CorporateAction(
                    action_id=uuid.uuid4(),
                    action_type=rec["action_type"],
                    security_id=security_id,
                    entity_id=entity_id,
                    announcement_date=rec.get("announcement_date"),
                    ex_date=rec["ex_date"],
                    record_date=rec.get("record_date"),
                    payment_date=rec.get("payment_date"),
                    status=rec["status"],
                    description=rec.get("description"),
                    source=rec["source"],
                )
                session.add(action)
                await session.flush()

                if rec["kind"] == "DIVIDEND":
                    session.add(DividendAction(
                        action_id=action.action_id,
                        dividend_type=rec["dividend_type"],
                        frequency=rec.get("frequency"),
                        gross_amount=rec["gross_amount"],
                        currency=rec.get("currency"),
                    ))
                elif rec["kind"] == "SPLIT":
                    session.add(SplitAction(
                        action_id=action.action_id,
                        split_ratio_from=rec["split_ratio_from"],
                        split_ratio_to=rec["split_ratio_to"],
                        split_factor=rec.get("split_factor"),
                        adjustment_factor=rec.get("adjustment_factor"),
                    ))

                stats["inserted"] += 1
            except Exception:  # noqa: BLE001
                logger.exception("Error loading corporate action for %s", rec.get("ticker"))
                stats["errors"] += 1

        await session.flush()
        return stats

    async def close(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None


def _parse_date(value: Any) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None
