"""SEC EDGAR Schedule 13D / 13G connector for beneficial-ownership ingestion.

Ingests SC 13D / SC 13D/A (activist / control-intent 5%+ beneficial
ownership) and SC 13G / SC 13G/A (passive 5%+ beneficial ownership)
filings into ``BeneficialOwnershipFiling``.

FLAG — UNTESTED AGAINST LIVE DATA
----------------------------------
Unlike 13F/Form 4 (``edgar_13f.py`` / ``edgar_form4.py``), the reporting
person on a Schedule 13D/13G is frequently NOT a pre-existing covered
entity in ``entity_identifiers`` (an activist fund or individual has no
reason to already be in the entity master), so the usual "drive the
connector off a known CIK list" pattern doesn't discover new filers. This
connector instead sweeps SEC EDGAR's keyless daily form index
(``https://www.sec.gov/Archives/edgar/daily-index/...``) for the target
form types over a configured day window -- the same purpose-built,
no-search-query-required mechanism EDGAR itself has used since the 1990s
for "all filings of form X on day Y". For each matching filing it fetches
the full submission text and:

1. Parses the SGML ``<SEC-HEADER>`` block's ``SUBJECT COMPANY`` (issuer)
   and ``FILED BY`` (reporting person) sub-blocks -- a stable, decades-old
   EDGAR convention -- to reliably identify both parties regardless of
   which CIK the daily index happened to list the filing under.
2. Regex-extracts the standard SC 13D/13G cover-page figures (aggregate
   amount beneficially owned, percent of class, voting/dispositive power
   rows, type of reporting person) from the free-text/HTML body. This
   mirrors ``bond_issuances.py``'s ``extract_pricing_terms()`` pattern:
   label-anchored, conservative, ``None`` when not confidently matched --
   never guessed. Multi-filer joint statements are not disambiguated
   beyond the first ``FILED BY`` block, same caveat as the bond connector's
   first-tranche limitation.

This has never been run against a live EDGAR response (no outbound network
access in this sandbox). Both the daily-index column layout and the
SEC-HEADER block wording are long-stable public conventions, but they have
not been spot-checked against a live payload. Run with ``--dry-run
--limit 5`` first and compare a handful of rows against the source filings
before trusting this in production.
"""

from __future__ import annotations

import logging
import re
import uuid
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.ingestion.base import BaseConnector
from src.ingestion.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)

DAILY_INDEX_URL = (
    "https://www.sec.gov/Archives/edgar/daily-index/{year}/QTR{quarter}/form.{yyyymmdd}.idx"
)
ARCHIVES_ROOT = "https://www.sec.gov/Archives/"

SCHEDULE_13D_FORMS = ("SC 13D", "SC 13D/A")
SCHEDULE_13G_FORMS = ("SC 13G", "SC 13G/A")
ALL_SCHEDULE_13_FORMS = SCHEDULE_13D_FORMS + SCHEDULE_13G_FORMS

_HTML_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(raw: str) -> str:
    """Cheap HTML-to-text so cover-page prose can be regex-scanned."""
    return _HTML_TAG_RE.sub(" ", raw)


def _quarter_for(day: date) -> int:
    return (day.month - 1) // 3 + 1


def daily_index_url(day: date) -> str:
    """Pure: build the daily form-index URL for a given calendar day."""
    return DAILY_INDEX_URL.format(
        year=day.year, quarter=_quarter_for(day), yyyymmdd=day.strftime("%Y%m%d")
    )


