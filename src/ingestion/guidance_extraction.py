"""SEC EDGAR 8-K Item 2.02 guidance-extraction connector.

Fetches 8-K filings with Item 2.02 ("Results of Operations and Financial
Condition") from SEC EDGAR — reusing the exact submissions-fetch pattern from
``edgar_8k.py`` — then fetches each filing's primary document body directly
and regex-extracts forward-looking revenue/EPS guidance language from the
press-release text into ``GuidanceTracking`` rows.

Note: ``EightKEvent.raw_text`` (``src/models/filing_intelligence.py``) is
never populated by ``edgar_8k.py``'s ``load()``, so this connector cannot
reuse already-ingested text — it fetches the filing document body itself.

FLAG — UNTESTED AGAINST LIVE DATA
----------------------------------
Outbound network access to SEC EDGAR is blocked in the sandbox this
connector was written in, so it has **not** been exercised against live
``data.sec.gov`` submissions JSON or live 8-K document bodies. The
submissions-fetch / document-fetch mechanics mirror ``edgar_8k.py`` (which is
itself the established, working pattern for this codebase), and the regex
extraction logic is unit-tested against realistic synthetic Item 2.02
press-release paragraphs — but the real wire behavior (redirects, HTML vs.
plain-text primary documents, throttling) must be validated against the live
feed before production use.

Guidance extraction is inherently imperfect free-text regex matching over
heterogeneous press-release prose (similar in spirit to ``edgar_esg.py``'s
regex-based governance scoring): it is real, deterministic extraction — not
fabricated data — but it will miss guidance phrased in unanticipated ways and
can occasionally misattribute a figure. Filings with no matching guidance
language are skipped, not guessed at. An optional second pass using the AI
core's Claude client (``src/ai/client.py``) can supplement the regex pass
when ``ANTHROPIC_API_KEY`` is configured; it is best-effort only and any
failure silently falls back to the regex result.
"""

from __future__ import annotations

import logging
import re
import uuid
from datetime import date, timedelta
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.ingestion.base import BaseConnector
from src.ingestion.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)

SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"

ITEM_202 = "2.02"

# Minimum body length to be worth regex-scanning for guidance language.
_MIN_BODY_LENGTH = 200

# --- Guidance figure extraction -------------------------------------------
# As documented in the module docstring above: real, deterministic regex
# extraction over free-text press-release prose. It is intentionally
# permissive (broad [^.]{0,N} gaps) to catch common phrasings, at the cost of
# occasionally missing unusual ones or grabbing an adjacent figure. Never
# invents a figure when nothing matches.
_GUIDANCE_RANGE_PATTERN = re.compile(
    r"(?:expects?|anticipates?|guidance|outlook|projects?)[^.]{0,50}"
    r"(revenue|EPS|earnings per share|net sales)[^.]{0,100}?"
    r"\$?([\d,]+(?:\.\d+)?)\s*(?:to|-|–)\s*\$?([\d,]+(?:\.\d+)?)\s*"
    r"(billion|million)?",
    re.IGNORECASE,
)

_GUIDANCE_POINT_PATTERN = re.compile(
    r"(?:expects?|anticipates?|guidance|outlook|projects?)[^.]{0,50}"
    r"(revenue|EPS|earnings per share|net sales)[^.]{0,100}?"
    r"\$?([\d,]+(?:\.\d+)?)\s*(billion|million)?",
    re.IGNORECASE,
)

_PRIOR_GUIDANCE_PATTERN = re.compile(
    r"(?:prior|previous(?:ly)?)\s+guidance\s+(?:of\s+)?"
    r"\$?([\d,]+(?:\.\d+)?)\s*(?:to|-|–)\s*\$?([\d,]+(?:\.\d+)?)",
    re.IGNORECASE,
)

_FISCAL_YEAR_PATTERN = re.compile(
    r"(?:fiscal\s+(?:year\s+)?|full[- ]year\s+|FY\s*)(\d{4})", re.IGNORECASE
)
_FISCAL_QUARTER_PATTERN = re.compile(
    r"\b(first|second|third|fourth)\s+quarter\b|\bQ([1-4])\b", re.IGNORECASE
)
_QUARTER_WORD_MAP = {"first": 1, "second": 2, "third": 3, "fourth": 4}

_UNIT_MULTIPLIER = {"billion": 1_000_000_000.0, "million": 1_000_000.0}

_RAISED_WORDS = ("raised", "raising", "increased", "increasing", "boosted", "boosting")
_LOWERED_WORDS = ("lowered", "lowering", "reduced", "reducing", "cut", "cutting")
_MAINTAINED_WORDS = (
    "reaffirm", "reaffirmed", "reaffirming", "maintain", "maintained",
    "maintaining", "unchanged",
)
_WITHDRAWN_WORDS = ("withdraw", "withdrew", "withdrawn", "suspend", "suspended", "suspending")
_PRIOR_CONTEXT_PHRASES = (
    "prior guidance", "previous guidance", "previously guided",
    "prior outlook", "previous outlook",
)


