"""SEC EDGAR Form 4 connector for insider transaction ingestion.

Fetches Form 4 (insider trading) filings from SEC EDGAR and creates
InsiderHolding records tracking insider buy/sell transactions.
"""

import logging
import re
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
from src.ingestion.redis_rate_limiter import RedisRateLimiter

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
    # Synthetic code (not an official SEC transaction code) for a Form 3/5
    # <...Holding> element -- an initial/annual reported POSITION, not a
    # transaction. Previously these forms were skipped entirely (only Form
    # 4 "changes" were captured), so an insider's very first reported stake
    # was never recorded at all.
    "H": "INITIAL_HOLDING",
}

# Mapping of Form 4 transaction codes to the Pillar 3 `transaction_type`
# vocabulary consumed by the filing-intelligence API (BUY / SELL / EXERCISE / ...).
P3_TRANSACTION_TYPE = {
    "P": "BUY",
    "S": "SELL",
    "A": "GRANT",
    "M": "EXERCISE",
    "X": "EXERCISE",
    "C": "CONVERSION",
    "F": "TAX",
    "G": "GIFT",
    "D": "SELL",  # disposition to issuer
    "E": "EXPIRE",
    "W": "ACQUIRE",
    "K": "SWAP",
    "U": "SELL",
    "I": "OTHER",
    "J": "OTHER",
    "H": "INITIAL_HOLDING",  # synthetic Form 3/5 holding code, see TRANSACTION_CODES
}

# P3 transaction types that represent shares flowing TO the insider (positive net).
_ACQUIRE_TYPES = {"BUY", "GRANT", "EXERCISE", "CONVERSION", "ACQUIRE"}


