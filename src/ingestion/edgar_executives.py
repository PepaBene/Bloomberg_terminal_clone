"""SEC EDGAR Executive/Director connector.

Builds the executive/director database (``executives`` / ``executive_roles``)
from the reporting-owner data carried in SEC Form 3/4/5 ownership filings.
Every insider filing identifies the reporting person by name and — via the
``reportingOwnerRelationship`` block — whether they are a director, officer
(with title) and/or a ten-percent owner. That is a reliable, free, structured
signal for who the officers and directors of an issuer are.

CIK-driven (issuer CIKs), following the ``edgar_form4`` / ``edgar_8k`` pattern.
The XML parse + transform + load path is exercised by mocked/sample-payload
unit tests; live extraction requires SEC network access.
"""

from __future__ import annotations

import logging
import uuid
import xml.etree.ElementTree as ET
from datetime import date
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

# Ownership forms that carry reporting-owner relationship data.
OWNERSHIP_FORMS = ("3", "4", "5", "3/A", "4/A", "5/A")


def _xml_text(parent: ET.Element | None, tag: str) -> str | None:
    """Return stripped text of ``tag`` under ``parent`` (dotted path allowed)."""
    if parent is None:
        return None
    el = parent.find(tag)
    if el is not None and el.text and el.text.strip():
        return el.text.strip()
    return None


def _is_flag(parent: ET.Element | None, tag: str) -> bool:
    """SEC ownership XML uses '1'/'true' for boolean relationship flags."""
    val = _xml_text(parent, tag)
    return val is not None and val.lower() in ("1", "true")


def parse_ownership_owner(xml_text: str) -> dict[str, Any] | None:
    """Parse issuer + reporting-owner identity/role from an ownership XML doc.

    Pure (no I/O) so it can be unit-tested directly. Returns None if the doc
    has no usable reporting-owner name.
    """
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:  # pragma: no cover - defensive
        logger.warning("Failed to parse ownership XML: %s", exc)
        return None

    issuer = root.find(".//issuer")
    issuer_cik = _xml_text(issuer, "issuerCik")
    issuer_name = _xml_text(issuer, "issuerName")

    owner = root.find(".//reportingOwner")
    owner_id = owner.find("reportingOwnerId") if owner is not None else None
    person_name = _xml_text(owner_id, "rptOwnerName")
    person_cik = _xml_text(owner_id, "rptOwnerCik")

    rel = owner.find("reportingOwnerRelationship") if owner is not None else None
    is_director = _is_flag(rel, "isDirector")
    is_officer = _is_flag(rel, "isOfficer")
    is_ten_pct = _is_flag(rel, "isTenPercentOwner")
    officer_title = _xml_text(rel, "officerTitle")

    if not person_name:
        return None

    return {
        "issuer_cik": issuer_cik,
        "issuer_name": issuer_name,
        "person_name": person_name,
        "person_cik": person_cik,
        "is_director": is_director,
        "is_officer": is_officer,
        "is_ten_percent": is_ten_pct,
        "officer_title": officer_title,
    }


