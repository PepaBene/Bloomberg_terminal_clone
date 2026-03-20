"""EDGAR 10-K NLP connector — relationship extraction from SEC filings (Spec 15.3).

Extracts business relationships from 10-K filing sections:
- Item 1 (Business): customer, supplier, competitor mentions
- Item 1A (Risk Factors): supply chain and competitive risks
- Item 7 (MD&A): revenue concentration, key customer disclosures

Uses keyword-based NLP (no ML models) to identify:
- Customer relationships (ASC 280 >10% revenue disclosures)
- Supplier/vendor dependencies
- Competitive landscape references

Creates BusinessRelationship records in src/models/relationships.py.
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
from src.ingestion.base import BaseConnector
from src.ingestion.nlp_utils import (
    classify_relationship_from_context,
    extract_10k_section,
    extract_revenue_percentages,
    find_entity_mentions,
)
from src.ingestion.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)

# SEC EDGAR endpoints
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
FULL_TEXT_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/{primary_doc}"

# Sections to extract and analyze
TARGET_SECTIONS = ["item_1", "item_1a", "item_7"]


class Edgar10KNLPConnector(BaseConnector):
    """Extract business relationships from 10-K filings using keyword NLP."""

    name = "EDGAR 10-K NLP"
    connector_type = "BATCH_API"
    data_domain = "RELATIONSHIPS"

    def __init__(
        self,
        cik_list: list[str] | None = None,
        known_entity_names: list[dict[str, Any]] | None = None,
        filing_limit: int = 3,
    ) -> None:
        """Initialize EDGAR 10-K NLP connector.

        Args:
            cik_list: List of CIK numbers to process.
            known_entity_names: List of dicts with 'entity_id' and 'name' keys
                                for matching entity mentions in filing text.
            filing_limit: Max recent 10-K filings to process per company.
        """
        self.cik_list = cik_list or []
        self.known_entity_names = known_entity_names or []
        self.filing_limit = filing_limit
        self.rate_limiter = RateLimiter(
            max_requests=settings.SEC_RATE_LIMIT, per_seconds=1.0
        )
        self.headers = {"User-Agent": settings.SEC_USER_AGENT}
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                headers=self.headers, timeout=30.0
            )
        return self._client

    async def _sec_get(self, url: str) -> httpx.Response:
        """Make a rate-limited GET request to SEC EDGAR."""
        await self.rate_limiter.acquire()
        client = await self._get_client()
        resp = await client.get(url)
        resp.raise_for_status()
        return resp

    async def _fetch_10k_filings(self, cik: str) -> list[dict[str, Any]]:
        """Fetch recent 10-K filing metadata for a CIK."""
        padded_cik = cik.zfill(10)
        url = SUBMISSIONS_URL.format(cik=padded_cik)

        try:
            resp = await self._sec_get(url)
            data = resp.json()
        except Exception as e:
            logger.error("Failed to fetch submissions for CIK %s: %s", cik, e)
            return []

        recent = data.get("filings", {}).get("recent", {})
        forms = recent.get("form", [])
        accessions = recent.get("accessionNumber", [])
        primary_docs = recent.get("primaryDocument", [])
        filing_dates = recent.get("filingDate", [])

        filings: list[dict[str, Any]] = []
        count = 0

        for i, form in enumerate(forms):
            if form != "10-K":
                continue
            if count >= self.filing_limit:
                break

            count += 1
            accession_clean = accessions[i].replace("-", "")
            filings.append({
                "cik": cik,
                "accession_number": accessions[i],
                "primary_document": primary_docs[i],
                "filing_date": filing_dates[i],
                "url": FULL_TEXT_URL.format(
                    cik=cik,
                    accession=accession_clean,
                    primary_doc=primary_docs[i],
                ),
            })

        return filings

    async def extract(self) -> list[dict[str, Any]]:
        """Pull 10-K filing text from SEC EDGAR and extract sections."""
        if not self.cik_list:
            logger.warning("[%s] No CIK list provided — skipping extraction", self.name)
            return []

        records: list[dict[str, Any]] = []

        for cik in self.cik_list:
            filings = await self._fetch_10k_filings(cik)
            logger.info(
                "  EDGAR 10-K NLP: CIK %s — found %d 10-K filings",
                cik,
                len(filings),
            )

            for filing in filings:
                try:
                    resp = await self._sec_get(filing["url"])
                    full_text = resp.text
                except Exception as e:
                    logger.warning(
                        "Failed to fetch 10-K text for CIK %s (%s): %s",
                        cik,
                        filing["accession_number"],
                        e,
                    )
                    continue

                # Extract target sections
                sections: dict[str, str] = {}
                for section_key in TARGET_SECTIONS:
                    section_text = extract_10k_section(full_text, section_key)
                    if section_text:
                        sections[section_key] = section_text

                if not sections:
                    logger.debug(
                        "No target sections found in CIK %s filing %s",
                        cik,
                        filing["accession_number"],
                    )
                    continue

                records.append({
                    "cik": cik,
                    "accession_number": filing["accession_number"],
                    "filing_date": filing["filing_date"],
                    "sections": sections,
                })

        return records

    async def validate(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Validate extracted section records."""
        valid: list[dict[str, Any]] = []
        for rec in records:
            if not rec.get("cik"):
                continue
            if not rec.get("sections"):
                continue
            if not rec.get("filing_date"):
                continue
            # At least one section must have meaningful content
            has_content = any(
                len(text) > 200 for text in rec["sections"].values()
            )
            if not has_content:
                logger.debug(
                    "Skipping CIK %s filing — sections too short",
                    rec.get("cik"),
                )
                continue
            valid.append(rec)
        return valid

    async def transform(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Extract relationships from 10-K sections using keyword NLP."""
        entity_name_list = [e["name"] for e in self.known_entity_names]
        entity_name_to_id: dict[str, Any] = {
            e["name"]: e["entity_id"] for e in self.known_entity_names
        }

        transformed: list[dict[str, Any]] = []

        for rec in records:
            cik = rec["cik"]
            filing_date = rec["filing_date"]
            accession = rec["accession_number"]
            relationships: list[dict[str, Any]] = []

            for section_key, section_text in rec["sections"].items():
                # Find mentions of known entities in this section
                mentions = find_entity_mentions(section_text, entity_name_list)

                for mention in mentions:
                    entity_name = mention["name"]
                    context = mention["context"]

                    # Classify the relationship type from surrounding context
                    rel_type = classify_relationship_from_context(context)
                    if rel_type is None:
                        continue

                    # Extract revenue percentage if this is a customer mention
                    revenue_pct = None
                    if rel_type == "CUSTOMER":
                        pcts = extract_revenue_percentages(context)
                        if pcts:
                            revenue_pct = pcts[0]  # Take highest percentage

                    # Determine confidence based on evidence quality
                    confidence = self._compute_confidence(
                        rel_type, revenue_pct, section_key
                    )

                    target_entity_id = entity_name_to_id.get(entity_name)

                    relationships.append({
                        "source_cik": cik,
                        "target_entity_name": entity_name,
                        "target_entity_id": target_entity_id,
                        "relationship_type": rel_type,
                        "revenue_percentage": revenue_pct,
                        "confidence_score": confidence,
                        "extraction_method": "KEYWORD_NLP",
                        "source_document": f"SEC 10-K {accession}",
                        "source_section": section_key,
                        "source_text": context[:500],
                        "filing_date": filing_date,
                    })

            # Deduplicate relationships (same target + type)
            deduped = self._deduplicate_relationships(relationships)

            if deduped:
                transformed.append({
                    "cik": cik,
                    "filing_date": filing_date,
                    "accession_number": accession,
                    "relationships": deduped,
                })

        return transformed

    async def load(
        self, records: list[dict[str, Any]], session: AsyncSession
    ) -> dict[str, int]:
        """Write BusinessRelationship records to the database."""
        from src.models.entity import EntityIdentifier
        from src.models.relationships import BusinessRelationship

        stats = {"inserted": 0, "updated": 0, "skipped": 0, "errors": 0}

        for rec in records:
            try:
                cik = rec["cik"]
                filing_date_str = rec["filing_date"]
                effective_date = date.fromisoformat(filing_date_str)

                # Resolve source CIK to entity_id
                result = await session.execute(
                    select(EntityIdentifier).where(
                        EntityIdentifier.identifier_type == "CIK",
                        EntityIdentifier.identifier_value == cik,
                    )
                )
                source_eid = result.scalar_one_or_none()
                if source_eid is None:
                    logger.debug("No entity found for CIK %s — skipping", cik)
                    stats["skipped"] += 1
                    continue

                source_entity_id = source_eid.entity_id

                for rel_data in rec.get("relationships", []):
                    try:
                        target_entity_id = rel_data.get("target_entity_id")
                        if target_entity_id is None:
                            # Cannot create relationship without target entity
                            stats["skipped"] += 1
                            continue

                        # Check for existing relationship
                        existing = await session.execute(
                            select(BusinessRelationship).where(
                                BusinessRelationship.source_entity_id == source_entity_id,
                                BusinessRelationship.target_entity_id == target_entity_id,
                                BusinessRelationship.relationship_type == rel_data["relationship_type"],
                                BusinessRelationship.effective_date == effective_date,
                            )
                        )
                        if existing.scalar_one_or_none() is not None:
                            stats["skipped"] += 1
                            continue

                        revenue_pct = rel_data.get("revenue_percentage")
                        relationship = BusinessRelationship(
                            relationship_id=uuid.uuid4(),
                            source_entity_id=source_entity_id,
                            target_entity_id=target_entity_id,
                            relationship_type=rel_data["relationship_type"],
                            direction="OUTBOUND",
                            revenue_percentage=Decimal(str(revenue_pct / 100)) if revenue_pct else None,
                            confidence_score=Decimal(str(rel_data.get("confidence_score", 0.5))),
                            extraction_method=rel_data.get("extraction_method", "KEYWORD_NLP"),
                            source_document=rel_data.get("source_document"),
                            source_text=rel_data.get("source_text"),
                            effective_date=effective_date,
                            is_active=True,
                        )
                        session.add(relationship)
                        stats["inserted"] += 1

                    except Exception as e:
                        logger.debug("Skip relationship: %s", e)
                        stats["errors"] += 1

                await session.flush()

            except Exception as e:
                logger.error(
                    "Error loading relationships for CIK %s: %s",
                    rec.get("cik"),
                    e,
                )
                stats["errors"] += 1

        await session.flush()
        return stats

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_confidence(
        rel_type: str,
        revenue_pct: float | None,
        section_key: str,
    ) -> float:
        """Compute a confidence score for an extracted relationship.

        Higher confidence for:
        - Revenue percentages (quantitative evidence)
        - Item 1 / Item 7 mentions (more reliable sections)
        - Customer relationships with ASC 280 disclosures
        """
        base = 0.40

        # Revenue percentage is strong quantitative evidence
        if revenue_pct is not None and revenue_pct >= 10.0:
            base += 0.30
        elif revenue_pct is not None:
            base += 0.15

        # Section reliability bonus
        section_bonus: dict[str, float] = {
            "item_1": 0.15,
            "item_7": 0.15,
            "item_1a": 0.10,
        }
        base += section_bonus.get(section_key, 0.0)

        return min(round(base, 2), 0.99)

    @staticmethod
    def _deduplicate_relationships(
        relationships: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Deduplicate relationships by target entity + type.

        Keeps the entry with the highest confidence score.
        """
        best: dict[str, dict[str, Any]] = {}

        for rel in relationships:
            key = f"{rel['target_entity_name']}|{rel['relationship_type']}"
            existing = best.get(key)
            if existing is None or rel.get("confidence_score", 0) > existing.get(
                "confidence_score", 0
            ):
                best[key] = rel

        return list(best.values())

    async def close(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
