"""EDGAR ESG connector — governance data from SEC filings (Spec 15.3).

Parses governance-related data from 10-K and DEF 14A filings:
- Board composition (independent directors, diversity)
- Executive compensation summary
- Shareholder proposal results

Limited scope: only governance pillar (no E or S data from filings).
Creates ESGScore and ESGMetric records in src/models/esg.py.
"""

import logging
import re
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.ingestion.base import BaseConnector
from src.ingestion.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)

# SEC EDGAR endpoints
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
FULL_TEXT_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/{primary_doc}"

# Filing types we parse for ESG/governance data
ESG_FILING_TYPES = {"10-K", "DEF 14A"}

# Governance keywords for scoring
_BOARD_INDEPENDENCE_PATTERN = re.compile(
    r"(\d{1,2})\s+(?:of\s+)?(?:our\s+)?(\d{1,2})\s+"
    r"(?:directors?|board\s+members?)\s+(?:are|is|were)\s+"
    r"(?:independent|non-executive)",
    re.IGNORECASE,
)
_BOARD_SIZE_PATTERN = re.compile(
    r"(?:board\s+of\s+directors?\s+(?:consists?\s+of|comprises?|has)\s+)"
    r"(\d{1,2})\s+(?:members?|directors?)",
    re.IGNORECASE,
)
_FEMALE_DIRECTOR_PATTERN = re.compile(
    r"(\d{1,2})\s+(?:of\s+)?(?:our\s+)?(?:directors?|board\s+members?)\s+"
    r"(?:are|is|were)\s+(?:female|women)",
    re.IGNORECASE,
)
_CEO_COMP_PATTERN = re.compile(
    r"(?:Chief\s+Executive|CEO|Principal\s+Executive).*?"
    r"\$\s*([\d,]+(?:\.\d{2})?)",
    re.IGNORECASE | re.DOTALL,
)
_SHAREHOLDER_PROPOSAL_PATTERN = re.compile(
    r"(?:shareholder|stockholder)\s+proposal",
    re.IGNORECASE,
)


