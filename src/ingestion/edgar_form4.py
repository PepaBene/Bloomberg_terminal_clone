"""SEC EDGAR Form 4 connector for insider transaction ingestion.

Fetches Form 4 (insider trading) filings from SEC EDGAR and creates
InsiderHolding records tracking insider buy/sell transactions.
"""

import logging
import uuid
import xml.etree.ElementTree as ET
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

SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
ARCHIVES_BASE_URL = "https://www.sec.gov/Archives/edgar/data"

# Form 4 transaction codes
TRANSACTION_CODES = {
    "P": "PURCHASE",
    "S": "SALE",
    "A": "GRANT",
    "D": "DISPOSITION_TO_ISSUER",
    "F": "TAX_WITHHOLDING",
    "M": "OPTION_EXERCISE",
    "G": "GIFT",
    "C": "CONVERSION",
    "E": "EXPIRATION",
    "X": "OPTION_EXERCISE_OOM",
    "W": "ACQUIRED_WILL",
    "I": "DISCRETIONARY",
    "J": "OTHER",
    "K": "EQUITY_SWAP",
    "U": "DISPOSITION_TENDER",
}


class EdgarForm4Connector(BaseConnector):
    """Ingest insider transactions from SEC EDGAR Form 4 filings."""

    name = "SEC EDGAR Form 4"
    connector_type = "BATCH_API"
    data_domain = "OWNERSHIP"

    def __init__(
        self,
        issuer_ciks: list[str] | None = None,
        days_back: int = 30,
        max_filings_per_cik: int = 50,
    ):
        """Initialize connector.

        Args:
            issuer_ciks: List of issuer CIK numbers to monitor for Form 4 filings.
            days_back: Number of days of history to look back.
            max_filings_per_cik: Maximum number of Form 4 filings to process per issuer.
        """
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
            self._client = httpx.AsyncClient(
                headers=self.headers, timeout=30.0
            )
        return self._client

    async def _fetch_submissions(self, cik: str) -> dict[str, Any] | None:
        """Fetch filing submissions for a single CIK."""
        padded_cik = cik.zfill(10)
        url = SUBMISSIONS_URL.format(cik=padded_cik)

        await self.rate_limiter.acquire()
        client = await self._get_client()

        try:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            logger.warning(f"Failed to fetch submissions for CIK {cik}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error fetching submissions for CIK {cik}: {e}")
            return None

    async def _fetch_form4_xml(self, cik: str, accession: str) -> str | None:
        """Fetch the Form 4 XML document for a specific filing."""
        accession_clean = accession.replace("-", "")
        cik_num = cik.lstrip("0")

        # Fetch the filing index to find the XML document
        index_url = f"{ARCHIVES_BASE_URL}/{cik_num}/{accession_clean}/index.json"

        await self.rate_limiter.acquire()
        client = await self._get_client()

        try:
            resp = await client.get(index_url)
            resp.raise_for_status()
            index_data = resp.json()
        except Exception as e:
            logger.warning(f"Failed to fetch filing index for {accession}: {e}")
            return None

        # Find the Form 4 XML document
        xml_doc = None
        directory = index_data.get("directory", {})
        items = directory.get("item", [])
        for item in items:
            name = item.get("name", "").lower()
            if name.endswith(".xml") and ("form4" in name or "doc4" in name or "primary_doc" in name):
                xml_doc = item["name"]
                break

        # Fallback: any XML file
        if xml_doc is None:
            for item in items:
                name = item.get("name", "").lower()
                if name.endswith(".xml") and "r" not in name:  # skip R files
                    xml_doc = item["name"]
                    break

        if xml_doc is None:
            logger.debug(f"No Form 4 XML found for {accession}")
            return None

        xml_url = f"{ARCHIVES_BASE_URL}/{cik_num}/{accession_clean}/{xml_doc}"

        await self.rate_limiter.acquire()

        try:
            resp = await client.get(xml_url)
            resp.raise_for_status()
            return resp.text
        except Exception as e:
            logger.warning(f"Failed to fetch Form 4 XML for {accession}: {e}")
            return None

    def _parse_form4_xml(self, xml_text: str) -> dict[str, Any]:
        """Parse Form 4 XML into structured data."""
        result: dict[str, Any] = {
            "issuer_cik": None,
            "issuer_name": None,
            "issuer_ticker": None,
            "insider_name": None,
            "insider_cik": None,
            "insider_title": None,
            "insider_relationship": None,
            "transactions": [],
        }

        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as e:
            logger.warning(f"Failed to parse Form 4 XML: {e}")
            return result

        # Issuer info
        issuer = root.find(".//issuer")
        if issuer is not None:
            cik_el = issuer.find("issuerCik")
            result["issuer_cik"] = cik_el.text.strip() if cik_el is not None and cik_el.text else None
            name_el = issuer.find("issuerName")
            result["issuer_name"] = name_el.text.strip() if name_el is not None and name_el.text else None
            ticker_el = issuer.find("issuerTradingSymbol")
            result["issuer_ticker"] = ticker_el.text.strip() if ticker_el is not None and ticker_el.text else None

        # Reporting owner info
        owner = root.find(".//reportingOwner")
        if owner is not None:
            owner_id = owner.find(".//reportingOwnerId")
            if owner_id is not None:
                name_el = owner_id.find("rptOwnerName")
                result["insider_name"] = name_el.text.strip() if name_el is not None and name_el.text else None
                cik_el = owner_id.find("rptOwnerCik")
                result["insider_cik"] = cik_el.text.strip() if cik_el is not None and cik_el.text else None

            relationship = owner.find(".//reportingOwnerRelationship")
            if relationship is not None:
                if relationship.find("isDirector") is not None:
                    dir_el = relationship.find("isDirector")
                    if dir_el is not None and dir_el.text and dir_el.text.strip() == "1":
                        result["insider_relationship"] = "DIRECTOR"
                if relationship.find("isOfficer") is not None:
                    officer_el = relationship.find("isOfficer")
                    if officer_el is not None and officer_el.text and officer_el.text.strip() == "1":
                        result["insider_relationship"] = "OFFICER"
                        title_el = relationship.find("officerTitle")
                        if title_el is not None and title_el.text:
                            result["insider_title"] = title_el.text.strip()
                if relationship.find("isTenPercentOwner") is not None:
                    ten_el = relationship.find("isTenPercentOwner")
                    if ten_el is not None and ten_el.text and ten_el.text.strip() == "1":
                        if result["insider_relationship"] is None:
                            result["insider_relationship"] = "TEN_PERCENT_OWNER"

        # Non-derivative transactions
        for txn in root.findall(".//nonDerivativeTransaction"):
            transaction = self._parse_transaction(txn)
            if transaction:
                result["transactions"].append(transaction)

        # Derivative transactions
        for txn in root.findall(".//derivativeTransaction"):
            transaction = self._parse_transaction(txn, is_derivative=True)
            if transaction:
                result["transactions"].append(transaction)

        return result

    def _parse_transaction(
        self, txn_element: ET.Element, is_derivative: bool = False
    ) -> dict[str, Any] | None:
        """Parse a single transaction element from Form 4 XML."""
        def _text(parent: ET.Element, tag: str) -> str | None:
            el = parent.find(f".//{tag}")
            return el.text.strip() if el is not None and el.text else None

        security_title = _text(txn_element, "securityTitle/value")
        transaction_date = _text(txn_element, "transactionDate/value")
        transaction_code = _text(txn_element, "transactionCoding/transactionCode")

        shares_str = _text(txn_element, "transactionAmounts/transactionShares/value")
        price_str = _text(txn_element, "transactionAmounts/transactionPricePerShare/value")
        acq_disp = _text(txn_element, "transactionAmounts/transactionAcquiredDisposedCode/value")

        shares_after_str = _text(txn_element, "postTransactionAmounts/sharesOwnedFollowingTransaction/value")

        ownership_nature = _text(txn_element, "ownershipNature/directOrIndirectOwnership/value")

        if not transaction_date:
            return None

        shares = None
        if shares_str:
            try:
                shares = float(shares_str)
            except ValueError:
                pass

        price = None
        if price_str:
            try:
                price = float(price_str)
                if price == 0:
                    price = None
            except ValueError:
                pass

        shares_after = None
        if shares_after_str:
            try:
                shares_after = float(shares_after_str)
            except ValueError:
                pass

        total_value = None
        if shares is not None and price is not None:
            total_value = shares * price

        # Map transaction code
        txn_type = TRANSACTION_CODES.get(transaction_code, "OTHER")

        return {
            "security_title": security_title,
            "transaction_date": transaction_date,
            "transaction_code": transaction_code,
            "transaction_type": txn_type,
            "shares_transacted": shares,
            "price_per_share": price,
            "total_value": total_value,
            "acquired_disposed": acq_disp,  # A = acquired, D = disposed
            "shares_owned_after": shares_after,
            "ownership_nature": ownership_nature,  # D = direct, I = indirect
            "is_derivative": is_derivative,
        }

    async def extract(self) -> list[dict[str, Any]]:
        """Pull Form 4 filing data from SEC EDGAR for configured issuer CIKs."""
        if not self.issuer_ciks:
            logger.warning("No issuer CIKs configured — skipping Form 4 extraction")
            return []

        records: list[dict[str, Any]] = []
        from datetime import timedelta
        cutoff_date = date.today() - timedelta(days=self.days_back)

        for cik in self.issuer_ciks:
            submissions = await self._fetch_submissions(cik)
            if submissions is None:
                continue

            entity_name = submissions.get("name", "")
            recent = submissions.get("filings", {}).get("recent", {})

            forms = recent.get("form", [])
            accession_numbers = recent.get("accessionNumber", [])
            filing_dates = recent.get("filingDate", [])

            form4_count = 0
            for i, form in enumerate(forms):
                if form not in ("4", "4/A"):
                    continue

                filing_date_str = filing_dates[i] if i < len(filing_dates) else ""
                try:
                    filing_date_val = date.fromisoformat(filing_date_str)
                    if filing_date_val < cutoff_date:
                        continue
                except (ValueError, TypeError):
                    continue

                accession = accession_numbers[i] if i < len(accession_numbers) else ""
                if not accession:
                    continue

                xml_text = await self._fetch_form4_xml(cik, accession)
                if xml_text is None:
                    continue

                parsed = self._parse_form4_xml(xml_text)
                parsed["accession_number"] = accession
                parsed["filing_date"] = filing_date_str
                records.append(parsed)

                form4_count += 1
                if form4_count >= self.max_filings_per_cik:
                    break

            logger.info(
                f"  Form 4: CIK {cik} ({entity_name}) — "
                f"{form4_count} Form 4 filings extracted"
            )

        return records

    async def validate(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Validate Form 4 records — ensure required fields are present."""
        valid = []
        for rec in records:
            if not rec.get("issuer_cik"):
                continue
            if not rec.get("insider_name"):
                continue
            if not rec.get("transactions"):
                continue

            # Filter out transactions with no date or shares
            clean_txns = [
                t for t in rec["transactions"]
                if t.get("transaction_date") and t.get("shares_transacted") is not None
            ]
            rec["transactions"] = clean_txns

            if clean_txns:
                valid.append(rec)
        return valid

    async def transform(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Transform Form 4 data into InsiderHolding records."""
        transformed = []

        for rec in records:
            issuer_cik = rec["issuer_cik"]
            insider_name = rec["insider_name"]
            insider_title = rec.get("insider_title")
            insider_relationship = rec.get("insider_relationship")

            for txn in rec["transactions"]:
                transformed.append({
                    "issuer_cik": issuer_cik,
                    "insider_name": insider_name,
                    "insider_title": insider_title,
                    "insider_relationship": insider_relationship,
                    "transaction_type": txn["transaction_type"],
                    "transaction_date": txn["transaction_date"],
                    "shares_transacted": txn.get("shares_transacted"),
                    "price_per_share": txn.get("price_per_share"),
                    "total_value": txn.get("total_value"),
                    "shares_owned_after": txn.get("shares_owned_after"),
                    "ownership_nature": txn.get("ownership_nature"),
                    "accession_number": rec.get("accession_number"),
                })

        logger.info(f"Transformed {len(transformed)} insider transaction records")
        return transformed

    async def load(
        self, records: list[dict[str, Any]], session: AsyncSession
    ) -> dict[str, int]:
        """Write insider transaction records to database."""
        from src.models.entity import EntityIdentifier
        from src.models.ownership import InsiderHolding
        from src.models.security import Security

        stats = {"inserted": 0, "updated": 0, "skipped": 0, "errors": 0}

        for rec in records:
            try:
                issuer_cik = rec["issuer_cik"]

                # Resolve entity_id from issuer CIK (CIK is an entity-level identifier)
                result = await session.execute(
                    select(EntityIdentifier).where(
                        EntityIdentifier.identifier_type == "CIK",
                        EntityIdentifier.identifier_value == issuer_cik,
                    )
                )
                entity_ident = result.scalar_one_or_none()
                entity_id = entity_ident.entity_id if entity_ident else None

                # Find the security associated with this entity
                security_id = None
                if entity_id is not None:
                    sec_result = await session.execute(
                        select(Security).where(
                            Security.issuer_entity_id == entity_id,
                        )
                    )
                    security = sec_result.scalars().first()
                    if security is not None:
                        security_id = security.security_id

                if security_id is None:
                    stats["skipped"] += 1
                    continue

                transaction_date_val = date.fromisoformat(rec["transaction_date"])

                # Check for duplicate
                existing = await session.execute(
                    select(InsiderHolding).where(
                        InsiderHolding.security_id == security_id,
                        InsiderHolding.insider_name == rec["insider_name"],
                        InsiderHolding.transaction_date == transaction_date_val,
                        InsiderHolding.transaction_type == rec["transaction_type"],
                    )
                )
                if existing.scalar_one_or_none() is not None:
                    stats["skipped"] += 1
                    continue

                holding = InsiderHolding(
                    transaction_id=uuid.uuid4(),
                    security_id=security_id,
                    entity_id=entity_id,
                    insider_name=rec["insider_name"],
                    insider_title=rec.get("insider_title"),
                    insider_relationship=rec.get("insider_relationship"),
                    transaction_type=rec["transaction_type"],
                    transaction_date=transaction_date_val,
                    shares_transacted=Decimal(str(rec["shares_transacted"])) if rec.get("shares_transacted") is not None else None,
                    price_per_share=Decimal(str(rec["price_per_share"])) if rec.get("price_per_share") is not None else None,
                    total_value=Decimal(str(rec["total_value"])) if rec.get("total_value") is not None else None,
                    shares_owned_after=Decimal(str(rec["shares_owned_after"])) if rec.get("shares_owned_after") is not None else None,
                    ownership_nature=rec.get("ownership_nature"),
                )
                session.add(holding)
                stats["inserted"] += 1

            except Exception as e:
                logger.error(f"Error loading Form 4 transaction: {e}")
                stats["errors"] += 1

        await session.flush()
        return stats

    async def close(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
