"""Primary-market bond issuance ingestion connector.

Ingests new-issue (primary market) corporate bond deals into the
``BondIssuance`` table: pricing/spread dynamics, deal size, bookrunners.

FLAG — UNTESTED AGAINST LIVE DATA
----------------------------------
What's real: ``extract()`` queries SEC EDGAR's full-text search API
(``https://efts.sec.gov/LATEST/search-index``) for 424B2/424B3/424B5/FWP
filings (prospectus supplements and free-writing prospectuses — the SEC forms
that carry final bond pricing terms) per configured CIK within a
``days_back`` window, fetches each matching filing document, and regex-parses
the free-text body for coupon rate, maturity date, aggregate principal amount
and the joint book-running managers list. This mirrors the
"structured index for lifecycle events, free-text parsing for terms" pattern
that ``edgar_ipo.py``'s docstring flags as the un-implemented next step for
IPOs — implemented here for bond issuances. The pre-existing configurable
JSON feed path (``BOND_ISSUANCES_FEED_URL`` / ``--feed-url``, mirroring
``congress_trades.py``) is preserved as an optional override for a future
paid feed (Bloomberg new-issue monitor, Ipreo/IHS Markit, etc.) and takes
priority over the EDGAR path when configured.

What's unvalidated: this has never been run against a live EDGAR response.
The full-text search hit shape (``hits.hits[]._source`` fields, the
``_id`` = "accession:primary_doc" convention) and the regex extraction
patterns are built from documented/observed EDGAR conventions, not from a
live payload captured in this sandbox (outbound network access to
efts.sec.gov / sec.gov is blocked here). Regex-based extraction of pricing
terms from free-text legal prose is inherently imperfect — multi-tranche
deals, unusual phrasing, or tables that don't survive HTML-stripping can all
cause a field to be missed. Fields that cannot be confidently parsed are left
``None`` rather than guessed (see ``extract_pricing_terms()``). This needs a
live run against real EDGAR responses, spot-checked against a handful of
known bond deals, before being trusted for production use. Deals whose issuer
cannot be resolved to an existing entity are skipped — no issuance rows are
fabricated.
"""

from __future__ import annotations

import logging
import re
import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.ingestion.base import BaseConnector
from src.ingestion.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)

# SEC EDGAR full-text search API (undocumented but stable; powers the public
# https://www.sec.gov/cgi-bin/browse-edgar full-text search UI).
EDGAR_FULL_TEXT_SEARCH_URL = "https://efts.sec.gov/LATEST/search-index"
# Filing document URL, following the same convention as edgar_8k.py /
# edgar_credit_ratings.py: {cik-no-leading-zeros}/{accession-no-dashes}/{doc}.
EDGAR_FILING_DOC_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/{primary_doc}"

# Forms that carry final bond pricing terms: 424B2/424B3/424B5 are prospectus
# supplements filed once a registered offering prices; FWP (free-writing
# prospectus) is the term sheet often filed the same day for both registered
# and 144A deals.
BOND_PRICING_FORMS = ("424B2", "424B3", "424B5", "FWP")

_HTML_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(raw: str) -> str:
    """Cheap HTML-to-text so prospectus prose can be regex-scanned."""
    return _HTML_TAG_RE.sub(" ", raw)


# --- Free-text pricing-term extraction -------------------------------------
# These patterns target the conventional phrasing of a 424B/FWP pricing term
# sheet, e.g.:
#   "$750,000,000 aggregate principal amount of 5.250% Notes due July 15, 2035"
# They are intentionally conservative: a field is only populated when a
# reasonably unambiguous match is found. See extract_pricing_terms() below
# for the accuracy caveats.

_COUPON_RE = re.compile(r"(\d+\.\d+)\s*%\s+[Nn]otes\s+due")

_MONTH_NAMES = (
    "January|February|March|April|May|June|July|August|September|"
    "October|November|December"
)
# Full "due <Month> <Day>, <Year>" date — the only maturity form we trust
# enough to populate maturity_date. A bare "due 2035" (year only, extremely
# common) is deliberately NOT parsed into a fabricated Jan-1 date.
_MATURITY_DATE_RE = re.compile(
    rf"due\s+({_MONTH_NAMES})\s+(\d{{1,2}}),?\s+(\d{{4}})", re.IGNORECASE
)

# "$X,XXX,XXX,XXX aggregate principal amount" and the "$X million/billion
# aggregate principal amount" shorthand some FWPs use.
_PRINCIPAL_AMOUNT_RE = re.compile(
    r"\$\s*([\d,]+(?:\.\d+)?)\s*(million|billion)?\s+aggregate principal amount",
    re.IGNORECASE,
)

