"""EDGAR Filing Diff connector — section-level change detection (Pillar 3).

Resolves the DATA_WIRING_AUDIT.md §6 "FILING DIFF" open item. The audit flagged
this as blocked because "no full filing text is stored to diff", but full text does
not need to be persisted first: for each entity we discover its two most recent
same-type filings (default 10-K), fetch both filing documents transiently, split
them into major Item sections, and run the existing pure-computation diff engine
(``src/engines/filing_diff.py``) over each section pair.

Persistence:
- ``filing_sections`` — the extracted section text for BOTH filings (so the text is
  now actually stored, directly addressing the audit note) keyed by
  (entity_id, filing_type, fiscal_year, section_key).
- ``filing_diffs`` — one row per section that changed between the two filings,
  carrying paragraph add/remove/modify counts, a change classification, a change
  percentage and a materiality assessment.

Honest scope: this is a SECTION-LEVEL HEURISTIC diff, not a word-level legal
redline. Sections are matched by 10-K/10-Q Item headers via regex, and paragraph
alignment is a two-pass word-overlap similarity (Jaccard screen + overlap confirm).
It reliably surfaces "Risk Factors grew 18% with 4 substantive new paragraphs", not
an authoritative clause-by-clause markup.
"""

import logging
import uuid
from datetime import date
from decimal import Decimal
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.engines.filing_diff import compute_filing_diff, extract_sections
from src.ingestion.base import BaseConnector
from src.ingestion.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)

SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
FILING_DOC_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/{primary_doc}"

# Max characters of paragraph text kept per snippet in the JSONB columns, and max
# snippets stored per change bucket, so rows stay compact.
_SNIPPET_CHARS = 400
_MAX_SNIPPETS = 25


