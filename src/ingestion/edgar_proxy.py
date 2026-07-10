"""SEC EDGAR DEF 14A (proxy statement) governance connector.

Populates the Pillar 3 governance-intelligence read models from SEC EDGAR
DEF 14A filings (free, keyless — descriptive User-Agent header only, exactly
like ``edgar_8k`` / ``edgar_xbrl`` / ``edgar_executives``).

Feasibility (be honest about what this connector can and cannot do — DEF 14A
bodies are unstructured HTML, so full extraction is fragile NLP):

* ``proxy_filings``            — RELIABLE. One row per DEF 14A discovered from
                                 the CIK submissions index. Never fabricated.
* ``executive_compensation``  — BEST-EFFORT. Heuristic parse of the "Summary
                                 Compensation Table". Yields rows on filings
                                 whose comp table is clean HTML; empty (not
                                 fabricated) otherwise.
* ``board_members``           — BEST-EFFORT. Director nominee names scraped
                                 from the director-election section.
* ``shareholder_proposals``   — BEST-EFFORT. "Proposal No. N — <title>"
                                 headings from the proxy body.

No numeric value is ever invented: a field is populated only when parsed from
the document, else left NULL. The models carry no confidence/quality column,
so provenance is conveyed purely by NULLs + this module's honest reporting.

The pure parse helpers (``parse_*``) do no I/O and are directly unit-testable.
"""

from __future__ import annotations

import logging
import re
import uuid
from datetime import date
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.ingestion.base import BaseConnector
from src.ingestion.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)

SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
ARCHIVES_BASE_URL = "https://www.sec.gov/Archives/edgar/data"

# Definitive proxy statement form types (exclude DEFA14A additional soliciting
# material and preliminary PRE 14A — we want the definitive proxy).
PROXY_FORMS = ("DEF 14A", "DEFR14A")

# Comp-table header keywords -> canonical field name.
_COMP_COLUMN_KEYWORDS: list[tuple[str, str]] = [
    ("salary", "base_salary"),
    ("bonus", "bonus"),
    ("stock award", "stock_awards"),
    ("option award", "option_awards"),
    ("non-equity", "non_equity_incentive"),
    ("nonequity", "non_equity_incentive"),
    ("pension", "change_in_pension"),
    ("all other", "other_compensation"),
    ("total", "total_compensation"),
]

# Ordered most-specific first so "Chief Financial Officer" wins over a bare
# "President" appearing in "Senior Vice President, Chief Financial Officer".
_ROLE_KEYWORDS = [
    ("chief executive", "CEO"),
    ("chief financial", "CFO"),
    ("chief operating", "COO"),
    ("general counsel", "General Counsel"),
    ("chief", "Executive"),
    ("chairman", "Chairman"),
    ("president", "President"),
    ("treasurer", "Treasurer"),
    ("secretary", "Secretary"),
]

# Tokens that begin a title (used to split the name off the title in a
# Summary-Comp name cell like "Kevan Parekh Senior Vice President, CFO").
_TITLE_START = (
    "chief ", "president", "senior vice", "executive vice", "vice president",
    "senior ", "general counsel", "chairman", "chair ", "director of",
    "head of", "evp", "svp", "treasurer", "secretary",
)