def _parse_amount(raw: str) -> float:
    return float(raw.replace(",", ""))


def _detect_guidance_type(text: str) -> str:
    """Classify guidance direction from surrounding language.

    Best-effort keyword classification, not a semantic reading of the
    filing. If a "prior guidance" context phrase is present but none of the
    explicit direction verbs are, we default to MAINTAINED (a revision is
    implied but no direction is stated) rather than guessing a direction;
    otherwise we treat it as an INITIAL guide with no prior context found.
    """
    lower = text.lower()
    if any(w in lower for w in _RAISED_WORDS):
        return "RAISED"
    if any(w in lower for w in _LOWERED_WORDS):
        return "LOWERED"
    if any(w in lower for w in _MAINTAINED_WORDS):
        return "MAINTAINED"
    if any(w in lower for w in _WITHDRAWN_WORDS):
        return "WITHDRAWN"
    if any(phrase in lower for phrase in _PRIOR_CONTEXT_PHRASES):
        return "MAINTAINED"
    return "INITIAL"


def _extract_fiscal_period(text: str, filing_date: date) -> tuple[int, int | None]:
    """Best-effort (fiscal_year, fiscal_quarter) extraction from guidance text.

    Falls back to the 8-K filing year when no explicit "fiscal <year>" /
    "full-year <year>" phrase is found — a heuristic, since guidance issued
    late in a fiscal year often targets the *next* fiscal year and free-text
    regex extraction cannot reliably disambiguate that from context alone.
    """
    year_match = _FISCAL_YEAR_PATTERN.search(text)
    fiscal_year = int(year_match.group(1)) if year_match else filing_date.year

    quarter_match = _FISCAL_QUARTER_PATTERN.search(text)
    fiscal_quarter = None
    if quarter_match:
        if quarter_match.group(1):
            fiscal_quarter = _QUARTER_WORD_MAP.get(quarter_match.group(1).lower())
        elif quarter_match.group(2):
            fiscal_quarter = int(quarter_match.group(2))

    return fiscal_year, fiscal_quarter


def extract_guidance_figures(text: str) -> dict[str, Any] | None:
    """Regex-extract a (metric, low, high) guidance figure from filing text.

    Pure (no I/O) so it can be unit-tested directly. Returns ``None`` when no
    guidance language is found — callers must not fabricate a figure in that
    case.
    """
    metric_raw: str
    low: float
    high: float
    unit: str | None

    match = _GUIDANCE_RANGE_PATTERN.search(text)
    if match:
        metric_raw = match.group(1)
        unit = match.group(4)
        try:
            low = _parse_amount(match.group(2))
            high = _parse_amount(match.group(3))
        except ValueError:
            match = None

    if not match:
        point_match = _GUIDANCE_POINT_PATTERN.search(text)
        if not point_match:
            return None
        metric_raw = point_match.group(1)
        unit = point_match.group(3)
        try:
            low = high = _parse_amount(point_match.group(2))
        except ValueError:
            return None

    multiplier = _UNIT_MULTIPLIER.get((unit or "").lower(), 1.0)
    low *= multiplier
    high *= multiplier
    if low > high:
        low, high = high, low

    metric = "EPS" if metric_raw.lower() in ("eps", "earnings per share") else "REVENUE"

    prior_low = prior_high = None
    prior_match = _PRIOR_GUIDANCE_PATTERN.search(text)
    if prior_match:
        try:
            prior_low = _parse_amount(prior_match.group(1)) * multiplier
            prior_high = _parse_amount(prior_match.group(2)) * multiplier
        except ValueError:
            prior_low = prior_high = None

    return {
        "metric": metric,
        "guidance_low": low,
        "guidance_high": high,
        "guidance_midpoint": (low + high) / 2.0,
        "guidance_type": _detect_guidance_type(text),
        "prior_guidance_low": prior_low,
        "prior_guidance_high": prior_high,
    }