class EdgarFilingDiffConnector(BaseConnector):
    """Diff an entity's two most recent same-type filings, section by section."""

    name = "EDGAR Filing Diff"
    connector_type = "BATCH_API"
    data_domain = "FILINGS"

    def __init__(
        self,
        cik_list: list[str] | None = None,
        filing_type: str = "10-K",
    ) -> None:
        """Initialize the filing-diff connector.

        Args:
            cik_list: CIK numbers to process (unpadded strings, as stored in
                ``entity_identifiers``).
            filing_type: EDGAR form type to diff (e.g. "10-K" or "10-Q").
        """
        self.cik_list = cik_list or []
        self.filing_type = filing_type
        self.rate_limiter = RateLimiter(
            max_requests=settings.SEC_RATE_LIMIT, per_seconds=1.0
        )
        self.headers = {"User-Agent": settings.SEC_USER_AGENT}
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(headers=self.headers, timeout=60.0)
        return self._client

    async def _sec_get(self, url: str) -> httpx.Response:
        await self.rate_limiter.acquire()
        client = await self._get_client()
        resp = await client.get(url)
        resp.raise_for_status()
        return resp

    async def _recent_filings(self, cik: str) -> list[dict[str, Any]]:
        """Return the two most recent filings of ``self.filing_type`` for a CIK.

        Newest first. Each dict carries accession, primary document, filing date,
        report (period) date and a fully-formed document URL.
        """
        padded_cik = cik.zfill(10)
        url = SUBMISSIONS_URL.format(cik=padded_cik)
        try:
            resp = await self._sec_get(url)
            data = resp.json()
        except Exception as e:  # noqa: BLE001
            logger.error("Failed to fetch submissions for CIK %s: %s", cik, e)
            return []

        recent = data.get("filings", {}).get("recent", {})
        forms = recent.get("form", [])
        accessions = recent.get("accessionNumber", [])
        primary_docs = recent.get("primaryDocument", [])
        filing_dates = recent.get("filingDate", [])
        report_dates = recent.get("reportDate", [])

        filings: list[dict[str, Any]] = []
        for i, form in enumerate(forms):
            if form != self.filing_type:
                continue
            primary_doc = primary_docs[i] if i < len(primary_docs) else ""
            if not primary_doc:
                continue
            accession_clean = accessions[i].replace("-", "")
            report_date = report_dates[i] if i < len(report_dates) else ""
            filing_date = filing_dates[i] if i < len(filing_dates) else ""
            filings.append({
                "cik": cik,
                "accession_number": accessions[i],
                "primary_document": primary_doc,
                "filing_date": filing_date,
                "report_date": report_date,
                "fiscal_year": self._fiscal_year(report_date, filing_date),
                "url": FILING_DOC_URL.format(
                    cik=cik,
                    accession=accession_clean,
                    primary_doc=primary_doc,
                ),
            })
            if len(filings) >= 2:
                break

        return filings

    @staticmethod
    def _fiscal_year(report_date: str, filing_date: str) -> int | None:
        """Derive a fiscal year from the report (period) date, falling back to the
        filing date."""
        for candidate in (report_date, filing_date):
            if candidate and len(candidate) >= 4 and candidate[:4].isdigit():
                return int(candidate[:4])
        return None

    async def extract(self) -> list[dict[str, Any]]:
        """Fetch the two most recent same-type filings per CIK and extract sections."""
        if not self.cik_list:
            logger.warning("[%s] No CIK list provided — skipping", self.name)
            return []

        records: list[dict[str, Any]] = []
        for cik in self.cik_list:
            filings = await self._recent_filings(cik)
            if len(filings) < 2:
                logger.info(
                    "  [%s] CIK %s — only %d %s filing(s), need 2; skipping",
                    self.name, cik, len(filings), self.filing_type,
                )
                continue

            new_filing, old_filing = filings[0], filings[1]
            try:
                new_html = (await self._sec_get(new_filing["url"])).text
                old_html = (await self._sec_get(old_filing["url"])).text
            except Exception as e:  # noqa: BLE001
                logger.warning("Failed to fetch filing docs for CIK %s: %s", cik, e)
                continue

            new_sections = extract_sections(new_html, self.filing_type)
            old_sections = extract_sections(old_html, self.filing_type)
            if not new_sections or not old_sections:
                logger.info(
                    "  [%s] CIK %s — no sections extracted (new=%d old=%d); skipping",
                    self.name, cik, len(new_sections), len(old_sections),
                )
                continue

            records.append({
                "cik": cik,
                "filing_type": self.filing_type,
                "old_filing": {**old_filing, "sections": old_sections},
                "new_filing": {**new_filing, "sections": new_sections},
            })

        return records

    async def validate(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Keep records that have both filings, distinct fiscal years and sections."""
        valid: list[dict[str, Any]] = []
        for rec in records:
            old_f = rec.get("old_filing", {})
            new_f = rec.get("new_filing", {})
            if not old_f.get("sections") or not new_f.get("sections"):
                continue
            oy, ny = old_f.get("fiscal_year"), new_f.get("fiscal_year")
            if oy is None or ny is None:
                logger.debug("CIK %s — missing fiscal year; skipping", rec.get("cik"))
                continue
            if oy == ny:
                logger.debug("CIK %s — same fiscal year %s; skipping", rec.get("cik"), oy)
                continue
            valid.append(rec)
        return valid

    async def transform(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Run the section-diff engine and shape rows for both target tables."""
        transformed: list[dict[str, Any]] = []
        for rec in records:
            old_f, new_f = rec["old_filing"], rec["new_filing"]
            year_old, year_new = old_f["fiscal_year"], new_f["fiscal_year"]
            # Ensure old < new even if EDGAR ordering is unusual.
            if year_old > year_new:
                old_f, new_f = new_f, old_f
                year_old, year_new = year_new, year_old

            diff = compute_filing_diff(old_f["sections"], new_f["sections"])

            diff_rows: list[dict[str, Any]] = []
            for section_key, sd in diff.section_diffs.items():
                changed = sd.added_count + sd.removed_count + sd.modified_count
                if changed == 0:
                    continue  # only persist sections that actually changed
                diff_rows.append({
                    "section_key": section_key,
                    "year_old": year_old,
                    "year_new": year_new,
                    "change_pct": Decimal(str(sd.change_pct)),
                    "change_classification": sd.classification,
                    "substantive_change_count": sd.substantive_count,
                    "boilerplate_change_count": sd.boilerplate_count,
                    "numerical_change_count": sd.numerical_count,
                    "structural_change_count": sd.structural_count,
                    "added_paragraphs": self._snip_added(sd.added_paragraphs),
                    "removed_paragraphs": self._snip_added(sd.removed_paragraphs),
                    "modified_paragraphs": self._snip_modified(sd.modified_paragraphs),
                    "ai_summary": self._summarize(section_key, sd),
                    "materiality": sd.materiality,
                })

            # Whole sections that appeared / disappeared between filings.
            for section_key in diff.new_sections_added:
                diff_rows.append(self._structural_row(section_key, year_old, year_new, "ADDED"))
            for section_key in diff.sections_removed:
                diff_rows.append(self._structural_row(section_key, year_old, year_new, "REMOVED"))

            transformed.append({
                "cik": rec["cik"],
                "filing_type": rec["filing_type"],
                "old_filing": old_f,
                "new_filing": new_f,
                "diff_rows": diff_rows,
                "overall_materiality": diff.overall_materiality,
            })

        return transformed

    async def load(
        self, records: list[dict[str, Any]], session: AsyncSession
    ) -> dict[str, int]:
        """Persist filing_sections (both filings) and filing_diffs (changed sections)."""
        from src.models.entity import EntityIdentifier
        from src.models.filing_intelligence import FilingDiff, FilingSection

        stats = {"inserted": 0, "updated": 0, "skipped": 0, "errors": 0}

        for rec in records:
            cik = rec["cik"]
            try:
                result = await session.execute(
                    select(EntityIdentifier).where(
                        EntityIdentifier.identifier_type == "CIK",
                        EntityIdentifier.identifier_value == cik,
                    )
                )
                ident = result.scalar_one_or_none()
                if ident is None:
                    logger.info("No entity for CIK %s — skipping", cik)
                    stats["skipped"] += 1
                    continue
                entity_id = ident.entity_id

                filing_type = rec["filing_type"]
                # Persist section text for both filings (idempotent on the unique key).
                for filing in (rec["old_filing"], rec["new_filing"]):
                    await self._upsert_sections(
                        session, FilingSection, entity_id, filing_type, filing, stats
                    )

                # Persist per-section diffs.
                for row in rec["diff_rows"]:
                    await self._upsert_diff(session, FilingDiff, entity_id, row, stats)

                await session.flush()
            except Exception as e:  # noqa: BLE001
                logger.error("Error loading filing diff for CIK %s: %s", cik, e)
                stats["errors"] += 1

        await session.flush()
        return stats

    # ── persistence helpers ────────────────────────────────────────────────

    async def _upsert_sections(
        self, session: AsyncSession, FilingSection, entity_id, filing_type,
        filing: dict[str, Any], stats: dict[str, int],
    ) -> None:
        fiscal_year = filing["fiscal_year"]
        filing_date = self._to_date(filing.get("filing_date"))
        for section_key, text in filing["sections"].items():
            existing = await session.execute(
                select(FilingSection).where(
                    FilingSection.entity_id == entity_id,
                    FilingSection.filing_type == filing_type,
                    FilingSection.fiscal_year == fiscal_year,
                    FilingSection.section_key == section_key,
                )
            )
            row = existing.scalar_one_or_none()
            word_count = len(text.split())
            if row is None:
                session.add(FilingSection(
                    id=uuid.uuid4(),
                    entity_id=entity_id,
                    filing_type=filing_type,
                    filing_date=filing_date or date.today(),
                    fiscal_year=fiscal_year,
                    section_key=section_key,
                    section_text=text,
                    word_count=word_count,
                    filing_accession_number=filing.get("accession_number"),
                    filing_url=filing.get("url"),
                ))
                stats["inserted"] += 1
            else:
                row.section_text = text
                row.word_count = word_count
                row.filing_accession_number = filing.get("accession_number")
                row.filing_url = filing.get("url")
                stats["updated"] += 1

    async def _upsert_diff(
        self, session: AsyncSession, FilingDiff, entity_id,
        row: dict[str, Any], stats: dict[str, int],
    ) -> None:
        existing = await session.execute(
            select(FilingDiff).where(
                FilingDiff.entity_id == entity_id,
                FilingDiff.section_key == row["section_key"],
                FilingDiff.year_old == row["year_old"],
                FilingDiff.year_new == row["year_new"],
            )
        )
        diff = existing.scalar_one_or_none()
        if diff is None:
            session.add(FilingDiff(
                id=uuid.uuid4(),
                entity_id=entity_id,
                **row,
            ))
            stats["inserted"] += 1
        else:
            for field_name, value in row.items():
                setattr(diff, field_name, value)
            stats["updated"] += 1

    # ── shaping helpers ────────────────────────────────────────────────────

    def _structural_row(
        self, section_key: str, year_old: int, year_new: int, kind: str
    ) -> dict[str, Any]:
        added = [{"text": f"Section {kind.lower()} between filings"}] if kind == "ADDED" else None
        removed = [{"text": f"Section {kind.lower()} between filings"}] if kind == "REMOVED" else None
        return {
            "section_key": section_key,
            "year_old": year_old,
            "year_new": year_new,
            "change_pct": Decimal("100.00"),
            "change_classification": "STRUCTURAL",
            "substantive_change_count": 0,
            "boilerplate_change_count": 0,
            "numerical_change_count": 0,
            "structural_change_count": 1,
            "added_paragraphs": added,
            "removed_paragraphs": removed,
            "modified_paragraphs": None,
            "ai_summary": f"Section {section_key} was {kind} between the two filings.",
            "materiality": "HIGH",
        }

    @staticmethod
    def _snip_added(paragraphs: list[dict]) -> list[dict] | None:
        if not paragraphs:
            return None
        out = []
        for p in paragraphs[:_MAX_SNIPPETS]:
            out.append({
                "text": (p.get("text") or "")[:_SNIPPET_CHARS],
                "classification": p.get("classification"),
            })
        return out

    @staticmethod
    def _snip_modified(paragraphs: list[dict]) -> list[dict] | None:
        if not paragraphs:
            return None
        out = []
        for p in paragraphs[:_MAX_SNIPPETS]:
            out.append({
                "old_text": (p.get("old_text") or "")[:_SNIPPET_CHARS],
                "new_text": (p.get("new_text") or "")[:_SNIPPET_CHARS],
                "similarity": p.get("similarity"),
                "classification": p.get("classification"),
            })
        return out

    @staticmethod
    def _summarize(section_key: str, sd) -> str:
        return (
            f"{section_key}: {sd.change_pct:.1f}% of paragraphs changed "
            f"({sd.added_count} added, {sd.removed_count} removed, "
            f"{sd.modified_count} modified; {sd.substantive_count} substantive). "
            f"Classification={sd.classification}, materiality={sd.materiality}."
        )

    @staticmethod
    def _to_date(value: str | None) -> date | None:
        if not value:
            return None
        try:
            return date.fromisoformat(value)
        except (ValueError, TypeError):
            return None

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None
