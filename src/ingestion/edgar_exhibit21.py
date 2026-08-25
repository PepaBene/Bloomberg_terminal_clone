"""SEC EDGAR Exhibit 21 (subsidiaries list) connector.

Ingests the corporate org-tree / subsidiary list disclosed in a registrant's
most recent 10-K under Exhibit 21 ("Subsidiaries of the Registrant") into the
``Subsidiary`` table (src/models/subsidiary.py). Feeds
``complex_structure.analyze_subsidiary_tree()`` (src/engines/
complex_structure.py), which previously had no real data source anywhere in
the platform.

Pipeline, CIK-driven, following the ``edgar_8k`` / ``edgar_ipo`` submissions
pattern:

1. Fetch the submissions JSON for each CIK and find the most recent 10-K.
2. Fetch that filing's ``index.json`` (SEC's structured per-accession file
   listing at ``.../Archives/edgar/data/{cik}/{accession}/index.json``) and
   locate the Exhibit 21 document by a case-insensitive substring match on
   its name/type/description against "ex-21", "ex21", "exhibit21", or
   "subsidiaries" — exhibit filenames are not perfectly standardized, so a
   substring match is the reliable approach here, not an exact match.
3. Fetch that document and parse it. Since 2023, larger filers must submit
   Exhibit 21 as structured XML per SEC's amended Item 601(b)(21) rules; this
   connector tries a structured ``<subsidiary><name>...</name>
   <jurisdiction>...</jurisdiction><ownership>...</ownership></subsidiary>``
   parse first, and falls back to a plain HTML-table parser (two or three
   columns: Subsidiary Name | State/Jurisdiction of Incorporation |
   [optional Ownership %]) for the still-common free-text exhibits. Neither
   ``bs4`` nor ``lxml`` is a project dependency (checked pyproject.toml), so
   the HTML fallback strips tags with ``re`` rather than pulling in a new
   parsing library. Ownership % is left ``None`` when not disclosed — most
   EX-21 exhibits list only name + jurisdiction, and that is not fabricated
   here.

FLAG — UNTESTED AGAINST LIVE DATA
----------------------------------
This sandbox has no outbound network access to SEC EDGAR (egress to
external domains is blocked by policy), so the submissions fetch, the
index.json fetch, the document fetch, and the exhibit-locator heuristic in
this connector have never been exercised against a real EDGAR response.
The code is written to SEC EDGAR's documented, publicly-known shapes
(``data.sec.gov/submissions/CIK##########.json`` and the per-accession
``index.json`` directory listing) from training knowledge, and the pure
parsing functions (``_find_latest_10k``, ``_find_exhibit21_document``,
``_parse_xml_exhibit21``, ``_parse_html_table_exhibit21``) are unit-tested
against realistic hand-built fixtures of both the structured-XML and
plain-HTML-table exhibit styles — not against live payloads. In particular,
the XML tag names used for the post-2023 structured Exhibit 21 filings are
inferred (SEC's amended Item 601(b)(21) rule specifies the *requirement*,
not a single canonical schema visible to us here), and real filings' exact
element names, the completeness of the ``index.json`` "type"/"description"
fields, and the prevalence of edge-case table layouts (merged cells,
footnote markers, nested sub-subsidiaries) should all be validated against
live EDGAR data before this connector is trusted in production. No
subsidiary rows are fabricated: unresolvable CIKs are skipped and logged in
``load()``, and documents that fail to parse into any rows are logged and
skipped rather than guessed at.
"""

from __future__ import annotations

import html
import logging
import re
import uuid
from datetime import date
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.ingestion.base import BaseConnector
from src.ingestion.redis_rate_limiter import RedisRateLimiter

logger = logging.getLogger(__name__)

SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
INDEX_JSON_URL = (
    "https://www.sec.gov/Archives/edgar/data/{cik}/{accession_nodash}/index.json"
)
DOCUMENT_URL = (
    "https://www.sec.gov/Archives/edgar/data/{cik}/{accession_nodash}/{doc_name}"
)

