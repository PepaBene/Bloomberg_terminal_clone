"""Capital Structure extraction from SEC EDGAR 10-K filings (Pillar 1 Supplement §2).

Parses debt footnotes from XBRL filings to extract individual debt tranches,
their terms, and seniority hierarchy. Builds a complete CapitalStructure
snapshot per filing.
"""

import logging
import re
from datetime import date
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.ingestion.base import BaseConnector
from src.ingestion.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)

# XBRL tags that contain debt disclosure information
DEBT_XBRL_TAGS = [
    "us-gaap:LongTermDebtTextBlock",
    "us-gaap:DebtDisclosureTextBlock",
    "us-gaap:LongTermDebtNoncurrent",
    "us-gaap:ShortTermBorrowings",
    "us-gaap:ConvertibleNotesPayable",
    "us-gaap:SubordinatedBorrowings",
    "us-gaap:LineOfCredit",
    "us-gaap:CapitalLeaseObligations",
]

# Keyword patterns for seniority classification
SENIORITY_PATTERNS = {
    "SENIOR_SECURED": ["senior secured", "first lien", "collateralized"],
    "SENIOR_UNSECURED": ["senior unsecured", "senior notes", "senior debentures"],
    "SUBORDINATED": ["subordinated", "junior", "mezzanine"],
    "JUNIOR_SUBORDINATED": ["junior subordinated"],
}

# Instrument type patterns
INSTRUMENT_TYPE_PATTERNS = {
    "REVOLVING_CREDIT_FACILITY": ["revolving credit", "revolving facility", "revolver"],
    "TERM_LOAN_A": ["term loan a", "term a loan"],
    "TERM_LOAN_B": ["term loan b", "term b loan"],
    "CONVERTIBLE_NOTES": ["convertible", "conversion rate", "conversion price"],
    "CAPITAL_LEASE_OBLIGATION": ["capital lease", "finance lease"],
    "COMMERCIAL_PAPER": ["commercial paper"],
    "PREFERRED_STOCK": ["preferred stock", "preferred shares"],
}

# Validation thresholds
VALIDATION_RULES = {
    "sum_tolerance": 0.05,  # Sum of tranches within 5% of reported total
    "max_coupon": 0.25,     # Maximum reasonable coupon rate (25%)
}


def classify_seniority(text: str) -> str:
    """Classify debt seniority from instrument description text."""
    lower = text.lower()
    # Check most specific patterns first
    for seniority, patterns in SENIORITY_PATTERNS.items():
        for pattern in patterns:
            if pattern in lower:
                return seniority
    return "SENIOR_UNSECURED"  # default


def classify_instrument_type(text: str) -> str:
    """Classify instrument type from description text."""
    lower = text.lower()
    for inst_type, patterns in INSTRUMENT_TYPE_PATTERNS.items():
        for pattern in patterns:
            if pattern in lower:
                return inst_type
    # Fallback to notes detection
    if "note" in lower:
        seniority = classify_seniority(text)
        if seniority == "SENIOR_SECURED":
            return "SENIOR_SECURED_NOTES"
        elif seniority == "SUBORDINATED":
            return "SUBORDINATED_NOTES"
        return "SENIOR_UNSECURED_NOTES"
    return "OTHER"


def extract_coupon_rate(text: str) -> float | None:
    """Extract coupon rate from instrument name like '4.875% Senior Notes'."""
    match = re.search(r"(\d+\.?\d*)\s*%", text)
    if match:
        rate = float(match.group(1)) / 100.0
        if 0 < rate < VALIDATION_RULES["max_coupon"]:
            return rate
    return None


def extract_maturity_year(text: str) -> int | None:
    """Extract maturity year from text like 'due 2028' or 'maturing 2030'."""
    match = re.search(r"(?:due|matur\w*)\s+(\d{4})", text, re.IGNORECASE)
    if match:
        year = int(match.group(1))
        if 2000 <= year <= 2100:
            return year
    return None