def parse_daily_index(
    text: str, target_forms: tuple[str, ...] = ALL_SCHEDULE_13_FORMS
) -> list[dict[str, Any]]:
    """Parse a SEC EDGAR daily ``form.idx`` file into filing stubs. Pure (no I/O).

    The file is fixed-width text; column start offsets are read from the
    header row itself (``Form Type   Company Name ... CIK ... Date Filed
    File Name``) rather than hardcoded, since exact padding has drifted
    over EDGAR's history. Rows are kept when their stripped Form Type
    column exactly matches an entry in ``target_forms``.
    """
    lines = text.splitlines()
    header_idx = None
    for i, line in enumerate(lines):
        if line.startswith("Form Type"):
            header_idx = i
            break
    if header_idx is None:
        return []

    header = lines[header_idx]
    col_names = ["Form Type", "Company Name", "CIK", "Date Filed", "File Name"]
    starts: list[int] = []
    for name in col_names:
        pos = header.find(name)
        if pos == -1:
            return []
        starts.append(pos)

    out: list[dict[str, Any]] = []
    for line in lines[header_idx + 1:]:
        if not line.strip() or set(line.strip()) <= {"-"}:
            continue
        fields = []
        for j, start in enumerate(starts):
            end = starts[j + 1] if j + 1 < len(starts) else len(line)
            fields.append(line[start:end].strip())
        if len(fields) != 5:
            continue
        form_type, company_name, cik, date_filed, file_name = fields
        if form_type not in target_forms or not file_name:
            continue
        out.append({
            "form": form_type,
            "daily_index_name": company_name,
            "daily_index_cik": cik,
            "filing_date": date_filed,
            "file_name": file_name,
        })
    return out


def submission_text_url(file_name: str) -> str:
    """Pure: full submission .txt URL from a daily-index ``File Name`` entry.

    ``file_name`` looks like ``edgar/data/1234567/0001234567-24-000123.txt``.
    """
    return ARCHIVES_ROOT + file_name.lstrip("/")


def _extract_block(text: str, start_label: str, end_labels: tuple[str, ...]) -> str | None:
    start = text.find(start_label)
    if start == -1:
        return None
    start += len(start_label)
    end = len(text)
    for label in end_labels:
        idx = text.find(label, start)
        if idx != -1:
            end = min(end, idx)
    return text[start:end]


def _parse_company_block(block: str | None) -> tuple[str | None, str | None]:
    if not block:
        return None, None
    name_match = re.search(r"COMPANY CONFORMED NAME:\s*(.+)", block)
    cik_match = re.search(r"CENTRAL INDEX KEY:\s*(\d+)", block)
    name = name_match.group(1).strip() if name_match else None
    cik = cik_match.group(1).strip().lstrip("0") or None if cik_match else None
    return name, cik


def parse_sec_header(text: str) -> dict[str, Any]:
    """Parse the SGML ``<SEC-HEADER>`` for SUBJECT COMPANY / FILED BY identities.

    Pure (no I/O). Returns ``None`` for any field that can't be confidently
    located -- see module docstring for the stability caveats. Only the
    first ``FILED BY`` block is read; joint-filer groups beyond the first
    reporting person are not captured.
    """
    header_end = text.find("</SEC-HEADER>")
    header = text[:header_end] if header_end != -1 else text[:8000]

    subject_block = _extract_block(header, "SUBJECT COMPANY:", ("FILED BY:", "FILER:"))
    filer_block = _extract_block(header, "FILED BY:", ("FILED BY:", "</SEC-HEADER>"))

    issuer_name, issuer_cik = _parse_company_block(subject_block)
    filer_name, filer_cik = _parse_company_block(filer_block)

    return {
        "issuer_name": issuer_name,
        "issuer_cik": issuer_cik,
        "filer_name": filer_name,
        "filer_cik": filer_cik,
    }


# --- Free-text cover-page term extraction -----------------------------------
# These patterns target the standard SC 13D/13G cover-page row labels, which
# are stable across both schedules regardless of row numbering (13D and 13G
# number these rows differently -- see module docstring). Conservative by
# design: a field is only populated when the label is followed by a
# reasonably unambiguous numeric value.