# Case-insensitive substrings used to locate the Exhibit 21 document among a
# filing's other exhibits — naming isn't perfectly standardized across
# filers, so this is a deliberately loose match.
_EXHIBIT21_NEEDLES = ("ex-21", "ex21", "exhibit21", "subsidiaries")

_HEADER_NAME_HINTS = ("name",)
_HEADER_JURISDICTION_HINTS = ("jurisdiction", "state", "incorporation")


# ── Pure parsing helpers (no I/O — unit-tested directly) ────────────────


def _strip_tags(fragment: str) -> str:
    """Strip HTML/XML tags and collapse whitespace. Pure, regex-based."""
    text = re.sub(r"<[^>]+>", " ", fragment)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _parse_pct(fragment: str) -> float | None:
    text = _strip_tags(fragment).replace("%", "").strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _find_latest_10k(submissions: dict[str, Any], cik: str) -> dict[str, Any] | None:
    """Find the most recent 10-K filing entry from a submissions JSON. Pure."""
    recent = submissions.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    accessions = recent.get("accessionNumber", [])
    filed = recent.get("filingDate", [])

    best: dict[str, Any] | None = None
    for i, form in enumerate(forms):
        if form != "10-K":
            continue
        filing_date = filed[i] if i < len(filed) else ""
        if not filing_date:
            continue
        if best is None or filing_date > best["filing_date"]:
            best = {
                "cik": cik,
                "accession_number": accessions[i] if i < len(accessions) else "",
                "filing_date": filing_date,
            }
    return best


def _find_exhibit21_document(index_json: dict[str, Any]) -> str | None:
    """Locate the Exhibit 21 document name in a filing's index.json. Pure."""
    items = (index_json or {}).get("directory", {}).get("item", [])
    for item in items:
        name = str(item.get("name") or "").lower()
        doc_type = str(item.get("type") or "").lower()
        description = str(item.get("description") or "").lower()
        combined = f"{name} {doc_type} {description}"
        if any(needle in combined for needle in _EXHIBIT21_NEEDLES):
            return item.get("name")
    return None


def _parse_xml_exhibit21(content: str) -> list[dict[str, Any]]:
    """Parse a structured (post-2023 Item 601(b)(21)) EX-21 XML document.

    Looks for ``<subsidiary>`` blocks containing ``<name>``,
    ``<jurisdiction>`` and optional ``<ownership>`` child elements. Returns
    [] (not an exception) if the document doesn't look like this shape, so
    callers can fall back to the HTML-table parser.
    """
    if "<subsidiary" not in content.lower():
        return []

    rows: list[dict[str, Any]] = []
    for block in re.findall(
        r"<subsidiary\b[^>]*>(.*?)</subsidiary>", content, re.IGNORECASE | re.DOTALL
    ):
        name_m = re.search(r"<name\b[^>]*>(.*?)</name>", block, re.IGNORECASE | re.DOTALL)
        jur_m = re.search(
            r"<jurisdiction\b[^>]*>(.*?)</jurisdiction>", block, re.IGNORECASE | re.DOTALL
        )
        own_m = re.search(
            r"<ownership\b[^>]*>(.*?)</ownership>", block, re.IGNORECASE | re.DOTALL
        )
        name = _strip_tags(name_m.group(1)) if name_m else ""
        if not name:
            continue
        jurisdiction = _strip_tags(jur_m.group(1)) if jur_m else None
        ownership_pct = _parse_pct(own_m.group(1)) if own_m else None
        rows.append(
            {
                "name": name,
                "jurisdiction": jurisdiction or None,
                "ownership_pct": ownership_pct,
            }
        )
    return rows