# Underwriter / bookrunner syndicate section header, e.g. "Joint Book-Running
# Managers" followed by a block of names up to the next blank line.
_BOOKRUNNERS_RE = re.compile(
    r"(?:Joint\s+)?Book-?Running\s+Managers?\s*[:\-]?\s*\n?(.+?)(?:\n\s*\n|\Z)",
    re.IGNORECASE | re.DOTALL,
)


def extract_pricing_terms(text: str) -> dict[str, Any]:
    """Best-effort regex extraction of bond pricing terms from a 424B/FWP body.

    ``text`` should already be HTML-stripped (see ``_strip_html``). Returns a
    dict with ``coupon_rate``, ``maturity_date`` (ISO string or None),
    ``announced_size_mm`` and ``all_bookrunners`` — all ``None``/absent when
    not confidently parsed.

    ACCURACY CAVEAT: this is free-text parsing of legal prose, not a
    structured feed. It has NOT been validated against a live filing. Known
    limitations:
      * Multi-tranche deals (e.g. a 5-year AND a 10-year note in one filing)
        are not disambiguated — only the first coupon/maturity match is used,
        which may be wrong for whichever tranche isn't first.
      * A maturity expressed only as a year ("Notes due 2035") is common and
        intentionally left unparsed rather than guessing a month/day.
      * Underwriter blocks rendered as HTML tables often don't survive
        ``_strip_html`` cleanly; the bookrunners list may be empty or noisy.
    Callers must not treat a populated field as ground truth without a human
    (or a stronger parser) checking it against the source filing.
    """
    result: dict[str, Any] = {
        "coupon_rate": None,
        "maturity_date": None,
        "announced_size_mm": None,
        "all_bookrunners": None,
    }

    coupon_match = _COUPON_RE.search(text)
    if coupon_match:
        result["coupon_rate"] = coupon_match.group(1)

    maturity_match = _MATURITY_DATE_RE.search(text)
    if maturity_match:
        month_name, day, year = maturity_match.groups()
        try:
            dt = datetime.strptime(f"{month_name} {day} {year}", "%B %d %Y")
            result["maturity_date"] = dt.date().isoformat()
        except ValueError:
            pass

    amount_match = _PRINCIPAL_AMOUNT_RE.search(text)
    if amount_match:
        raw_amount, unit = amount_match.groups()
        try:
            amount = Decimal(raw_amount.replace(",", ""))
            if unit and unit.lower() == "billion":
                amount_mm = amount * Decimal(1000)
            elif unit and unit.lower() == "million":
                amount_mm = amount
            else:
                # Bare dollar figure, e.g. "$750,000,000" -> convert to $mm.
                amount_mm = amount / Decimal(1_000_000)
            result["announced_size_mm"] = str(amount_mm)
        except (InvalidOperation, ValueError):
            pass

    bookrunners_match = _BOOKRUNNERS_RE.search(text)
    if bookrunners_match:
        raw_block = bookrunners_match.group(1)
        names = [n.strip() for n in re.split(r"\n|(?:\s{2,})", raw_block) if n.strip()]
        # Filter obviously-not-a-name noise (stray punctuation, page numbers).
        names = [n for n in names if 3 <= len(n) <= 80 and any(c.isalpha() for c in n)]
        if names:
            result["all_bookrunners"] = names

    return result


def _clean(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, str):
        v = value.strip()
        if v == "" or v.lower() in ("null", "none", "n/a"):
            return None
        return v
    return value


def _parse_date(value: Any) -> date | None:
    value = _clean(value)
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%Y%m%d"):
        try:
            return datetime.strptime(str(value), fmt).date()
        except ValueError:
            continue
    return None


def _parse_decimal(value: Any) -> Decimal | None:
    value = _clean(value)
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _parse_int(value: Any) -> int | None:
    value = _clean(value)
    if value is None:
        return None
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return None


def _parse_bool(value: Any) -> bool:
    value = _clean(value)
    return bool(value) and str(value).strip().lower() in ("y", "yes", "true", "1")