def _normalize_cik(cik: str | None) -> str | None:
    """Normalize a CIK to the unpadded form stored in entity_identifiers.

    Form 4 XML reports zero-padded 10-digit CIKs (e.g. ``0000320193``) whereas
    ``entity_identifiers.identifier_value`` stores them unpadded (``320193``).
    """
    if not cik:
        return None
    stripped = cik.strip().lstrip("0")
    return stripped or "0"


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
        self.rate_limiter = RedisRateLimiter(key="sec_edgar", max_requests=settings.SEC_RATE_LIMIT, per_seconds=1.0)
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

        # Find the ownership XML document (shared schema across Form 3/4/5).
        # Filenames vary: modern filings use "primary_doc.xml" or
        # "form4.xml"/"doc4.xml"; many Form 3/5 filings (and older Form 4s)
        # instead use a plain "ownership.xml".
        xml_doc = None
        directory = index_data.get("directory", {})
        items = directory.get("item", [])
        for item in items:
            name = item.get("name", "").lower()
            if name.endswith(".xml") and (
                "form4" in name or "doc4" in name or "primary_doc" in name or "ownership" in name
            ):
                xml_doc = item["name"]
                break

        # Fallback: any XML file that isn't an XBRL viewer "R<n>.xml"
        # rendering artifact. The old bare "r" not in name check also
        # excluded legitimate files like "ownership.xml" (contains "r").
        if xml_doc is None:
            for item in items:
                name = item.get("name", "").lower()
                if name.endswith(".xml") and not re.match(r"^r\d+\.xml$", name):
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
                def _flag(tag: str) -> bool:
                    # SEC filers use either "1" or "true" for boolean flags.
                    el = relationship.find(tag)
                    return el is not None and el.text is not None and el.text.strip().lower() in ("1", "true")

                if _flag("isDirector"):
                    result["insider_relationship"] = "DIRECTOR"
                if _flag("isOfficer"):
                    result["insider_relationship"] = "OFFICER"
                    title_el = relationship.find("officerTitle")
                    if title_el is not None and title_el.text:
                        result["insider_title"] = title_el.text.strip()
                if _flag("isTenPercentOwner") and result["insider_relationship"] is None:
                    result["insider_relationship"] = "TEN_PERCENT_OWNER"

        period_el = root.find(".//periodOfReport")
        period_of_report = period_el.text.strip() if period_el is not None and period_el.text else None

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

        # Form 3 (initial ownership) and, often, Form 5 (annual) carry no
        # transactions at all -- just a reported POSITION as of the filing.
        # These live in <nonDerivativeHolding>/<derivativeHolding>, a
        # sibling element to *Transaction with no transactionDate of its
        # own, so periodOfReport substitutes as the as-of date.
        for holding in root.findall(".//nonDerivativeHolding"):
            parsed = self._parse_holding(holding, period_of_report)
            if parsed:
                result["transactions"].append(parsed)

        for holding in root.findall(".//derivativeHolding"):
            parsed = self._parse_holding(holding, period_of_report, is_derivative=True)
            if parsed:
                result["transactions"].append(parsed)

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

    def _parse_holding(
        self, holding_element: ET.Element, period_of_report: str | None,
        is_derivative: bool = False,
    ) -> dict[str, Any] | None:
        """Parse a Form 3/5 <...Holding> element -- a reported position, not a
        transaction. No transactionDate exists on a holding, so
        periodOfReport (the filing's as-of date) substitutes for it."""
        def _text(parent: ET.Element, tag: str) -> str | None:
            el = parent.find(f".//{tag}")
            return el.text.strip() if el is not None and el.text else None

        if not period_of_report:
            return None

        security_title = _text(holding_element, "securityTitle/value")
        shares_str = _text(holding_element, "postTransactionAmounts/sharesOwnedFollowingTransaction/value")
        ownership_nature = _text(holding_element, "ownershipNature/directOrIndirectOwnership/value")

        shares = None
        if shares_str:
            try:
                shares = float(shares_str)
            except ValueError:
                pass

        return {
            "security_title": security_title,
            "transaction_date": period_of_report,
            "transaction_code": "H",
            "transaction_type": "INITIAL_HOLDING",
            "shares_transacted": None,
            "price_per_share": None,
            "total_value": None,
            "acquired_disposed": None,
            "shares_owned_after": shares,
            "ownership_nature": ownership_nature,
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
                # Form 3 = initial ownership, Form 4 = changes, Form 5 =
                # annual/exempt. All three share the same ownershipDocument
                # XML schema. Form 3/5 previously silently skipped entirely.
                if form not in ("3", "3/A", "4", "4/A", "5", "5/A"):
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
            insider_cik = rec.get("insider_cik")
            insider_title = rec.get("insider_title")
            insider_relationship = rec.get("insider_relationship")
            accession = rec.get("accession_number")

            for txn in rec["transactions"]:
                transaction_code = txn.get("transaction_code")
                ownership_nature = txn.get("ownership_nature")
                transformed.append({
                    "issuer_cik": issuer_cik,
                    "insider_name": insider_name,
                    "insider_cik": insider_cik,
                    "insider_title": insider_title,
                    "insider_relationship": insider_relationship,
                    # transaction_type keeps the InsiderHolding vocabulary
                    # (PURCHASE/SALE/...) for backwards compatibility.
                    "transaction_type": txn["transaction_type"],
                    # p3_transaction_type is the API vocabulary (BUY/SELL/...).
                    "p3_transaction_type": P3_TRANSACTION_TYPE.get(
                        transaction_code, "OTHER"
                    ),
                    "transaction_code": transaction_code,
                    "acquired_disposed": txn.get("acquired_disposed"),
                    "is_derivative": txn.get("is_derivative", False),
                    "transaction_date": txn["transaction_date"],
                    "shares_transacted": txn.get("shares_transacted"),
                    "price_per_share": txn.get("price_per_share"),
                    "total_value": txn.get("total_value"),
                    "shares_owned_after": txn.get("shares_owned_after"),
                    "ownership_nature": ownership_nature,
                    "is_open_market": transaction_code in ("P", "S"),
                    "is_direct_ownership": ownership_nature != "I",
                    "accession_number": accession,
                    "filing_date": rec.get("filing_date"),
                })

        logger.info(f"Transformed {len(transformed)} insider transaction records")
        return transformed

    async def load(
        self, records: list[dict[str, Any]], session: AsyncSession
    ) -> dict[str, int]:
        """Write insider transactions to `insider_holdings` and `insider_transactions_p3`.

        `insider_holdings` (Domain 6) is keyed on a security and is written only
        when a matching Security exists. `insider_transactions_p3` (Pillar 3) is
        keyed on the issuer entity and is written whenever the issuer CIK resolves
        to an entity. After the per-record loads, aggregated `insider_signals`
        rows are computed for every entity that received new transactions.
        """
        from src.models.entity import EntityIdentifier
        from src.models.insider_intelligence import InsiderTransactionP3
        from src.models.ownership import InsiderHolding
        from src.models.security import Security

        stats = {
            "inserted": 0,
            "updated": 0,
            "skipped": 0,
            "errors": 0,
            "p3_inserted": 0,
            "p3_skipped": 0,
            "signals_upserted": 0,
        }

        # Cache CIK -> (entity_id, security_id) resolutions across records.
        resolution_cache: dict[str, tuple[Any, Any]] = {}
        touched_entities: set[Any] = set()

        for rec in records:
            try:
                # SAVEPOINT per record: a single bad transaction (a share count or
                # value that overflows its numeric column, an over-long string)
                # otherwise aborts the shared session and every later record — and
                # every other data type in the pass — dies with PendingRollbackError
                # via autoflush. begin_nested() isolates the failure to this record.
                async with session.begin_nested():
                    issuer_cik = rec["issuer_cik"]
                    lookup_cik = _normalize_cik(issuer_cik)

                    if lookup_cik in resolution_cache:
                        entity_id, security_id = resolution_cache[lookup_cik]
                    else:
                        result = await session.execute(
                            select(EntityIdentifier).where(
                                EntityIdentifier.identifier_type == "CIK",
                                EntityIdentifier.identifier_value == lookup_cik,
                            )
                        )
                        entity_ident = result.scalar_one_or_none()
                        entity_id = entity_ident.entity_id if entity_ident else None

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
                        resolution_cache[lookup_cik] = (entity_id, security_id)

                    # No entity means nothing can be written for this record.
                    if entity_id is None:
                        stats["skipped"] += 1
                        stats["p3_skipped"] += 1
                        continue

                    transaction_date_val = date.fromisoformat(rec["transaction_date"])

                    # --- insider_holdings (requires a security) ---
                    if security_id is not None:
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
                        else:
                            session.add(InsiderHolding(
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
                            ))
                            stats["inserted"] += 1

                    # --- insider_transactions_p3 (requires only an entity) ---
                    shares_dec = (
                        Decimal(str(rec["shares_transacted"]))
                        if rec.get("shares_transacted") is not None else None
                    )
                    # Natural key: entity + person + date + code + shares.
                    p3_existing = await session.execute(
                        select(InsiderTransactionP3.id).where(
                            InsiderTransactionP3.entity_id == entity_id,
                            InsiderTransactionP3.reporting_person == rec["insider_name"],
                            InsiderTransactionP3.transaction_date == transaction_date_val,
                            InsiderTransactionP3.transaction_code == rec.get("transaction_code"),
                            InsiderTransactionP3.shares == shares_dec,
                        )
                    )
                    if p3_existing.first() is not None:
                        stats["p3_skipped"] += 1
                    else:
                        filing_date_val = None
                        if rec.get("filing_date"):
                            try:
                                filing_date_val = date.fromisoformat(rec["filing_date"])
                            except (ValueError, TypeError):
                                filing_date_val = None

                        filing_url = None
                        accession = rec.get("accession_number")
                        if accession and lookup_cik:
                            acc_clean = accession.replace("-", "")
                            filing_url = (
                                f"{ARCHIVES_BASE_URL}/{lookup_cik}/{acc_clean}/"
                                f"{accession}-index.htm"
                            )[:500]

                        session.add(InsiderTransactionP3(
                            entity_id=entity_id,
                            reporting_person=rec["insider_name"][:200],
                            reporting_person_cik=(rec.get("insider_cik") or None) if rec.get("insider_cik") else None,
                            relationship=(rec.get("insider_relationship") or "UNKNOWN")[:30],
                            transaction_type=rec["p3_transaction_type"][:20],
                            transaction_code=rec.get("transaction_code"),
                            transaction_date=transaction_date_val,
                            shares=shares_dec,
                            price_per_share=Decimal(str(rec["price_per_share"])) if rec.get("price_per_share") is not None else None,
                            total_value=Decimal(str(rec["total_value"])) if rec.get("total_value") is not None else None,
                            shares_owned_after=Decimal(str(rec["shares_owned_after"])) if rec.get("shares_owned_after") is not None else None,
                            is_open_market=bool(rec.get("is_open_market", False)),
                            is_10b5_1=False,  # not reliably present in Form 4 ownership XML
                            is_direct_ownership=bool(rec.get("is_direct_ownership", True)),
                            filing_date=filing_date_val,
                            filing_url=filing_url,
                        ))
                        stats["p3_inserted"] += 1
                        touched_entities.add(entity_id)

                    # Surface any overflow/truncation now, inside this record's
                    # savepoint, instead of via a later record's autoflush.
                    await session.flush()

            except Exception as e:
                logger.error(f"Error loading Form 4 transaction: {e}")
                stats["errors"] += 1

        await session.flush()

        # Compute aggregated insider signals for entities with new transactions.
        for entity_id in touched_entities:
            try:
                upserted = await self._compute_signal(session, entity_id)
                stats["signals_upserted"] += upserted
            except Exception as e:
                logger.error(f"Error computing insider signal for {entity_id}: {e}")
                stats["errors"] += 1

        await session.flush()
        return stats

    async def _compute_signal(self, session: AsyncSession, entity_id: Any) -> int:
        """Compute and upsert an `insider_signals` row for one entity.

        Aggregates all `insider_transactions_p3` rows for the entity over trailing
        30/90/365-day windows (relative to today) into net share/value flows and
        insider counts, then classifies the entity's signal.
        """
        from datetime import timedelta

        from src.models.insider_intelligence import InsiderSignal, InsiderTransactionP3

        today = date.today()
        cutoff_365 = today - timedelta(days=365)

        result = await session.execute(
            select(InsiderTransactionP3).where(
                InsiderTransactionP3.entity_id == entity_id,
                InsiderTransactionP3.transaction_date >= cutoff_365,
            )
        )
        txns = result.scalars().all()
        if not txns:
            return 0

        def _signed_shares(t: "InsiderTransactionP3") -> Decimal:
            shares = t.shares or Decimal(0)
            return shares if t.transaction_type in _ACQUIRE_TYPES else -shares

        def _signed_value(t: "InsiderTransactionP3") -> Decimal:
            value = t.total_value or Decimal(0)
            return value if t.transaction_type in _ACQUIRE_TYPES else -value

        windows = {
            30: today - timedelta(days=30),
            90: today - timedelta(days=90),
            365: cutoff_365,
        }
        net_shares = {w: Decimal(0) for w in windows}
        net_value = {w: Decimal(0) for w in windows}
        for t in txns:
            s = _signed_shares(t)
            v = _signed_value(t)
            for w, cutoff in windows.items():
                if t.transaction_date >= cutoff:
                    net_shares[w] += s
                    net_value[w] += v

        open_market_buys_90d = sum(
            1 for t in txns
            if t.is_open_market and t.transaction_type == "BUY"
            and t.transaction_date >= windows[90]
        )
        buyers_30d = {
            t.reporting_person for t in txns
            if t.transaction_date >= windows[30]
            and t.transaction_type in _ACQUIRE_TYPES
        }
        sellers_30d = {
            t.reporting_person for t in txns
            if t.transaction_date >= windows[30]
            and t.transaction_type not in _ACQUIRE_TYPES
        }

        # Classify signal from 90-day net value + open-market buying breadth.
        nv90 = net_value[90]
        if open_market_buys_90d >= 2 and len(buyers_30d) >= 2 and nv90 > 0:
            signal_type = "CLUSTER_BUY"
        elif nv90 > 0:
            signal_type = "NET_BUYING"
        elif nv90 < 0:
            signal_type = "NET_SELLING"
        else:
            signal_type = "NEUTRAL"

        # Strength 0-100 scaled by |net value| (log-ish) + open-market breadth.
        magnitude = abs(float(nv90))
        strength = min(100, int(magnitude / 1_000_000 * 10) + open_market_buys_90d * 10)

        detail = {
            "net_shares_30d": float(net_shares[30]),
            "net_shares_90d": float(net_shares[90]),
            "net_shares_365d": float(net_shares[365]),
            "net_value_30d": float(net_value[30]),
            "net_value_90d": float(net_value[90]),
            "net_value_365d": float(net_value[365]),
            "open_market_buy_count_90d": open_market_buys_90d,
            "insider_count_buying_30d": len(buyers_30d),
            "insider_count_selling_30d": len(sellers_30d),
            "transaction_count_365d": len(txns),
        }

        # Upsert on (entity_id, signal_date, signal_type).
        existing = await session.execute(
            select(InsiderSignal).where(
                InsiderSignal.entity_id == entity_id,
                InsiderSignal.signal_date == today,
                InsiderSignal.signal_type == signal_type,
            )
        )
        signal = existing.scalar_one_or_none()
        if signal is None:
            signal = InsiderSignal(
                entity_id=entity_id,
                signal_date=today,
                signal_type=signal_type,
            )
            session.add(signal)

        signal.signal_strength = strength
        signal.net_shares_30d = net_shares[30]
        signal.net_value_30d = net_value[30]
        signal.net_shares_90d = net_shares[90]
        signal.net_value_90d = net_value[90]
        signal.net_shares_365d = net_shares[365]
        signal.net_value_365d = net_value[365]
        signal.open_market_buy_count_90d = open_market_buys_90d
        signal.insider_count_buying_30d = len(buyers_30d)
        signal.insider_count_selling_30d = len(sellers_30d)
        signal.detail = detail
        return 1

    async def close(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