def _parse_html_table_exhibit21(content: str) -> list[dict[str, Any]]:
    """Fallback parser for a plain HTML-table EX-21 (the common real-world case).

    Two or three columns: Subsidiary Name | State/Jurisdiction of
    Incorporation | [optional Ownership %]. No bs4/lxml dependency — tags
    are stripped with ``re``.
    """
    rows_out: list[dict[str, Any]] = []
    for row_html in re.findall(r"<tr\b[^>]*>(.*?)</tr>", content, re.IGNORECASE | re.DOTALL):
        cells = re.findall(r"<t[dh]\b[^>]*>(.*?)</t[dh]>", row_html, re.IGNORECASE | re.DOTALL)
        cell_texts = [_strip_tags(c) for c in cells]
        if not any(cell_texts):
            continue
        if len(cell_texts) < 2:
            continue

        first_lower = cell_texts[0].lower()
        second_lower = cell_texts[1].lower()
        is_header = any(h in first_lower for h in _HEADER_NAME_HINTS) and any(
            h in second_lower for h in _HEADER_JURISDICTION_HINTS
        )
        if is_header:
            continue

        name = cell_texts[0].strip()
        jurisdiction = cell_texts[1].strip() or None
        ownership_pct = _parse_pct(cell_texts[2]) if len(cell_texts) >= 3 else None
        if not name:
            continue
        rows_out.append(
            {"name": name, "jurisdiction": jurisdiction, "ownership_pct": ownership_pct}
        )
    return rows_out


def _parse_exhibit21_document(content: str) -> list[dict[str, Any]]:
    """Parse an EX-21 document body: structured XML first, HTML table fallback. Pure."""
    rows = _parse_xml_exhibit21(content)
    if rows:
        return rows
    return _parse_html_table_exhibit21(content)