def normalize_issuance(row: dict[str, Any]) -> dict[str, Any] | None:
    """Normalize one raw new-issue row into a BondIssuance field dict (pure).

    ``issuer_cik`` / ``issuer_name`` are retained so the loader can resolve the
    (non-nullable) issuer entity FK. Returns ``None`` if the row lacks a
    pricing/announcement date entirely.
    """
    pricing_date = _parse_date(row.get("pricing_date"))
    announce_date = _parse_date(row.get("announcement_date"))
    if not pricing_date and not announce_date:
        return None

    talk_low = _parse_int(row.get("initial_talk_low_bps"))
    talk_high = _parse_int(row.get("initial_talk_high_bps"))
    final_spread = _parse_int(row.get("final_spread_bps"))
    tightening = _parse_int(row.get("tightening_bps"))
    # Derive tightening from talk midpoint → final if not supplied.
    if tightening is None and final_spread is not None and talk_low is not None:
        talk_mid = (talk_low + talk_high) / 2 if talk_high is not None else talk_low
        tightening = int(round(talk_mid - final_spread))

    bookrunners = row.get("all_bookrunners")
    if isinstance(bookrunners, str):
        bookrunners = [b.strip() for b in bookrunners.split(",") if b.strip()]
    elif not isinstance(bookrunners, list):
        bookrunners = None

    return {
        "issuer_cik": _clean(row.get("issuer_cik") or row.get("cik")),
        "issuer_name": _clean(row.get("issuer_name") or row.get("company_name")),
        "pricing_date": pricing_date,
        "settlement_date": _parse_date(row.get("settlement_date")),
        "announcement_date": announce_date,
        "coupon_rate": _parse_decimal(row.get("coupon_rate") or row.get("coupon")),
        "maturity_date": _parse_date(row.get("maturity_date")),
        "seniority": (_clean(row.get("seniority")) or None),
        "issue_price": _parse_decimal(row.get("issue_price")),
        "issue_yield": _parse_decimal(row.get("issue_yield")),
        "initial_talk_low_bps": talk_low,
        "initial_talk_high_bps": talk_high,
        "final_spread_bps": final_spread,
        "tightening_bps": tightening,
        "announced_size_mm": _parse_decimal(row.get("announced_size_mm")),
        "issued_size_mm": _parse_decimal(row.get("issued_size_mm")),
        "lead_left_bookrunner": _clean(row.get("lead_left_bookrunner")),
        "all_bookrunners": bookrunners,
        "use_of_proceeds": _clean(row.get("use_of_proceeds")),
        "currency": (_clean(row.get("currency")) or "USD")[:3],
        "is_benchmark": _parse_bool(row.get("is_benchmark")),
        "is_144a": _parse_bool(row.get("is_144a")),
        "is_registered": _parse_bool(row.get("is_registered")),
    }


