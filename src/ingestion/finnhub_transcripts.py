"""Finnhub earnings call transcript connector.

HONEST SCOPE — verified 403 (Forbidden) live against the configured free-tier
FINNHUB_API_KEY: ``/stock/transcripts/list`` requires a premium Finnhub plan.
This mirrors the same free-tier wall already documented in
:mod:`src.ingestion.finnhub_earnings` for ``/stock/price-target`` and
``/stock/eps-estimate`` — this connector is written and ready, but produces
no rows until the API key is upgraded (or another transcript source is
wired in). It never fabricates transcript content.

Destination: ``earnings_call_transcripts`` (``EarningsCallTranscript``) —
raw_text/prepared_remarks/qa_section/participants only. The tone/topic/AI
analysis columns on that model are computed separately by
:class:`~src.engines.transcript_engine.TranscriptEngine`, not by ingestion.
"""

from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timezone
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.ingestion.base import BaseConnector
from src.ingestion.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)

FINNHUB_TRANSCRIPTS_LIST_URL = "https://finnhub.io/api/v1/stock/transcripts/list"
FINNHUB_TRANSCRIPT_DETAIL_URL = "https://finnhub.io/api/v1/stock/transcripts"


class FinnhubTranscriptsConnector(BaseConnector):
    """Pull earnings call transcripts from Finnhub, one company at a time."""

    name = "Finnhub Earnings Transcripts"
    connector_type = "BATCH_API"
    data_domain = "EARNINGS"

    def __init__(
        self,
        symbols: list[str] | None = None,
        entity_ids: dict[str, uuid.UUID] | None = None,
        api_key: str | None = None,
    ) -> None:
        """
        Args:
            symbols: Ticker symbols to fetch transcripts for.
            entity_ids: symbol -> entity_id map (load() needs entity_id, not
                just a ticker string, to satisfy the FK).
            api_key: Override for settings.FINNHUB_API_KEY.
        """
        self.symbols = symbols or []
        self.entity_ids = entity_ids or {}
        self.api_key = api_key or getattr(settings, "FINNHUB_API_KEY", "")
        # Finnhub free tier allows 60 req/min; stay comfortably under.
        self.rate_limiter = RateLimiter(max_requests=30, per_seconds=60.0)
        self._client: httpx.AsyncClient | None = None
        self._premium_required = False  # set True on first 403, short-circuits the rest

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=20.0)
        return self._client

    async def _fetch_transcript_list(self, symbol: str) -> list[dict]:
        if not self.api_key or self._premium_required:
            return []
        await self.rate_limiter.acquire()
        client = await self._get_client()
        resp = await client.get(
            FINNHUB_TRANSCRIPTS_LIST_URL, params={"symbol": symbol, "token": self.api_key}
        )
        if resp.status_code in (401, 403):
            logger.warning(
                "Finnhub transcripts for %s returned %s (premium plan required) — "
                "skipping this and all remaining symbols this run",
                symbol,
                resp.status_code,
            )
            self._premium_required = True
            return []
        resp.raise_for_status()
        data = resp.json()
        return data.get("transcripts", []) if isinstance(data, dict) else []

    async def _fetch_transcript_detail(self, transcript_id: str) -> dict | None:
        if not self.api_key or self._premium_required:
            return None
        await self.rate_limiter.acquire()
        client = await self._get_client()
        resp = await client.get(
            FINNHUB_TRANSCRIPT_DETAIL_URL, params={"id": transcript_id, "token": self.api_key}
        )
        if resp.status_code in (401, 403):
            self._premium_required = True
            return None
        resp.raise_for_status()
        return resp.json()

    async def extract(self) -> list[dict[str, Any]]:
        if not self.symbols:
            logger.warning("[%s] No symbols configured — skipping extraction", self.name)
            return []
        if not self.api_key:
            logger.warning("[%s] FINNHUB_API_KEY not set — skipping extraction", self.name)
            return []

        records: list[dict[str, Any]] = []
        for symbol in self.symbols:
            if self._premium_required:
                break
            entity_id = self.entity_ids.get(symbol)
            if entity_id is None:
                continue
            try:
                listings = await self._fetch_transcript_list(symbol)
            except Exception as e:
                logger.error("[%s] Failed to list transcripts for %s: %s", self.name, symbol, e)
                continue

            for item in listings:
                transcript_id = item.get("id")
                if not transcript_id:
                    continue
                try:
                    detail = await self._fetch_transcript_detail(str(transcript_id))
                except Exception as e:
                    logger.error(
                        "[%s] Failed to fetch transcript %s for %s: %s",
                        self.name, transcript_id, symbol, e,
                    )
                    continue
                if not detail:
                    continue
                records.append({
                    "symbol": symbol,
                    "entity_id": entity_id,
                    "transcript_id": transcript_id,
                    "title": item.get("title"),
                    "list_date": item.get("time"),
                    "detail": detail,
                })

        if self._premium_required:
            logger.warning(
                "[%s] Finnhub transcripts require a premium plan — 0 transcripts "
                "fetched this run (not a bug, verified 403 on the configured key)",
                self.name,
            )
        return records

    async def validate(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [r for r in records if r.get("detail", {}).get("transcript")]

    async def transform(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        transformed = []
        for rec in records:
            detail = rec["detail"]
            speakers = detail.get("transcript", [])  # [{name, speech: [str,...]}]
            participants = detail.get("participant", [])  # [{name, description}]

            prepared_parts: list[str] = []
            qa_parts: list[str] = []
            ceo_parts: list[str] = []
            cfo_parts: list[str] = []
            in_qa = False

            def _is_role(name: str, keywords: tuple[str, ...]) -> bool:
                lname = (name or "").lower()
                return any(k in lname for k in keywords)

            for seg in speakers:
                name = seg.get("name", "")
                text = " ".join(seg.get("speech", []) or [])
                if not text:
                    continue
                lname = name.lower()
                if "operator" in lname and ("question" in text.lower() or "q&a" in text.lower()):
                    in_qa = True
                bucket = qa_parts if in_qa else prepared_parts
                bucket.append(f"{name}: {text}")
                if _is_role(name, ("ceo", "chief executive")):
                    ceo_parts.append(text)
                if _is_role(name, ("cfo", "chief financial")):
                    cfo_parts.append(text)

            raw_text = "\n\n".join(prepared_parts + qa_parts) or None
            call_date_str = detail.get("time") or rec.get("list_date")
            try:
                call_date = (
                    datetime.fromtimestamp(int(call_date_str), tz=timezone.utc).date()
                    if isinstance(call_date_str, (int, float, str)) and str(call_date_str).isdigit()
                    else date.fromisoformat(str(call_date_str)[:10])
                )
            except (ValueError, TypeError):
                continue

            fiscal_quarter = detail.get("quarter") or 0
            fiscal_year = detail.get("year") or call_date.year
            if not fiscal_quarter:
                continue

            transformed.append({
                "entity_id": rec["entity_id"],
                "call_date": call_date,
                "fiscal_year": int(fiscal_year),
                "fiscal_quarter": int(fiscal_quarter),
                "call_type": "EARNINGS",
                "raw_text": raw_text,
                "prepared_remarks": "\n\n".join(prepared_parts) or None,
                "qa_section": "\n\n".join(qa_parts) or None,
                "ceo_section": "\n\n".join(ceo_parts) or None,
                "cfo_section": "\n\n".join(cfo_parts) or None,
                "participants": participants or None,
                "source_url": None,
                "source_type": "FINNHUB",
            })
        return transformed

    async def load(
        self, records: list[dict[str, Any]], session: AsyncSession
    ) -> dict[str, int]:
        from src.models.earnings_transcript import EarningsCallTranscript

        stats = {"inserted": 0, "updated": 0, "skipped": 0, "errors": 0}
        if getattr(self, "dry_run", False):
            return stats

        for rec in records:
            try:
                existing = await session.execute(
                    select(EarningsCallTranscript).where(
                        EarningsCallTranscript.entity_id == rec["entity_id"],
                        EarningsCallTranscript.fiscal_year == rec["fiscal_year"],
                        EarningsCallTranscript.fiscal_quarter == rec["fiscal_quarter"],
                    )
                )
                row = existing.scalar_one_or_none()
                if row is not None:
                    stats["skipped"] += 1
                    continue

                session.add(EarningsCallTranscript(
                    id=uuid.uuid4(),
                    ai_enabled=False,
                    **rec,
                ))
                stats["inserted"] += 1
            except Exception as e:
                logger.error("[%s] Error loading transcript: %s", self.name, e)
                stats["errors"] += 1

        await session.flush()
        return stats

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None