# --------------------------------------------------------------------------- #
# HTML helpers (stdlib only — no bs4/lxml available in this environment)
# --------------------------------------------------------------------------- #
class _TableExtractor(HTMLParser):
    """Collect every ``<table>`` as a list of rows, each a list of cell text."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tables: list[list[list[str]]] = []
        self._cur_table: list[list[str]] | None = None
        self._cur_row: list[str] | None = None
        self._cur_cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: Any) -> None:
        if tag == "table":
            self._cur_table = []
        elif tag == "tr" and self._cur_table is not None:
            self._cur_row = []
        elif tag in ("td", "th") and self._cur_row is not None:
            self._cur_cell = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "table" and self._cur_table is not None:
            self.tables.append(self._cur_table)
            self._cur_table = None
        elif tag == "tr" and self._cur_row is not None:
            self._cur_table.append(self._cur_row)  # type: ignore[union-attr]
            self._cur_row = None
        elif tag in ("td", "th") and self._cur_cell is not None:
            text = " ".join("".join(self._cur_cell).split())
            self._cur_row.append(text)  # type: ignore[union-attr]
            self._cur_cell = None

    def handle_data(self, data: str) -> None:
        if self._cur_cell is not None:
            self._cur_cell.append(data)


def _strip_tags(html: str) -> str:
    """Return whitespace-collapsed plain text from an HTML document."""
    text_parts: list[str] = []

    class _T(HTMLParser):
        def handle_data(self, data: str) -> None:
            text_parts.append(data)

    parser = _T(convert_charrefs=True)
    try:
        parser.feed(html)
    except Exception:  # pragma: no cover - malformed HTML
        pass
    return " ".join("".join(text_parts).split())


def _extract_tables(html: str) -> list[list[list[str]]]:
    parser = _TableExtractor()
    try:
        parser.feed(html)
    except Exception:  # pragma: no cover - malformed HTML
        pass
    return parser.tables


_MONEY_RE = re.compile(r"-?\$?\s*([\d,]+(?:\.\d+)?)")


def _parse_money(cell: str) -> Decimal | None:
    """Parse a currency cell (``$1,234,567`` / ``1,234``) to Decimal, else None."""
    if not cell:
        return None
    cell = cell.strip()
    if cell in ("", "—", "-", "–", "N/A", "n/a", "*"):
        return None
    m = _MONEY_RE.search(cell.replace("\xa0", " "))
    if not m:
        return None
    try:
        return Decimal(m.group(1).replace(",", ""))
    except (InvalidOperation, ValueError):
        return None


# --------------------------------------------------------------------------- #
# Pure parse helpers (no I/O — unit-testable)
# --------------------------------------------------------------------------- #
_MEETING_RE = re.compile(
    r"annual meeting[^.]{0,120}?"
    r"(?:on|held on|to be held on|will be held on)\s+"
    r"([A-Z][a-z]+\s+\d{1,2},\s+\d{4})",
    re.IGNORECASE,
)
_MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11,
    "december": 12,
}


def parse_meeting_date(html: str) -> date | None:
    """Best-effort extraction of the annual-meeting date from the proxy body."""
    text = _strip_tags(html)
    m = _MEETING_RE.search(text)
    if not m:
        return None
    return _parse_us_date(m.group(1))


def _parse_us_date(raw: str) -> date | None:
    m = re.match(r"([A-Za-z]+)\s+(\d{1,2}),\s+(\d{4})", raw.strip())
    if not m:
        return None
    month = _MONTHS.get(m.group(1).lower())
    if not month:
        return None
    try:
        return date(int(m.group(3)), month, int(m.group(2)))
    except ValueError:
        return None


def _classify_role(text: str) -> str | None:
    low = text.lower()
    for kw, role in _ROLE_KEYWORDS:
        if kw in low:
            return role
    return None


def _split_name_role(raw: str) -> tuple[str, str]:
    """Summary-comp name cells often read "Tim Cook Chief Executive Officer".

    Cut the person's name at the first title keyword so ``person_name`` holds
    just the name and ``role`` holds the classified title. Falls back to the
    full string + "NEO" when no title keyword is present.
    """
    raw = re.sub(r"\s+", " ", raw).strip()
    low = raw.lower()
    cut = len(raw)
    for kw in _TITLE_START:
        idx = low.find(kw)
        if idx > 0:
            cut = min(cut, idx)
    name = raw[:cut].strip(" ,;-")
    name = re.sub(r"\s+(Former|Interim|Outgoing)$", "", name, flags=re.IGNORECASE)
    title_part = raw[cut:]
    role = _classify_role(title_part) or _classify_role(raw) or "NEO"
    return (name or raw)[:200], role


def parse_summary_comp_table(html: str) -> list[dict[str, Any]]:
    """Best-effort parse of the DEF 14A "Summary Compensation Table".

    Returns a list of ``{person_name, role, fiscal_year, <money fields>}``
    dicts. Empty list when no recognisable comp table is found — never
    fabricates values.
    """
    tables = _extract_tables(html)
    out: list[dict[str, Any]] = []

    for table in tables:
        if len(table) < 2:
            continue
        # Locate a header row (within the first 4 rows) that looks like a
        # Summary Compensation Table header: has Salary + Total columns.
        header_idx = None
        col_map: dict[int, str] = {}
        for r in range(min(4, len(table))):
            row = table[r]
            joined = " ".join(row).lower()
            if "salary" in joined and "total" in joined:
                for ci, cell in enumerate(row):
                    cl = cell.lower()
                    for kw, field in _COMP_COLUMN_KEYWORDS:
                        if kw in cl and ci not in col_map:
                            col_map[ci] = field
                            break
                header_idx = r
                break
        if header_idx is None or "total_compensation" not in col_map.values():
            continue

        # Year column: a numeric header cell or a column whose body is 4-digit
        # years. Find by scanning data rows for a 4-digit year.
        last_name: str | None = None
        for row in table[header_idx + 1:]:
            if not any(c.strip() for c in row):
                continue
            name_cell = row[0].strip() if row else ""
            # Name persists across the exec's multiple year rows.
            if name_cell and not re.fullmatch(r"[\d,.\s$()%-]+", name_cell):
                last_name = name_cell
            if not last_name:
                continue

            # Find a fiscal year anywhere in the row.
            year = None
            for cell in row:
                ym = re.fullmatch(r"(19|20)\d{2}", cell.strip())
                if ym:
                    year = int(cell.strip())
                    break
            if year is None:
                continue

            clean_name, role = _split_name_role(last_name)
            rec: dict[str, Any] = {
                "person_name": clean_name,
                "role": role,
                "fiscal_year": year,
            }
            got_money = False
            for ci, field in col_map.items():
                if ci < len(row):
                    val = _parse_money(row[ci])
                    if val is not None:
                        rec[field] = val
                        got_money = True
            # Only keep rows that actually carried a total or salary figure.
            if got_money and rec.get("total_compensation") is not None:
                out.append(rec)

        if out:
            break  # first plausible comp table wins

    # De-dup by (name, year).
    seen: set[tuple[str, int]] = set()
    deduped = []
    for rec in out:
        key = (rec["person_name"].lower(), rec["fiscal_year"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(rec)
    return deduped


_PROPOSAL_RE = re.compile(
    r"proposal\s+(?:no\.?\s*)?(\d{1,2})\s*[:\-—–]\s*([A-Z][^\n.]{5,150})",
    re.IGNORECASE,
)


def parse_shareholder_proposals(html: str) -> list[dict[str, Any]]:
    """Best-effort extraction of ``Proposal No. N — <title>`` headings."""
    text = _strip_tags(html)
    out: list[dict[str, Any]] = []
    seen: set[int] = set()
    for m in _PROPOSAL_RE.finditer(text):
        num = int(m.group(1))
        if num in seen or num > 20:
            continue
        seen.add(num)
        title = re.sub(r"\s+", " ", m.group(2)).strip(" .:-—–")
        # Table-of-contents captures trail into a page number + the next
        # heading (e.g. "... 64 Proposal No"); cut at the first page-number
        # digit run or a repeated "Proposal" token.
        title = re.split(r"\s+\d{1,4}\b|\s+Proposal\b", title, maxsplit=1)[0]
        title = title.strip(" .:-—–")
        if len(title) < 4:
            continue
        out.append({"proposal_number": num, "description": title[:2000]})
    return sorted(out, key=lambda r: r["proposal_number"])


_DIRECTOR_SECTION_RE = re.compile(
    r"(election of directors|nominees for (?:election as )?director|"
    r"board of directors)",
    re.IGNORECASE,
)
# A plausible person name: "First Last" or "First M. Last".
_NAME_RE = re.compile(r"^[A-Z][a-z]+(?:\s+[A-Z]\.?)?(?:\s+[A-Z][a-z]+){1,2}$")


def parse_board_members(html: str) -> list[dict[str, Any]]:
    """Best-effort director-nominee name extraction.

    DEF 14A director-election sections are highly inconsistent HTML; this
    heuristic scans tables in/after a director section for a "name + age"
    style row. Returns names only (independence/committees not reliably
    machine-extractable → left at model defaults). Empty when nothing clean
    is found.
    """
    tables = _extract_tables(html)
    out: list[dict[str, Any]] = []
    seen: set[str] = set()

    for table in tables:
        if len(table) < 2:
            continue
        header = " ".join(table[0]).lower()
        # Director tables usually pair a Name column with Age / Director Since.
        if not ("name" in header and ("age" in header or "director since" in header)):
            continue
        for row in table[1:]:
            if not row:
                continue
            cand = row[0].strip()
            cand = re.sub(r"\s*\(.*?\)\s*", "", cand)  # drop "(1)" footnotes
            cand = re.sub(r"\s+", " ", cand).strip()
            if _NAME_RE.match(cand) and cand.lower() not in seen:
                seen.add(cand.lower())
                out.append({"person_name": cand[:200]})
    return out


# --------------------------------------------------------------------------- #
# Connector
# --------------------------------------------------------------------------- #
class EdgarProxyConnector(BaseConnector):
    """Ingest DEF 14A proxy governance data from SEC EDGAR."""

    name = "SEC EDGAR Proxy (DEF 14A)"
    connector_type = "BATCH_API"
    data_domain = "GOVERNANCE"

    def __init__(
        self,
        ciks: list[str] | None = None,
        max_filings_per_cik: int = 5,
        parse_bodies: bool = True,
        max_body_parse_per_cik: int = 2,
    ):
        """Initialise.

        Args:
            ciks: CIK numbers to ingest proxies for.
            max_filings_per_cik: cap on DEF 14A filings recorded per CIK
                (most recent first).
            parse_bodies: when True, download the proxy HTML for best-effort
                comp/board/proposal/meeting-date parsing. proxy_filings itself
                needs no body download.
            max_body_parse_per_cik: cap on how many filing bodies to download
                per CIK (body downloads are large — the summary index is not).
        """
        self.ciks = ciks or []
        self.max_filings_per_cik = max_filings_per_cik
        self.parse_bodies = parse_bodies
        self.max_body_parse_per_cik = max_body_parse_per_cik
        self.rate_limiter = RateLimiter(
            max_requests=settings.SEC_RATE_LIMIT, per_seconds=1.0
        )
        self.headers = {"User-Agent": settings.SEC_USER_AGENT}
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(headers=self.headers, timeout=45.0)
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
            logger.warning("Failed to fetch submissions for CIK %s: %s", cik, exc)
            return None

    async def _fetch_body(self, url: str) -> str | None:
        await self.rate_limiter.acquire()
        client = await self._get_client()
        try:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.text
        except Exception as exc:  # pragma: no cover - network
            logger.warning("Failed to fetch proxy body %s: %s", url, exc)
            return None

    @staticmethod
    def _discover_proxy_filings(
        submissions: dict[str, Any], cik: str
    ) -> list[dict[str, Any]]:
        """Extract DEF 14A filing metadata rows from the submissions JSON."""
        recent = submissions.get("filings", {}).get("recent", {})
        if not recent:
            return []
        forms = recent.get("form", [])
        accessions = recent.get("accessionNumber", [])
        filed = recent.get("filingDate", [])
        primary_docs = recent.get("primaryDocument", [])

        rows: list[dict[str, Any]] = []
        cik_num = cik.lstrip("0")
        for i, form in enumerate(forms):
            if form not in PROXY_FORMS:
                continue
            accession = accessions[i] if i < len(accessions) else ""
            filing_date = filed[i] if i < len(filed) else ""
            primary_doc = primary_docs[i] if i < len(primary_docs) else ""
            if not accession or not filing_date:
                continue
            accession_clean = accession.replace("-", "")
            doc_url = (
                f"{ARCHIVES_BASE_URL}/{cik_num}/{accession_clean}/{primary_doc}"
                if primary_doc
                else f"{ARCHIVES_BASE_URL}/{cik_num}/{accession_clean}/"
            )
            rows.append(
                {
                    "cik": cik,
                    "form": form,
                    "accession_number": accession,
                    "filing_date": filing_date,
                    "filing_url": doc_url,
                }
            )
        # Most recent first.
        rows.sort(key=lambda r: r["filing_date"], reverse=True)
        return rows

    async def extract(self) -> list[dict[str, Any]]:
        if not self.ciks:
            logger.warning("No CIKs configured — skipping proxy extraction")
            return []

        records: list[dict[str, Any]] = []
        for cik in self.ciks:
            submissions = await self._fetch_submissions(cik)
            if submissions is None:
                continue
            entity_name = submissions.get("name", "")
            proxy_rows = self._discover_proxy_filings(submissions, cik)[
                : self.max_filings_per_cik
            ]

            bodies_parsed = 0
            for row in proxy_rows:
                row["entity_name"] = entity_name
                if self.parse_bodies and bodies_parsed < self.max_body_parse_per_cik:
                    html = await self._fetch_body(row["filing_url"])
                    bodies_parsed += 1
                    if html:
                        row["meeting_date"] = parse_meeting_date(html)
                        row["compensation"] = parse_summary_comp_table(html)
                        row["board_members"] = parse_board_members(html)
                        row["proposals"] = parse_shareholder_proposals(html)
                records.append(row)

            logger.info(
                "  Proxy: CIK %s (%s) — %d DEF 14A filings (%d bodies parsed)",
                cik,
                entity_name,
                len(proxy_rows),
                bodies_parsed,
            )
        return records

    async def validate(
        self, records: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        valid = []
        for rec in records:
            if not rec.get("cik"):
                continue
            if not rec.get("accession_number"):
                continue
            if not rec.get("filing_date"):
                continue
            valid.append(rec)
        return valid

    async def transform(
        self, records: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Attach a derived fiscal_year (proxy filing calendar year)."""
        for rec in records:
            try:
                rec["fiscal_year"] = date.fromisoformat(rec["filing_date"]).year
            except (ValueError, TypeError):
                rec["fiscal_year"] = None
        return [r for r in records if r.get("fiscal_year")]

    async def load(
        self, records: list[dict[str, Any]], session: AsyncSession
    ) -> dict[str, int]:
        from src.models.entity import EntityIdentifier
        from src.models.governance_intelligence import (
            BoardMember,
            ExecutiveCompensation,
            ProxyFiling,
            ShareholderProposal,
        )

        stats = {
            "inserted": 0,
            "updated": 0,
            "skipped": 0,
            "errors": 0,
            "comp_rows": 0,
            "board_rows": 0,
            "proposal_rows": 0,
        }
        if getattr(self, "dry_run", False):
            return stats

        # Resolve/skip duplicate fiscal years within this batch (unique on
        # entity_id+fiscal_year); newest filing_date wins.
        records = sorted(records, key=lambda r: r["filing_date"], reverse=True)

        for rec in records:
            try:
                ident = (
                    await session.execute(
                        select(EntityIdentifier).where(
                            EntityIdentifier.identifier_type == "CIK",
                            EntityIdentifier.identifier_value == rec["cik"],
                        )
                    )
                ).scalar_one_or_none()
                if ident is None:
                    stats["skipped"] += 1
                    continue
                entity_id = ident.entity_id
                fiscal_year = rec["fiscal_year"]
                filing_date = date.fromisoformat(rec["filing_date"])

                proxy = (
                    await session.execute(
                        select(ProxyFiling).where(
                            ProxyFiling.entity_id == entity_id,
                            ProxyFiling.fiscal_year == fiscal_year,
                        )
                    )
                ).scalar_one_or_none()

                if proxy is None:
                    proxy = ProxyFiling(
                        id=uuid.uuid4(),
                        entity_id=entity_id,
                        fiscal_year=fiscal_year,
                        filing_date=filing_date,
                        meeting_date=rec.get("meeting_date"),
                        filing_accession_number=rec["accession_number"],
                        filing_url=rec.get("filing_url"),
                    )
                    session.add(proxy)
                    await session.flush()
                    stats["inserted"] += 1
                else:
                    # Backfill meeting date if newly parsed.
                    if proxy.meeting_date is None and rec.get("meeting_date"):
                        proxy.meeting_date = rec["meeting_date"]
                    stats["skipped"] += 1

                proxy_id = proxy.id

                # ---- best-effort child rows -----------------------------
                for comp in rec.get("compensation") or []:
                    exists = (
                        await session.execute(
                            select(ExecutiveCompensation).where(
                                ExecutiveCompensation.entity_id == entity_id,
                                ExecutiveCompensation.person_name
                                == comp["person_name"],
                                ExecutiveCompensation.fiscal_year
                                == comp["fiscal_year"],
                            )
                        )
                    ).scalar_one_or_none()
                    if exists is not None:
                        continue
                    session.add(
                        ExecutiveCompensation(
                            id=uuid.uuid4(),
                            proxy_id=proxy_id,
                            entity_id=entity_id,
                            person_name=comp["person_name"],
                            role=comp.get("role", "NEO")[:50],
                            fiscal_year=comp["fiscal_year"],
                            total_compensation=comp.get("total_compensation"),
                            base_salary=comp.get("base_salary"),
                            bonus=comp.get("bonus"),
                            stock_awards=comp.get("stock_awards"),
                            option_awards=comp.get("option_awards"),
                            non_equity_incentive=comp.get("non_equity_incentive"),
                            other_compensation=comp.get("other_compensation"),
                            change_in_pension=comp.get("change_in_pension"),
                        )
                    )
                    stats["comp_rows"] += 1

                for bm in rec.get("board_members") or []:
                    exists = (
                        await session.execute(
                            select(BoardMember).where(
                                BoardMember.entity_id == entity_id,
                                BoardMember.person_name == bm["person_name"],
                                BoardMember.proxy_id == proxy_id,
                            )
                        )
                    ).scalar_one_or_none()
                    if exists is not None:
                        continue
                    session.add(
                        BoardMember(
                            id=uuid.uuid4(),
                            proxy_id=proxy_id,
                            entity_id=entity_id,
                            person_name=bm["person_name"],
                        )
                    )
                    stats["board_rows"] += 1

                for prop in rec.get("proposals") or []:
                    exists = (
                        await session.execute(
                            select(ShareholderProposal).where(
                                ShareholderProposal.proxy_id == proxy_id,
                                ShareholderProposal.proposal_number
                                == prop["proposal_number"],
                            )
                        )
                    ).scalar_one_or_none()
                    if exists is not None:
                        continue
                    session.add(
                        ShareholderProposal(
                            id=uuid.uuid4(),
                            proxy_id=proxy_id,
                            entity_id=entity_id,
                            proposal_number=prop["proposal_number"],
                            description=prop.get("description"),
                        )
                    )
                    stats["proposal_rows"] += 1

            except Exception:  # pragma: no cover - defensive
                logger.exception("[%s] failed to load proxy row", self.name)
                stats["errors"] += 1

        await session.flush()
        return stats

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None