class BondIssuancesConnector(BaseConnector):
    """Ingest primary-market bond issuances.

    Primary path: SEC EDGAR full-text search over 424B2/424B3/424B5/FWP
    filings for the configured CIKs, with free-text regex extraction of
    pricing terms from each matching filing document (see module docstring
    and ``extract_pricing_terms()``).

    Fallback path: a configurable JSON feed (``feed_url`` /
    ``BOND_ISSUANCES_FEED_URL``), preserved for a future paid data source
    (Bloomberg new-issue monitor, Ipreo/IHS Markit, etc.). If ``feed_url`` is
    set it takes priority over the EDGAR path.
    """

    name = "Bond Issuances"
    connector_type = "BATCH_API"
    data_domain = "FIXED_INCOME"

    def __init__(
        self,
        *,
        ciks: list[str] | None = None,
        days_back: int = 180,
        feed_url: str | None = None,
        api_key: str | None = None,
    ):
        self.ciks = ciks or []
        self.days_back = days_back
        self.feed_url = feed_url or getattr(settings, "BOND_ISSUANCES_FEED_URL", "")
        self.api_key = api_key or getattr(settings, "BOND_ISSUANCES_API_KEY", "")
        self.rate_limiter = RateLimiter(max_requests=settings.SEC_RATE_LIMIT, per_seconds=1.0)
        self.headers = {"User-Agent": settings.SEC_USER_AGENT}
        self._client: httpx.AsyncClient | None = None

    def auth_headers(self) -> dict[str, str]:
        headers = {"User-Agent": settings.SEC_USER_AGENT, "Accept": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(headers=self.headers, timeout=30.0)
        return self._client

    async def _search_filings(
        self, cik: str, start: date, end: date
    ) -> dict[str, Any] | None:
        """Query EDGAR full-text search for bond-pricing forms filed by ``cik``.

        NOTE: the full-text search API requires a non-empty ``q``. We use a
        phrase ("aggregate principal amount") that is near-universal in debt
        prospectuses/term sheets, combined with the ``forms``/``ciks``/
        ``dateRange`` filters to scope results to this issuer's bond filings.
        This is a heuristic, not a documented/guaranteed API contract — it
        has not been exercised against a live response in this sandbox.
        """
        params = {
            "q": '"aggregate principal amount"',
            "forms": ",".join(BOND_PRICING_FORMS),
            "dateRange": "custom",
            "startdt": start.isoformat(),
            "enddt": end.isoformat(),
            "ciks": cik.zfill(10),
        }
        await self.rate_limiter.acquire()
        client = await self._get_client()
        try:
            resp = await client.get(EDGAR_FULL_TEXT_SEARCH_URL, params=params)
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:  # pragma: no cover - network
            logger.warning(
                "[%s] full-text search failed for CIK %s: %s", self.name, cik, exc
            )
            return None

    @staticmethod
    def _parse_search_hits(data: dict[str, Any], cik: str) -> list[dict[str, Any]]:
        """Pure: map an EDGAR full-text search response to filing stubs.

        Expected shape (per EDGAR's public full-text search UI, inferred —
        not confirmed against a live payload):
            {"hits": {"hits": [
                {"_id": "<accession-with-dashes>:<primary-doc-filename>",
                 "_source": {"display_names": ["ISSUER INC (0000320193)"],
                             "form": "424B2", "file_date": "2024-05-01", ...}}
            ]}}
        """
        hits = ((data or {}).get("hits") or {}).get("hits") or []
        out: list[dict[str, Any]] = []
        for hit in hits:
            hit_id = hit.get("_id", "") or ""
            accession, _, primary_doc = hit_id.partition(":")
            if not accession or not primary_doc:
                continue
            source = hit.get("_source", {}) or {}
            display_names = source.get("display_names") or []
            issuer_name = None
            if display_names:
                # "ISSUER INC (0000320193)" -> "ISSUER INC"
                issuer_name = re.sub(r"\s*\(\d+\)\s*$", "", display_names[0]).strip()
            out.append(
                {
                    "cik": cik,
                    "issuer_name": issuer_name,
                    "form": source.get("form"),
                    "filing_date": source.get("file_date"),
                    "accession_number": accession,
                    "primary_doc": primary_doc,
                }
            )
        return out

    async def _fetch_filing_text(
        self, cik: str, accession: str, primary_doc: str
    ) -> str | None:
        accession_nodash = accession.replace("-", "")
        url = EDGAR_FILING_DOC_URL.format(
            cik=cik.lstrip("0") or cik,
            accession=accession_nodash,
            primary_doc=primary_doc,
        )
        await self.rate_limiter.acquire()
        client = await self._get_client()
        try:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.text
        except Exception as exc:  # pragma: no cover - network
            logger.warning("[%s] failed to fetch filing %s: %s", self.name, url, exc)
            return None

    async def _extract_from_edgar(self) -> list[dict[str, Any]]:
        end = date.today()
        start = end - timedelta(days=self.days_back)
        records: list[dict[str, Any]] = []
        for cik in self.ciks:
            data = await self._search_filings(cik, start, end)
            if not data:
                continue
            hits = self._parse_search_hits(data, cik)
            for hit in hits:
                text = await self._fetch_filing_text(
                    cik, hit["accession_number"], hit["primary_doc"]
                )
                if not text:
                    continue
                parsed = extract_pricing_terms(_strip_html(text))
                bookrunners = parsed.get("all_bookrunners")
                records.append(
                    {
                        "issuer_cik": cik,
                        "issuer_name": hit["issuer_name"],
                        "pricing_date": hit["filing_date"],
                        "coupon_rate": parsed.get("coupon_rate"),
                        "maturity_date": parsed.get("maturity_date"),
                        "announced_size_mm": parsed.get("announced_size_mm"),
                        "all_bookrunners": bookrunners,
                        "lead_left_bookrunner": bookrunners[0] if bookrunners else None,
                        "currency": "USD",
                        "form": hit["form"],
                        "accession_number": hit["accession_number"],
                    }
                )
            logger.info(
                "[%s] CIK %s — %d bond-pricing filings in last %d days",
                self.name, cik, len(hits), self.days_back,
            )
        return records

    async def _extract_from_feed(self) -> list[dict[str, Any]]:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.get(self.feed_url, headers=self.auth_headers())
            resp.raise_for_status()
            data = resp.json()
        records = data if isinstance(data, list) else data.get("issuances", data.get("data", []))
        logger.info("[%s] fetched %d raw rows from configured feed", self.name, len(records))
        return records

    async def extract(self) -> list[dict[str, Any]]:
        if self.feed_url:
            return await self._extract_from_feed()
        if not self.ciks:
            logger.warning(
                "[%s] no CIKs and no BOND_ISSUANCES_FEED_URL configured — "
                "skipping extraction",
                self.name,
            )
            return []
        return await self._extract_from_edgar()

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    async def validate(
        self, records: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        valid = []
        for r in records:
            has_issuer = _clean(r.get("issuer_cik") or r.get("cik") or r.get("issuer_name"))
            has_date = _parse_date(r.get("pricing_date")) or _parse_date(
                r.get("announcement_date")
            )
            if has_issuer and has_date:
                valid.append(r)
        return valid

    async def transform(
        self, records: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        out = []
        for r in records:
            norm = normalize_issuance(r)
            if norm:
                out.append(norm)
        logger.info("[%s] normalized %d issuances", self.name, len(out))
        return out

    async def load(
        self, records: list[dict[str, Any]], session: AsyncSession
    ) -> dict[str, int]:
        from src.models.bond_issuance import BondIssuance
        from src.models.entity import Entity, EntityIdentifier
        from src.models.fi_intelligence import NewIssuanceEvent

        counts = {"inserted": 0, "updated": 0, "skipped": 0, "errors": 0}
        if getattr(self, "dry_run", False):
            return counts

        for rec in records:
            try:
                # Resolve the (non-nullable) issuer entity — never fabricate one.
                issuer_entity_id = None
                cik = rec.pop("issuer_cik", None)
                issuer_name = rec.pop("issuer_name", None)
                if cik:
                    issuer_entity_id = (
                        await session.execute(
                            select(EntityIdentifier.entity_id).where(
                                EntityIdentifier.identifier_type == "CIK",
                                EntityIdentifier.identifier_value == str(cik),
                            )
                        )
                    ).scalar_one_or_none()
                if issuer_entity_id is None and issuer_name:
                    issuer_entity_id = (
                        await session.execute(
                            select(Entity.entity_id).where(
                                Entity.legal_name == issuer_name
                            )
                        )
                    ).scalar_one_or_none()
                if issuer_entity_id is None:
                    logger.info(
                        "[%s] skipping issuance — issuer '%s' not resolvable to an "
                        "existing entity (no fabricated row created)",
                        self.name,
                        issuer_name or cik,
                    )
                    counts["skipped"] += 1
                    continue

                # De-dupe on (issuer, pricing_date, maturity_date).
                existing = (
                    await session.execute(
                        select(BondIssuance).where(
                            BondIssuance.issuer_entity_id == issuer_entity_id,
                            BondIssuance.pricing_date == rec["pricing_date"],
                            BondIssuance.maturity_date == rec["maturity_date"],
                        )
                    )
                ).scalar_one_or_none()
                if existing:
                    counts["skipped"] += 1
                    continue

                session.add(
                    BondIssuance(
                        issuance_id=uuid.uuid4(),
                        issuer_entity_id=issuer_entity_id,
                        **rec,
                    )
                )
                counts["inserted"] += 1

                # Also feed the Pillar 3 FI Intelligence dashboard's
                # NewIssuanceEvent table (src/api/routers/fi_intelligence.py
                # /fi/issuance/*), which previously had zero producers. Same
                # underlying real EDGAR-extracted deal, reshaped for that
                # table's narrower field set -- no new data invented.
                issue_date = rec["pricing_date"] or rec["announcement_date"]
                talk_low = rec["initial_talk_low_bps"]
                talk_high = rec["initial_talk_high_bps"]
                if talk_low is not None and talk_high is not None:
                    initial_talk_bps = Decimal(talk_low + talk_high) / 2
                elif talk_low is not None:
                    initial_talk_bps = Decimal(talk_low)
                else:
                    initial_talk_bps = None
                existing_event = (
                    await session.execute(
                        select(NewIssuanceEvent).where(
                            NewIssuanceEvent.entity_id == issuer_entity_id,
                            NewIssuanceEvent.issue_date == issue_date,
                            NewIssuanceEvent.maturity_date == rec["maturity_date"],
                        )
                    )
                ).scalar_one_or_none()
                if not existing_event:
                    session.add(
                        NewIssuanceEvent(
                            id=uuid.uuid4(),
                            entity_id=issuer_entity_id,
                            issue_date=issue_date,
                            coupon_rate=rec["coupon_rate"],
                            maturity_date=rec["maturity_date"],
                            size_mm=rec["issued_size_mm"] or rec["announced_size_mm"],
                            spread_at_issue_bps=(
                                Decimal(rec["final_spread_bps"])
                                if rec["final_spread_bps"] is not None
                                else None
                            ),
                            initial_talk_bps=initial_talk_bps,
                            use_of_proceeds=rec["use_of_proceeds"],
                        )
                    )
            except Exception:  # pragma: no cover - defensive
                logger.exception("[%s] failed to load issuance", self.name)
                counts["errors"] += 1
        await session.flush()
        return counts