class GuidanceExtractionConnector(BaseConnector):
    """Extract forward guidance from SEC EDGAR 8-K Item 2.02 filings."""

    name = "SEC EDGAR Guidance Extraction"
    connector_type = "BATCH_API"
    data_domain = "ESTIMATES"

    def __init__(self, ciks: list[str] | None = None, days_back: int = 30):
        self.ciks = ciks or []
        self.days_back = days_back
        self.rate_limiter = RateLimiter(max_requests=settings.SEC_RATE_LIMIT, per_seconds=1.0)
        self.headers = {"User-Agent": settings.SEC_USER_AGENT}
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(headers=self.headers, timeout=30.0)
        return self._client

    async def _fetch_submissions(self, cik: str) -> dict[str, Any] | None:
        url = SUBMISSIONS_URL.format(cik=cik.zfill(10))
        await self.rate_limiter.acquire()
        client = await self._get_client()
        try:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:  # pragma: no cover - network
            logger.warning("[%s] failed to fetch submissions for CIK %s: %s", self.name, cik, exc)
            return None

    async def _fetch_document_body(self, doc_url: str) -> str | None:
        await self.rate_limiter.acquire()
        client = await self._get_client()
        try:
            resp = await client.get(doc_url)
            resp.raise_for_status()
            return resp.text
        except Exception as exc:  # pragma: no cover - network
            logger.warning("[%s] failed to fetch document body %s: %s", self.name, doc_url, exc)
            return None

    @staticmethod
    def _extract_item_202_filings(submissions: dict[str, Any], cik: str) -> list[dict[str, Any]]:
        """Extract 8-K filings with Item 2.02 from submissions JSON. Pure (no I/O).

        Mirrors ``Edgar8KConnector._extract_8k_filings``'s field layout and
        document-URL construction exactly.
        """
        recent = submissions.get("filings", {}).get("recent", {})
        if not recent:
            return []

        forms = recent.get("form", [])
        accession_numbers = recent.get("accessionNumber", [])
        filing_dates = recent.get("filingDate", [])
        primary_docs = recent.get("primaryDocument", [])
        items_list = recent.get("items", [])
        entity_name = submissions.get("name", "")

        out: list[dict[str, Any]] = []
        for i, form in enumerate(forms):
            if form not in ("8-K", "8-K/A"):
                continue
            items_raw = items_list[i] if i < len(items_list) else ""
            items = [item.strip() for item in items_raw.split(",") if item.strip()]
            if ITEM_202 not in items:
                continue

            accession = accession_numbers[i] if i < len(accession_numbers) else ""
            filed = filing_dates[i] if i < len(filing_dates) else ""
            primary_doc = primary_docs[i] if i < len(primary_docs) else ""
            accession_clean = accession.replace("-", "")
            doc_url = (
                f"https://www.sec.gov/Archives/edgar/data/"
                f"{cik.lstrip('0')}/{accession_clean}/{primary_doc}"
            )

            out.append(
                {
                    "cik": cik,
                    "entity_name": entity_name,
                    "accession_number": accession,
                    "filing_date": filed,
                    "document_url": doc_url,
                }
            )
        return out

    async def extract(self) -> list[dict[str, Any]]:
        if not self.ciks:
            logger.warning("[%s] no CIKs configured — skipping extraction", self.name)
            return []

        cutoff = date.today() - timedelta(days=self.days_back)
        records: list[dict[str, Any]] = []

        for cik in self.ciks:
            submissions = await self._fetch_submissions(cik)
            if submissions is None:
                continue

            filings = self._extract_item_202_filings(submissions, cik)
            for filing in filings:
                try:
                    if date.fromisoformat(filing["filing_date"]) < cutoff:
                        continue
                except (ValueError, TypeError):
                    continue

                body = await self._fetch_document_body(filing["document_url"])
                records.append({**filing, "body": body})

            logger.info(
                "[%s] CIK %s — %d Item 2.02 8-K filings in last %d days",
                self.name, cik, len(filings), self.days_back,
            )

        return records

    async def validate(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Drop filings where the document fetch failed or the body is too short."""
        valid: list[dict[str, Any]] = []
        for r in records:
            if not r.get("cik") or not r.get("filing_date"):
                continue
            body = r.get("body")
            if not body or len(body) < _MIN_BODY_LENGTH:
                logger.debug(
                    "[%s] skipping filing %s — body missing/too short to contain guidance",
                    self.name, r.get("accession_number"),
                )
                continue
            valid.append(r)
        return valid

    async def transform(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Regex-extract guidance figures from filing bodies. Pure (no I/O)."""
        out: list[dict[str, Any]] = []
        for r in records:
            text = r["body"]
            filing_date = date.fromisoformat(r["filing_date"])

            figures = extract_guidance_figures(text)
            if figures is None:
                # No parseable forward-guidance language — skip, don't fabricate.
                continue

            fiscal_year, fiscal_quarter = _extract_fiscal_period(text, filing_date)

            out.append(
                {
                    "cik": r["cik"],
                    "guidance_fiscal_year": fiscal_year,
                    "guidance_fiscal_quarter": fiscal_quarter,
                    "metric": figures["metric"],
                    "guidance_low": figures["guidance_low"],
                    "guidance_high": figures["guidance_high"],
                    "guidance_midpoint": figures["guidance_midpoint"],
                    "guidance_date": filing_date,
                    "guidance_type": figures["guidance_type"],
                    "prior_guidance_low": figures["prior_guidance_low"],
                    "prior_guidance_high": figures["prior_guidance_high"],
                    # Not derivable from the 8-K text itself — would require
                    # joining against a consensus-estimate source, which this
                    # connector deliberately does not do (no fabrication).
                    "consensus_at_guidance_date": None,
                    "guidance_vs_consensus": None,
                    # Stashed only for the optional AI augmentation pass in
                    # resolve(); stripped before load() ever sees the record.
                    "_raw_text": text,
                }
            )
        logger.info("[%s] transformed %d guidance rows", self.name, len(out))
        return out

    async def resolve(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Optional best-effort AI augmentation via Claude (see module docstring).

        No-ops (aside from stripping the stashed raw text) when
        ``ANTHROPIC_API_KEY`` isn't configured or the AI call fails —
        the regex-derived fields are always kept as the fallback.
        """
        from src.ai.client import get_ai_client

        client = get_ai_client()
        out: list[dict[str, Any]] = []
        for rec in records:
            text = rec.pop("_raw_text", None)
            if client.enabled and text:
                try:
                    ai_result = await self._ai_extract_guidance(client, text)
                    if ai_result:
                        rec.update(ai_result)
                except Exception as exc:  # pragma: no cover - best-effort AI path
                    logger.warning(
                        "[%s] AI guidance extraction failed for CIK %s, keeping regex result: %s",
                        self.name, rec.get("cik"), exc,
                    )
            out.append(rec)
        return out

    async def _ai_extract_guidance(self, client: Any, text: str) -> dict[str, Any] | None:
        """Structured guidance extraction via Claude — supplements, never
        replaces the ability of the regex pass to function on its own."""
        from pydantic import BaseModel

        class _GuidanceExtraction(BaseModel):
            metric: str
            guidance_low: float | None = None
            guidance_high: float | None = None
            guidance_type: str | None = None
            guidance_fiscal_year: int | None = None
            guidance_fiscal_quarter: int | None = None

        prompt = (
            "You are extracting forward financial guidance (revenue or EPS) from "
            "an SEC 8-K Item 2.02 press release. If the filing contains a forward "
            "guidance range or point figure, extract it. metric must be exactly "
            "'REVENUE' or 'EPS'. guidance_type must be exactly one of RAISED, "
            "LOWERED, MAINTAINED, WITHDRAWN, INITIAL. If no guidance is present, "
            "respond with your best null-filled guess rather than inventing figures.\n\n"
            f"{text[:8000]}"
        )
        result = await client.complete_structured(
            response_model=_GuidanceExtraction, user=prompt,
            tier="light", feature="guidance_extraction",
        )
        return {k: v for k, v in result.model_dump().items() if v is not None}

    async def load(
        self, records: list[dict[str, Any]], session: AsyncSession
    ) -> dict[str, int]:
        from src.models.earnings_intelligence import GuidanceTracking
        from src.models.entity import EntityIdentifier

        stats = {"inserted": 0, "updated": 0, "skipped": 0, "errors": 0}
        if getattr(self, "dry_run", False):
            return stats

        seen: set[tuple[Any, str, date]] = set()
        for rec in records:
            try:
                cik = rec["cik"]
                # Resolve entity_id from CIK — mirrors edgar_8k.py's lookup exactly.
                ident = (
                    await session.execute(
                        select(EntityIdentifier).where(
                            EntityIdentifier.identifier_type == "CIK",
                            EntityIdentifier.identifier_value == cik,
                        )
                    )
                ).scalar_one_or_none()
                if ident is None:
                    logger.info(
                        "[%s] skipping CIK %s — not resolvable to an existing "
                        "entity (no fabricated guidance row)",
                        self.name, cik,
                    )
                    stats["skipped"] += 1
                    continue
                entity_id = ident.entity_id

                dedupe_key = (entity_id, rec["metric"], rec["guidance_date"])
                if dedupe_key in seen:
                    stats["skipped"] += 1
                    continue
                seen.add(dedupe_key)

                fields = {k: v for k, v in rec.items() if k not in ("cik",) and not k.startswith("_")}

                existing = (
                    await session.execute(
                        select(GuidanceTracking).where(
                            GuidanceTracking.entity_id == entity_id,
                            GuidanceTracking.metric == fields["metric"],
                            GuidanceTracking.guidance_date == fields["guidance_date"],
                        )
                    )
                ).scalar_one_or_none()

                if existing:
                    for key, val in fields.items():
                        if val is not None:
                            setattr(existing, key, val)
                    stats["updated"] += 1
                else:
                    session.add(
                        GuidanceTracking(guidance_id=uuid.uuid4(), entity_id=entity_id, **fields)
                    )
                    stats["inserted"] += 1
            except Exception:  # pragma: no cover - defensive
                logger.exception("[%s] failed to load guidance row", self.name)
                stats["errors"] += 1

        await session.flush()
        return stats

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None