_AGGREGATE_AMOUNT_RE = re.compile(
    r"AGGREGATE\s+AMOUNT\s+BENEFICIALLY\s+OWNED[^\n]*\n+\s*([\d,]+(?:\.\d+)?)",
    re.IGNORECASE,
)
_PERCENT_OF_CLASS_RE = re.compile(
    r"PERCENT\s+OF\s+CLASS\s+REPRESENTED[^\n]*\n+\s*(\d{1,3}(?:\.\d+)?)\s*%",
    re.IGNORECASE,
)
_REPORTING_PERSON_TYPE_RE = re.compile(
    r"TYPE\s+OF\s+REPORTING\s+PERSON[^\n]*\n+\s*([A-Z]{2})\b",
)
_SOLE_VOTING_RE = re.compile(
    r"SOLE\s+VOTING\s+POWER[^\n]*\n+\s*([\d,]+(?:\.\d+)?)", re.IGNORECASE
)
_SHARED_VOTING_RE = re.compile(
    r"SHARED\s+VOTING\s+POWER[^\n]*\n+\s*([\d,]+(?:\.\d+)?)", re.IGNORECASE
)
_SOLE_DISPOSITIVE_RE = re.compile(
    r"SOLE\s+DISPOSITIVE\s+POWER[^\n]*\n+\s*([\d,]+(?:\.\d+)?)", re.IGNORECASE
)
_SHARED_DISPOSITIVE_RE = re.compile(
    r"SHARED\s+DISPOSITIVE\s+POWER[^\n]*\n+\s*([\d,]+(?:\.\d+)?)", re.IGNORECASE
)


def extract_cover_page_terms(text: str) -> dict[str, Any]:
    """Best-effort regex extraction of SC 13D/13G cover-page figures.

    ``text`` should already be HTML-stripped. Returns a dict with
    ``shares_owned``, ``percent_of_class``, ``reporting_person_type``,
    ``sole_voting_power``, ``shared_voting_power``, ``sole_dispositive_power``,
    ``shared_dispositive_power`` -- all ``None`` when not confidently parsed.

    ACCURACY CAVEAT: free-text parsing of a legal cover page, not a
    structured feed; has NOT been validated against a live filing. Known
    limitations mirror ``bond_issuances.extract_pricing_terms()``: only the
    first match of each label is used, so a joint filing listing multiple
    reporting persons' cover pages will only yield the first one's figures.
    """
    result: dict[str, Any] = {
        "shares_owned": None,
        "percent_of_class": None,
        "reporting_person_type": None,
        "sole_voting_power": None,
        "shared_voting_power": None,
        "sole_dispositive_power": None,
        "shared_dispositive_power": None,
    }

    amount_match = _AGGREGATE_AMOUNT_RE.search(text)
    if amount_match:
        result["shares_owned"] = amount_match.group(1)

    percent_match = _PERCENT_OF_CLASS_RE.search(text)
    if percent_match:
        result["percent_of_class"] = percent_match.group(1)

    type_match = _REPORTING_PERSON_TYPE_RE.search(text)
    if type_match:
        result["reporting_person_type"] = type_match.group(1)

    for key, pattern in (
        ("sole_voting_power", _SOLE_VOTING_RE),
        ("shared_voting_power", _SHARED_VOTING_RE),
        ("sole_dispositive_power", _SOLE_DISPOSITIVE_RE),
        ("shared_dispositive_power", _SHARED_DISPOSITIVE_RE),
    ):
        m = pattern.search(text)
        if m:
            result[key] = m.group(1)

    return result


def _parse_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value).replace(",", ""))
    except (InvalidOperation, ValueError):
        return None


def _parse_date(value: Any) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value).strip())
    except ValueError:
        return None