class EdgarESGConnector(BaseConnector):
    """Parse ESG governance data from SEC 10-K and DEF 14A filings."""

    name = "EDGAR ESG"
    connector_type = "BATCH_API"
    data_domain = "ESG"

    def __init__(
        self,
        cik_list: list[str] | None = None,
        filing_limit: int = 5,
    ) -> None:
        """Initialize EDGAR ESG connector.

        Args:
            cik_list: List of CIK numbers to process. If None, must be set
                      before calling extract().
            filing_limit: Max recent filings per type to fetch per company.
        """
        self.cik_list = cik_list or []
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

    async def _fetch_filing_index(self, cik: str) -> list[dict[str, Any]]:
        """Fetch recent 10-K and DEF 14A filing metadata for a CIK."""
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
        counts: dict[str, int] = {}

        for i, form in enumerate(forms):
            if form not in ESG_FILING_TYPES:
                continue
            if counts.get(form, 0) >= self.filing_limit:
                continue

            counts[form] = counts.get(form, 0) + 1
            accession_clean = accessions[i].replace("-", "")
            filings.append({
                "cik": cik,
                "form_type": form,
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

    async def _fetch_filing_text(self, filing: dict[str, Any]) -> str | None:
        """Fetch the full text of a filing document."""
        try:
            resp = await self._sec_get(filing["url"])
            return resp.text
        except Exception as e:
            logger.warning(
                "Failed to fetch filing text for CIK %s (%s): %s",
                filing["cik"],
                filing["accession_number"],
                e,
            )
            return None

    async def extract(self) -> list[dict[str, Any]]:
        """Pull 10-K and DEF 14A filing text from SEC EDGAR."""
        if not self.cik_list:
            logger.warning("[%s] No CIK list provided — skipping extraction", self.name)
            return []

        records: list[dict[str, Any]] = []

        for cik in self.cik_list:
            filings = await self._fetch_filing_index(cik)
            logger.info("  EDGAR ESG: CIK %s — found %d relevant filings", cik, len(filings))

            for filing in filings:
                text = await self._fetch_filing_text(filing)
                if text:
                    records.append({
                        "cik": cik,
                        "form_type": filing["form_type"],
                        "accession_number": filing["accession_number"],
                        "filing_date": filing["filing_date"],
                        "text": text,
                    })

        return records

    async def validate(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Validate extracted filing records."""
        valid: list[dict[str, Any]] = []
        for rec in records:
            if not rec.get("cik"):
                continue
            if not rec.get("text") or len(rec["text"]) < 500:
                logger.debug(
                    "Skipping filing for CIK %s — text too short (%d chars)",
                    rec.get("cik"),
                    len(rec.get("text", "")),
                )
                continue
            if not rec.get("filing_date"):
                continue
            valid.append(rec)
        return valid

    async def transform(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Extract governance metrics from filing text."""
        transformed: list[dict[str, Any]] = []

        for rec in records:
            text = rec["text"]
            cik = rec["cik"]
            filing_date = rec["filing_date"]
            form_type = rec["form_type"]
            accession = rec["accession_number"]

            metrics: list[dict[str, Any]] = []
            governance_score_components: list[float] = []

            # --- Board composition ---
            board_size = self._extract_board_size(text)
            if board_size:
                metrics.append({
                    "metric_type": "BOARD_SIZE",
                    "metric_category": "GOVERNANCE",
                    "value": float(board_size),
                    "unit": "directors",
                    "source": f"SEC_{form_type}",
                })

            independent_count, total_count = self._extract_board_independence(text)
            if independent_count is not None and total_count:
                independence_ratio = independent_count / total_count
                metrics.append({
                    "metric_type": "BOARD_INDEPENDENCE_RATIO",
                    "metric_category": "GOVERNANCE",
                    "value": round(independence_ratio, 4),
                    "unit": "ratio",
                    "source": f"SEC_{form_type}",
                })
                # Score: >50% independent = good
                governance_score_components.append(
                    min(independence_ratio / 0.75, 1.0) * 100
                )

            female_count = self._extract_female_directors(text)
            if female_count is not None:
                metrics.append({
                    "metric_type": "FEMALE_DIRECTORS",
                    "metric_category": "GOVERNANCE",
                    "value": float(female_count),
                    "unit": "directors",
                    "source": f"SEC_{form_type}",
                })
                if board_size and board_size > 0:
                    diversity_ratio = female_count / board_size
                    metrics.append({
                        "metric_type": "BOARD_GENDER_DIVERSITY_RATIO",
                        "metric_category": "GOVERNANCE",
                        "value": round(diversity_ratio, 4),
                        "unit": "ratio",
                        "source": f"SEC_{form_type}",
                    })
                    governance_score_components.append(
                        min(diversity_ratio / 0.40, 1.0) * 100
                    )

            # --- Executive compensation ---
            ceo_comp = self._extract_ceo_compensation(text)
            if ceo_comp is not None:
                metrics.append({
                    "metric_type": "CEO_TOTAL_COMPENSATION",
                    "metric_category": "GOVERNANCE",
                    "value": ceo_comp,
                    "unit": "USD",
                    "source": f"SEC_{form_type}",
                })

            # --- Shareholder proposals ---
            has_proposals = self._has_shareholder_proposals(text)
            if has_proposals:
                metrics.append({
                    "metric_type": "HAS_SHAREHOLDER_PROPOSALS",
                    "metric_category": "GOVERNANCE",
                    "value": 1.0,
                    "unit": "boolean",
                    "source": f"SEC_{form_type}",
                })

            # Build governance score (average of available components)
            governance_score = None
            if governance_score_components:
                governance_score = round(
                    sum(governance_score_components) / len(governance_score_components),
                    2,
                )

            transformed.append({
                "cik": cik,
                "filing_date": filing_date,
                "form_type": form_type,
                "accession_number": accession,
                "metrics": metrics,
                "governance_score": governance_score,
            })

        return transformed

    async def load(
        self, records: list[dict[str, Any]], session: AsyncSession
    ) -> dict[str, int]:
        """Write ESGScore and ESGMetric records to the database."""
        from src.models.entity import EntityIdentifier
        from src.models.esg import ESGMetric, ESGScore

        stats = {"inserted": 0, "updated": 0, "skipped": 0, "errors": 0}

        for rec in records:
            try:
                cik = rec["cik"]
                filing_date_str = rec["filing_date"]
                as_of_date = date.fromisoformat(filing_date_str)

                # Resolve CIK to entity_id
                result = await session.execute(
                    select(EntityIdentifier).where(
                        EntityIdentifier.identifier_type == "CIK",
                        EntityIdentifier.identifier_value == cik,
                    )
                )
                eid_row = result.scalar_one_or_none()
                if eid_row is None:
                    logger.debug("No entity found for CIK %s — skipping", cik)
                    stats["skipped"] += 1
                    continue

                entity_id = eid_row.entity_id

                # Check for existing ESG score to avoid duplicates
                existing_score = await session.execute(
                    select(ESGScore).where(
                        ESGScore.entity_id == entity_id,
                        ESGScore.provider == "SEC_EDGAR",
                        ESGScore.as_of_date == as_of_date,
                    )
                )
                if existing_score.scalar_one_or_none() is not None:
                    stats["skipped"] += 1
                    continue

                # Create ESGScore record (governance pillar only)
                gov_score = rec.get("governance_score")
                score = ESGScore(
                    score_id=uuid.uuid4(),
                    entity_id=entity_id,
                    provider="SEC_EDGAR",
                    as_of_date=as_of_date,
                    governance_score=Decimal(str(gov_score)) if gov_score is not None else None,
                    esg_rating=None,  # Governance-only; no composite rating
                )
                session.add(score)
                stats["inserted"] += 1

                # Create ESGMetric records
                for metric_data in rec.get("metrics", []):
                    metric = ESGMetric(
                        metric_id=uuid.uuid4(),
                        entity_id=entity_id,
                        metric_type=metric_data["metric_type"],
                        metric_category=metric_data.get("metric_category", "GOVERNANCE"),
                        period_end_date=as_of_date,
                        period_type="ANNUAL",
                        value=Decimal(str(metric_data["value"])) if metric_data.get("value") is not None else None,
                        unit=metric_data.get("unit"),
                        is_reported=True,
                        source=metric_data.get("source", "SEC_EDGAR"),
                    )
                    session.add(metric)
                    stats["inserted"] += 1

                await session.flush()

            except Exception as e:
                logger.error("Error loading ESG data for CIK %s: %s", rec.get("cik"), e)
                stats["errors"] += 1

        await session.flush()
        return stats

    # ------------------------------------------------------------------
    # Private extraction helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_board_size(text: str) -> int | None:
        """Extract board size from filing text."""
        match = _BOARD_SIZE_PATTERN.search(text)
        if match:
            try:
                return int(match.group(1))
            except ValueError:
                return None
        return None

    @staticmethod
    def _extract_board_independence(text: str) -> tuple[int | None, int | None]:
        """Extract count of independent directors / total directors."""
        match = _BOARD_INDEPENDENCE_PATTERN.search(text)
        if match:
            try:
                independent = int(match.group(1))
                total = int(match.group(2))
                if 0 < independent <= total <= 30:
                    return independent, total
            except ValueError:
                pass
        return None, None

    @staticmethod
    def _extract_female_directors(text: str) -> int | None:
        """Extract count of female directors from filing text."""
        match = _FEMALE_DIRECTOR_PATTERN.search(text)
        if match:
            try:
                count = int(match.group(1))
                if 0 < count <= 30:
                    return count
            except ValueError:
                return None
        return None

    @staticmethod
    def _extract_ceo_compensation(text: str) -> float | None:
        """Extract CEO total compensation figure from filing text."""
        match = _CEO_COMP_PATTERN.search(text)
        if match:
            try:
                raw = match.group(1).replace(",", "")
                value = float(raw)
                # Sanity check — CEO comp should be > $10K and < $1B
                if 10_000 < value < 1_000_000_000:
                    return value
            except ValueError:
                return None
        return None

    @staticmethod
    def _has_shareholder_proposals(text: str) -> bool:
        """Check if the filing contains shareholder proposals."""
        return bool(_SHAREHOLDER_PROPOSAL_PATTERN.search(text))

    async def close(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