class EdgarExecutivesConnector(BaseConnector):
    """Ingest executives/directors from SEC ownership (Form 3/4/5) filings."""

    name = "SEC EDGAR Executives"
    connector_type = "BATCH_API"
    data_domain = "GOVERNANCE"

    def __init__(
        self,
        issuer_ciks: list[str] | None = None,
        days_back: int = 365,
        max_filings_per_cik: int = 50,
    ):
        self.issuer_ciks = issuer_ciks or []
        self.days_back = days_back
        self.max_filings_per_cik = max_filings_per_cik
        self.rate_limiter = RateLimiter(
            max_requests=settings.SEC_RATE_LIMIT, per_seconds=1.0
        )
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
            logger.warning("Failed to fetch submissions for CIK %s: %s", cik, exc)
            return None

    async def _fetch_ownership_xml(self, cik: str, accession: str) -> str | None:
        accession_clean = accession.replace("-", "")
        cik_num = cik.lstrip("0")
        index_url = f"{ARCHIVES_BASE_URL}/{cik_num}/{accession_clean}/index.json"
        await self.rate_limiter.acquire()
        client = await self._get_client()
        try:
            resp = await client.get(index_url)
            resp.raise_for_status()
            items = resp.json().get("directory", {}).get("item", [])
        except Exception as exc:  # pragma: no cover - network
            logger.warning("Failed to fetch filing index for %s: %s", accession, exc)
            return None

        xml_doc = None
        for item in items:
            name = item.get("name", "").lower()
            if name.endswith(".xml") and (
                "form" in name or "doc" in name or "primary_doc" in name
            ):
                xml_doc = item["name"]
                break
        if xml_doc is None:
            for item in items:
                if item.get("name", "").lower().endswith(".xml"):
                    xml_doc = item["name"]
                    break
        if xml_doc is None:
            return None

        xml_url = f"{ARCHIVES_BASE_URL}/{cik_num}/{accession_clean}/{xml_doc}"
        await self.rate_limiter.acquire()
        try:
            resp = await client.get(xml_url)
            resp.raise_for_status()
            return resp.text
        except Exception as exc:  # pragma: no cover - network
            logger.warning("Failed to fetch ownership XML for %s: %s", accession, exc)
            return None

    async def extract(self) -> list[dict[str, Any]]:
        if not self.issuer_ciks:
            logger.warning("No issuer CIKs configured — skipping executives extraction")
            return []

        from datetime import timedelta

        records: list[dict[str, Any]] = []
        cutoff = date.today() - timedelta(days=self.days_back)

        for cik in self.issuer_ciks:
            submissions = await self._fetch_submissions(cik)
            if submissions is None:
                continue
            recent = submissions.get("filings", {}).get("recent", {})
            forms = recent.get("form", [])
            accessions = recent.get("accessionNumber", [])
            filed = recent.get("filingDate", [])

            count = 0
            for i, form in enumerate(forms):
                if form not in OWNERSHIP_FORMS:
                    continue
                filing_date_str = filed[i] if i < len(filed) else ""
                try:
                    if date.fromisoformat(filing_date_str) < cutoff:
                        continue
                except (ValueError, TypeError):
                    continue
                accession = accessions[i] if i < len(accessions) else ""
                if not accession:
                    continue
                xml_text = await self._fetch_ownership_xml(cik, accession)
                if xml_text is None:
                    continue
                parsed = parse_ownership_owner(xml_text)
                if parsed is None:
                    continue
                parsed.setdefault("issuer_cik", cik)
                parsed["accession_number"] = accession
                parsed["filing_date"] = filing_date_str
                records.append(parsed)
                count += 1
                if count >= self.max_filings_per_cik:
                    break
            logger.info("  Executives: CIK %s — %d ownership filings parsed", cik, count)

        return records

    async def validate(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        valid = []
        for rec in records:
            if not rec.get("person_name"):
                continue
            if not (rec.get("issuer_cik")):
                continue
            # Must indicate at least one insider relationship.
            if not (rec.get("is_director") or rec.get("is_officer") or rec.get("is_ten_percent")):
                continue
            valid.append(rec)
        return valid

    async def transform(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Normalize ownership rows to Executive/ExecutiveRole field dicts.

        Pure (no I/O) — directly unit-testable. De-duplicates so a person with
        multiple filings at the same issuer/role produces one role record.
        """
        seen: set[tuple[str, str, str]] = set()
        out: list[dict[str, Any]] = []
        for rec in records:
            person_name = (rec.get("person_name") or "").strip()
            issuer_cik = rec.get("issuer_cik")
            if not person_name or not issuer_cik:
                continue

            if rec.get("is_officer"):
                role_type = "OFFICER"
                title = (rec.get("officer_title") or "Officer").strip()[:100]
                is_independent = False
            elif rec.get("is_director"):
                role_type = "DIRECTOR"
                title = "Director"
                is_independent = None  # independence not stated in Form 4
            else:
                role_type = "10PCT"
                title = "10% Owner"
                is_independent = None

            key = (person_name.lower(), issuer_cik, role_type)
            if key in seen:
                continue
            seen.add(key)

            out.append(
                {
                    "person_name": person_name,
                    "issuer_cik": issuer_cik,
                    "role_type": role_type,
                    "title": title,
                    "is_independent": is_independent,
                }
            )
        logger.info("Transformed %d executive-role records", len(out))
        return out

    async def load(
        self, records: list[dict[str, Any]], session: AsyncSession
    ) -> dict[str, int]:
        from src.models.entity import EntityIdentifier
        from src.models.executives import Executive, ExecutiveRole

        stats = {"inserted": 0, "updated": 0, "skipped": 0, "errors": 0}
        if getattr(self, "dry_run", False):
            return stats

        for rec in records:
            try:
                # Resolve issuer entity_id from CIK. entity_id is required for a role.
                ident = (
                    await session.execute(
                        select(EntityIdentifier).where(
                            EntityIdentifier.identifier_type == "CIK",
                            EntityIdentifier.identifier_value == rec["issuer_cik"],
                        )
                    )
                ).scalar_one_or_none()
                if ident is None:
                    stats["skipped"] += 1
                    continue
                entity_id = ident.entity_id

                # Upsert the person (by name).
                executive = (
                    await session.execute(
                        select(Executive).where(
                            Executive.person_name == rec["person_name"]
                        )
                    )
                ).scalar_one_or_none()
                if executive is None:
                    executive = Executive(
                        executive_id=uuid.uuid4(),
                        person_name=rec["person_name"],
                    )
                    session.add(executive)
                    await session.flush()

                # Upsert the role (by person + entity + role_type + title).
                existing_role = (
                    await session.execute(
                        select(ExecutiveRole).where(
                            ExecutiveRole.executive_id == executive.executive_id,
                            ExecutiveRole.entity_id == entity_id,
                            ExecutiveRole.role_type == rec["role_type"],
                            ExecutiveRole.title == rec["title"],
                        )
                    )
                ).scalar_one_or_none()
                if existing_role is not None:
                    stats["skipped"] += 1
                    continue

                session.add(
                    ExecutiveRole(
                        role_id=uuid.uuid4(),
                        executive_id=executive.executive_id,
                        entity_id=entity_id,
                        title=rec["title"],
                        role_type=rec["role_type"],
                        is_independent=rec.get("is_independent"),
                    )
                )
                stats["inserted"] += 1
            except Exception:  # pragma: no cover - defensive
                logger.exception("[%s] failed to load executive row", self.name)
                stats["errors"] += 1

        await session.flush()
        return stats

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None