class Edgar13D13GConnector(BaseConnector):
    """Ingest beneficial-ownership disclosures from SEC Schedule 13D/13G filings.

    Sweeps EDGAR's keyless daily form index over a day window (no per-filer
    CIK list required -- see module docstring for why that differs from
    ``edgar_13f.py``/``edgar_form4.py``), then reads each matching filing's
    SGML header + cover page.
    """

    name = "SEC EDGAR Schedule 13D/13G"
    connector_type = "BATCH_API"
    data_domain = "OWNERSHIP"

    def __init__(
        self,
        days_back: int = 10,
        forms: tuple[str, ...] = ALL_SCHEDULE_13_FORMS,
        max_filings: int | None = None,
    ):
        self.days_back = days_back
        self.forms = forms
        self.max_filings = max_filings
        self.rate_limiter = RateLimiter(max_requests=settings.SEC_RATE_LIMIT, per_seconds=1.0)
        self.headers = {"User-Agent": settings.SEC_USER_AGENT}
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(headers=self.headers, timeout=30.0)
        return self._client

    async def _fetch_daily_index(self, day: date) -> str | None:
        await self.rate_limiter.acquire()
        client = await self._get_client()
        try:
            resp = await client.get(daily_index_url(day))
            if resp.status_code == 404:
                # No filings that day (weekend/holiday) — not an error.
                return None
            resp.raise_for_status()
            return resp.text
        except Exception as exc:  # pragma: no cover - network
            logger.warning("[%s] failed to fetch daily index for %s: %s", self.name, day, exc)
            return None

    async def _fetch_submission_text(self, file_name: str) -> str | None:
        await self.rate_limiter.acquire()
        client = await self._get_client()
        try:
            resp = await client.get(submission_text_url(file_name))
            resp.raise_for_status()
            return resp.text
        except Exception as exc:  # pragma: no cover - network
            logger.warning("[%s] failed to fetch submission %s: %s", self.name, file_name, exc)
            return None

    async def extract(self) -> list[dict[str, Any]]:
        end = date.today()
        start = end - timedelta(days=self.days_back)

        stubs: list[dict[str, Any]] = []
        seen_files: set[str] = set()
        day = start
        while day <= end:
            idx_text = await self._fetch_daily_index(day)
            day += timedelta(days=1)
            if idx_text is None:
                continue
            for stub in parse_daily_index(idx_text, self.forms):
                if stub["file_name"] in seen_files:
                    continue
                seen_files.add(stub["file_name"])
                stubs.append(stub)

        logger.info(
            "[%s] found %d Schedule 13D/13G filings across %d days",
            self.name, len(stubs), self.days_back + 1,
        )
        if self.max_filings is not None:
            stubs = stubs[: self.max_filings]

        records: list[dict[str, Any]] = []
        for stub in stubs:
            full_text = await self._fetch_submission_text(stub["file_name"])
            if full_text is None:
                continue
            header = parse_sec_header(full_text)
            terms = extract_cover_page_terms(_strip_html(full_text))
            accession = stub["file_name"].rsplit("/", 1)[-1].removesuffix(".txt")
            records.append({
                **stub,
                **header,
                **terms,
                "accession_number": accession,
                "filing_url": submission_text_url(stub["file_name"]),
            })
        return records

    async def validate(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        valid = []
        for rec in records:
            has_issuer = rec.get("issuer_cik") or rec.get("issuer_name") or rec.get("daily_index_cik")
            has_filer = rec.get("filer_name") or rec.get("daily_index_name")
            if has_issuer and has_filer and rec.get("form") and rec.get("filing_date"):
                valid.append(rec)
        return valid

    async def transform(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        transformed = []
        for rec in records:
            form = rec["form"]
            # The daily index doesn't reliably say whether a given CIK/name
            # is the subject company or the filer (an accession can appear
            # under either party's CIK); prefer the SEC-HEADER-derived
            # identities and only fall back to the daily-index columns when
            # the header couldn't be parsed.
            issuer_cik = rec.get("issuer_cik") or rec.get("daily_index_cik")
            issuer_name = rec.get("issuer_name") or rec.get("daily_index_name")
            filer_name = rec.get("filer_name") or rec.get("daily_index_name")
            filer_cik = rec.get("filer_cik")

            transformed.append({
                "issuer_cik": issuer_cik,
                "issuer_name": issuer_name,
                "filer_name": filer_name,
                "filer_cik": filer_cik,
                "reporting_person_type": rec.get("reporting_person_type"),
                "schedule_type": form,
                "is_activist": form.startswith("SC 13D"),
                "is_amendment": form.endswith("/A"),
                "filing_date": rec.get("filing_date"),
                "shares_owned": rec.get("shares_owned"),
                "percent_of_class": rec.get("percent_of_class"),
                "sole_voting_power": rec.get("sole_voting_power"),
                "shared_voting_power": rec.get("shared_voting_power"),
                "sole_dispositive_power": rec.get("sole_dispositive_power"),
                "shared_dispositive_power": rec.get("shared_dispositive_power"),
                "accession_number": rec.get("accession_number"),
                "filing_url": rec.get("filing_url"),
            })
        logger.info("[%s] transformed %d filings", self.name, len(transformed))
        return transformed

    async def load(
        self, records: list[dict[str, Any]], session: AsyncSession
    ) -> dict[str, int]:
        from src.models.entity import Entity, EntityIdentifier
        from src.models.ownership import BeneficialOwnershipFiling
        from src.models.security import Security

        stats = {"inserted": 0, "skipped": 0, "errors": 0}

        for rec in records:
            try:
                async with session.begin_nested():
                    # Never fabricate the issuer -- skip if it doesn't
                    # resolve to an existing entity (same doctrine as
                    # bond_issuances.py).
                    issuer_entity_id = None
                    if rec.get("issuer_cik"):
                        issuer_entity_id = (
                            await session.execute(
                                select(EntityIdentifier.entity_id).where(
                                    EntityIdentifier.identifier_type == "CIK",
                                    EntityIdentifier.identifier_value == str(rec["issuer_cik"]),
                                )
                            )
                        ).scalar_one_or_none()
                    if issuer_entity_id is None and rec.get("issuer_name"):
                        issuer_entity_id = (
                            await session.execute(
                                select(Entity.entity_id).where(
                                    Entity.legal_name == rec["issuer_name"]
                                )
                            )
                        ).scalar_one_or_none()
                    if issuer_entity_id is None:
                        stats["skipped"] += 1
                        continue

                    accession = rec.get("accession_number")
                    if accession:
                        existing = (
                            await session.execute(
                                select(BeneficialOwnershipFiling.filing_id).where(
                                    BeneficialOwnershipFiling.accession_number == accession
                                )
                            )
                        ).scalar_one_or_none()
                        if existing is not None:
                            stats["skipped"] += 1
                            continue

                    filing_date_val = _parse_date(rec.get("filing_date"))
                    if filing_date_val is None:
                        stats["skipped"] += 1
                        continue

                    # The filer (activist fund/individual) is often not a
                    # covered entity — resolve if possible, but always keep
                    # the denormalized name (never block the row on this).
                    filer_entity_id = None
                    if rec.get("filer_cik"):
                        filer_entity_id = (
                            await session.execute(
                                select(EntityIdentifier.entity_id).where(
                                    EntityIdentifier.identifier_type == "CIK",
                                    EntityIdentifier.identifier_value == str(rec["filer_cik"]),
                                )
                            )
                        ).scalar_one_or_none()

                    security_id = (
                        await session.execute(
                            select(Security.security_id).where(
                                Security.issuer_entity_id == issuer_entity_id
                            )
                        )
                    ).scalars().first()

                    session.add(BeneficialOwnershipFiling(
                        filing_id=uuid.uuid4(),
                        issuer_entity_id=issuer_entity_id,
                        security_id=security_id,
                        filer_entity_id=filer_entity_id,
                        filer_name=(rec.get("filer_name") or "Unknown")[:300],
                        filer_cik=rec.get("filer_cik"),
                        reporting_person_type=rec.get("reporting_person_type"),
                        schedule_type=rec["schedule_type"],
                        is_activist=rec["is_activist"],
                        is_amendment=rec["is_amendment"],
                        filing_date=filing_date_val,
                        shares_owned=_parse_decimal(rec.get("shares_owned")),
                        percent_of_class=_parse_decimal(rec.get("percent_of_class")),
                        sole_voting_power=_parse_decimal(rec.get("sole_voting_power")),
                        shared_voting_power=_parse_decimal(rec.get("shared_voting_power")),
                        sole_dispositive_power=_parse_decimal(rec.get("sole_dispositive_power")),
                        shared_dispositive_power=_parse_decimal(rec.get("shared_dispositive_power")),
                        accession_number=accession,
                        filing_url=rec.get("filing_url"),
                        source="SEC_EDGAR_SC13",
                    ))
                    stats["inserted"] += 1
                    await session.flush()

            except Exception as e:
                logger.error("[%s] error loading filing: %s", self.name, e)
                stats["errors"] += 1

        await session.flush()
        return stats

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None