class EdgarExhibit21Connector(BaseConnector):
    """Ingest subsidiary org-tree data from SEC EDGAR Exhibit 21 (10-K)."""

    name = "SEC EDGAR Exhibit 21"
    connector_type = "BATCH_API"
    data_domain = "RELATIONSHIPS"

    def __init__(self, ciks: list[str] | None = None):
        self.ciks = ciks or []
        self.rate_limiter = RedisRateLimiter(key="sec_edgar", max_requests=settings.SEC_RATE_LIMIT, per_seconds=1.0)
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

    async def _fetch_index(self, cik: str, accession: str) -> dict[str, Any] | None:
        accession_nodash = accession.replace("-", "")
        cik_nodash = cik.lstrip("0") or "0"
        url = INDEX_JSON_URL.format(cik=cik_nodash, accession_nodash=accession_nodash)
        await self.rate_limiter.acquire()
        client = await self._get_client()
        try:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:  # pragma: no cover - network
            logger.warning(
                "[%s] failed to fetch filing index for CIK %s accession %s: %s",
                self.name, cik, accession, exc,
            )
            return None

    async def _fetch_document(self, cik: str, accession: str, doc_name: str) -> str | None:
        accession_nodash = accession.replace("-", "")
        cik_nodash = cik.lstrip("0") or "0"
        url = DOCUMENT_URL.format(cik=cik_nodash, accession_nodash=accession_nodash, doc_name=doc_name)
        await self.rate_limiter.acquire()
        client = await self._get_client()
        try:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.text
        except Exception as exc:  # pragma: no cover - network
            logger.warning(
                "[%s] failed to fetch Exhibit 21 document %s for CIK %s: %s",
                self.name, doc_name, cik, exc,
            )
            return None

    async def extract(self) -> list[dict[str, Any]]:
        if not self.ciks:
            logger.warning("[%s] no CIKs configured — skipping extraction", self.name)
            return []

        records: list[dict[str, Any]] = []
        for cik in self.ciks:
            submissions = await self._fetch_submissions(cik)
            if submissions is None:
                continue

            filing = _find_latest_10k(submissions, cik)
            if filing is None or not filing.get("accession_number"):
                logger.info("[%s] no 10-K filing found for CIK %s", self.name, cik)
                continue

            index_json = await self._fetch_index(cik, filing["accession_number"])
            if index_json is None:
                continue

            doc_name = _find_exhibit21_document(index_json)
            if doc_name is None:
                logger.info(
                    "[%s] no Exhibit 21 document found in 10-K %s for CIK %s",
                    self.name, filing["accession_number"], cik,
                )
                continue

            content = await self._fetch_document(cik, filing["accession_number"], doc_name)
            if content is None:
                continue

            subs = _parse_exhibit21_document(content)
            if not subs:
                logger.info(
                    "[%s] Exhibit 21 document %s for CIK %s parsed to zero subsidiaries — skipping",
                    self.name, doc_name, cik,
                )
                continue

            for sub in subs:
                records.append(
                    {
                        "cik": cik,
                        "name": sub.get("name"),
                        "jurisdiction": sub.get("jurisdiction"),
                        "ownership_pct": sub.get("ownership_pct"),
                        "accession_number": filing["accession_number"],
                        "filing_date": filing["filing_date"],
                    }
                )
        return records

    async def validate(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [r for r in records if (r.get("name") or "").strip() and r.get("cik")]

    async def transform(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Map parsed EX-21 rows to Subsidiary field dicts. Pure (no I/O)."""
        out: list[dict[str, Any]] = []
        for r in records:
            name = (r.get("name") or "").strip()
            if not name:
                continue
            accession = r.get("accession_number") or ""
            out.append(
                {
                    "cik": r["cik"],
                    "name": name[:300],
                    "jurisdiction": (r.get("jurisdiction") or None),
                    "ownership_pct": r.get("ownership_pct"),
                    "source_filing_accession": accession[:25] or None,
                    "as_of_date": r.get("filing_date"),
                }
            )
        logger.info("[%s] transformed %d subsidiary rows", self.name, len(out))
        return out

    async def load(
        self, records: list[dict[str, Any]], session: AsyncSession
    ) -> dict[str, int]:
        from src.models.entity import EntityIdentifier
        from src.models.subsidiary import Subsidiary

        stats = {"inserted": 0, "updated": 0, "skipped": 0, "errors": 0}
        if getattr(self, "dry_run", False):
            return stats

        for rec in records:
            try:
                cik = rec.get("cik")
                name = rec.get("name")
                as_of_raw = rec.get("as_of_date")
                if not cik or not name or not as_of_raw:
                    stats["skipped"] += 1
                    continue

                ident = (
                    await session.execute(
                        select(EntityIdentifier).where(
                            EntityIdentifier.identifier_type == "CIK",
                            EntityIdentifier.identifier_value == cik,
                        )
                    )
                ).scalar_one_or_none()
                if ident is None:
                    # No entity resolvable for this CIK — do not fabricate a
                    # parent link, skip and log instead.
                    logger.info(
                        "[%s] no entity found for CIK %s — skipping subsidiary %r",
                        self.name, cik, name,
                    )
                    stats["skipped"] += 1
                    continue
                entity_id = ident.entity_id

                as_of_date = (
                    date.fromisoformat(as_of_raw) if isinstance(as_of_raw, str) else as_of_raw
                )

                existing = (
                    await session.execute(
                        select(Subsidiary).where(
                            Subsidiary.parent_entity_id == entity_id,
                            Subsidiary.name == name,
                            Subsidiary.as_of_date == as_of_date,
                        )
                    )
                ).scalar_one_or_none()

                if existing is not None:
                    existing.jurisdiction = rec.get("jurisdiction") or existing.jurisdiction
                    if rec.get("ownership_pct") is not None:
                        existing.ownership_pct = rec["ownership_pct"]
                    existing.source_filing_accession = (
                        rec.get("source_filing_accession") or existing.source_filing_accession
                    )
                    stats["updated"] += 1
                else:
                    session.add(
                        Subsidiary(
                            subsidiary_id=uuid.uuid4(),
                            parent_entity_id=entity_id,
                            name=name,
                            jurisdiction=rec.get("jurisdiction"),
                            ownership_pct=rec.get("ownership_pct"),
                            is_vie=False,
                            source_filing_accession=rec.get("source_filing_accession"),
                            as_of_date=as_of_date,
                        )
                    )
                    stats["inserted"] += 1
            except Exception:  # pragma: no cover - defensive
                logger.exception("[%s] failed to load subsidiary row", self.name)
                stats["errors"] += 1

        await session.flush()
        return stats

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None