class EdgarCapitalStructureConnector(BaseConnector):
    """Extract capital structure data from SEC EDGAR 10-K/10-Q filings."""

    name = "SEC EDGAR Capital Structure"
    connector_type = "BATCH_API"
    data_domain = "CAPITAL_STRUCTURE"

    def __init__(self, ciks: list[str] | None = None):
        self.ciks = ciks or []
        self.rate_limiter = RateLimiter(
            max_requests=settings.SEC_RATE_LIMIT, per_seconds=1.0
        )

    async def extract(self) -> list[dict[str, Any]]:
        """Extract debt disclosure text blocks from XBRL filings."""
        if not self.ciks:
            logger.warning("No CIKs configured — skipping capital structure extraction")
            return []

        records: list[dict[str, Any]] = []
        # In production this would fetch XBRL filings from EDGAR and parse
        # debt footnote text blocks. For now, return empty — the connector
        # skeleton is ready for the parsing logic to be wired in.
        logger.info("Capital structure extraction: %d CIKs queued", len(self.ciks))
        return records

    async def validate(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Validate extracted capital structure records."""
        valid = []
        for rec in records:
            if not rec.get("entity_id"):
                continue
            if not rec.get("as_of_date"):
                continue
            valid.append(rec)
        return valid

    async def transform(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Transform raw debt data into CapitalStructure + DebtTranche records."""
        transformed = []
        for rec in records:
            # Classify each tranche
            tranches = rec.get("tranches", [])
            for tranche in tranches:
                name = tranche.get("instrument_name", "")
                if not tranche.get("instrument_type"):
                    tranche["instrument_type"] = classify_instrument_type(name)
                if not tranche.get("seniority_type"):
                    tranche["seniority_type"] = classify_seniority(name)
                if not tranche.get("coupon_rate") and name:
                    tranche["coupon_rate"] = extract_coupon_rate(name)

            rec["tranches"] = tranches
            transformed.append(rec)
        return transformed

    async def load(
        self, records: list[dict[str, Any]], session: AsyncSession
    ) -> dict[str, int]:
        """Load capital structure records into the database."""
        stats = {"inserted": 0, "updated": 0, "skipped": 0, "errors": 0}

        for rec in records:
            try:
                from src.models.capital_structure import CapitalStructure, DebtTranche

                cs = CapitalStructure(
                    entity_id=rec["entity_id"],
                    as_of_date=rec["as_of_date"],
                    filing_id=rec.get("filing_id"),
                    total_debt=rec.get("total_debt"),
                    total_long_term_debt=rec.get("total_long_term_debt"),
                    total_short_term_debt=rec.get("total_short_term_debt"),
                    net_debt=rec.get("net_debt"),
                    total_capitalization=rec.get("total_capitalization"),
                    debt_to_capitalization=rec.get("debt_to_capitalization"),
                    source=rec.get("source", "SEC_10K"),
                    extraction_method=rec.get("extraction_method", "XBRL_STRUCTURED"),
                    confidence_score=rec.get("confidence_score"),
                )
                session.add(cs)
                await session.flush()

                for tranche_data in rec.get("tranches", []):
                    maturity_year = extract_maturity_year(
                        tranche_data.get("instrument_name", "")
                    )
                    maturity_date_val = None
                    if maturity_year:
                        maturity_date_val = date(maturity_year, 12, 31)

                    tranche = DebtTranche(
                        entity_id=rec["entity_id"],
                        capital_structure_id=cs.capital_structure_id,
                        instrument_name=tranche_data.get("instrument_name"),
                        instrument_type=tranche_data.get("instrument_type"),
                        principal_amount=tranche_data.get("principal_amount"),
                        coupon_rate=tranche_data.get("coupon_rate"),
                        coupon_type=tranche_data.get("coupon_type", "FIXED"),
                        maturity_date=tranche_data.get("maturity_date", maturity_date_val),
                        seniority_type=tranche_data.get("seniority_type"),
                    )
                    session.add(tranche)

                stats["inserted"] += 1
            except Exception as e:
                logger.error("Error loading capital structure: %s", e)
                stats["errors"] += 1

        return stats
