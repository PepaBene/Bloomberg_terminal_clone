"""SEC EDGAR 13F-HR connector for institutional holdings ingestion.

Fetches 13F-HR (institutional investment manager) filings from SEC EDGAR
and creates InstitutionProfile + InstitutionalHolding records.
"""

import asyncio
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
from src.ingestion.redis_rate_limiter import RedisRateLimiter

logger = logging.getLogger(__name__)

SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
ARCHIVES_BASE_URL = "https://www.sec.gov/Archives/edgar/data"

# XML namespaces used in 13F filings
NS_13F = {
    "ns": "http://www.sec.gov/edgar/document/thirteenf/informationtable",
}


class Edgar13FConnector(BaseConnector):
    """Ingest institutional holdings from SEC EDGAR 13F-HR filings."""

    name = "SEC EDGAR 13F"
    connector_type = "BATCH_API"
    data_domain = "OWNERSHIP"

    def __init__(
        self,
        ciks: list[str] | None = None,
        max_filings_per_cik: int = 1,
        concurrency: int = 8,
    ):
        """Initialize connector.

        Args:
            ciks: List of institutional investor CIKs to fetch.
            max_filings_per_cik: Max number of recent 13F filings to process per CIK.
            concurrency: Max CIKs processed concurrently. Each CIK still makes its
                requests one at a time and every request still goes through the
                same shared ``rate_limiter``, so this can't push the aggregate
                request rate past SEC_RATE_LIMIT -- it just lets one CIK's network
                wait overlap with another's, instead of the whole pipeline sitting
                idle on a single response before the rate limiter even gets a
                chance to release the next token.
        """
        self.ciks = ciks or []
        self.max_filings_per_cik = max_filings_per_cik
        self.concurrency = concurrency
        self.rate_limiter = RedisRateLimiter(key="sec_edgar", max_requests=settings.SEC_RATE_LIMIT, per_seconds=1.0)
        self.headers = {"User-Agent": settings.SEC_USER_AGENT}
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                headers=self.headers, timeout=60.0
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

    async def _fetch_13f_xml(self, cik: str, accession: str) -> str | None:
        """Fetch the 13F information table XML for a specific filing."""
        accession_clean = accession.replace("-", "")
        cik_num = cik.lstrip("0")

        # The information table is typically named with 'infotable' in the filename
        # First fetch the filing index to find the info table document
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

        # Find the information table document
        info_table_doc = None
        directory = index_data.get("directory", {})
        items = directory.get("item", [])
        for item in items:
            name = item.get("name", "").lower()
            if "infotable" in name and name.endswith(".xml"):
                info_table_doc = item["name"]
                break

        if info_table_doc is None:
            # Try alternative naming patterns
            for item in items:
                name = item.get("name", "").lower()
                if name.endswith(".xml") and "13f" in name:
                    info_table_doc = item["name"]
                    break

        if info_table_doc is None:
            logger.debug(f"No information table found for {accession}")
            return None

        # Fetch the info table XML
        xml_url = f"{ARCHIVES_BASE_URL}/{cik_num}/{accession_clean}/{info_table_doc}"

        await self.rate_limiter.acquire()

        try:
            resp = await client.get(xml_url)
            resp.raise_for_status()
            return resp.text
        except Exception as e:
            logger.warning(f"Failed to fetch 13F XML for {accession}: {e}")
            return None

    def _parse_13f_xml(self, xml_text: str) -> list[dict[str, Any]]:
        """Parse 13F information table XML into holding records."""
        holdings = []

        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as e:
            logger.warning(f"Failed to parse 13F XML: {e}")
            return []

        # Try with namespace and without
        info_tables = root.findall(".//ns:infoTable", NS_13F)
        if not info_tables:
            # Try without namespace
            info_tables = root.findall(".//{*}infoTable")
        if not info_tables:
            info_tables = root.findall(".//infoTable")

        for entry in info_tables:
            def _text(tag: str) -> str | None:
                """Extract text from a tag, trying with and without namespace."""
                el = entry.find(f"ns:{tag}", NS_13F)
                if el is None:
                    el = entry.find(f"{{*}}{tag}")
                if el is None:
                    el = entry.find(tag)
                return el.text.strip() if el is not None and el.text else None

            name_of_issuer = _text("nameOfIssuer")
            title_of_class = _text("titleOfClass")
            cusip = _text("cusip")
            value_str = _text("value")  # in thousands
            shares_str = None

            # Shares are nested under shrsOrPrnAmt
            shrs_el = entry.find("ns:shrsOrPrnAmt", NS_13F)
            if shrs_el is None:
                shrs_el = entry.find("{*}shrsOrPrnAmt")
            if shrs_el is None:
                shrs_el = entry.find("shrsOrPrnAmt")

            if shrs_el is not None:
                sh_amt = shrs_el.find("ns:sshPrnamt", NS_13F)
                if sh_amt is None:
                    sh_amt = shrs_el.find("{*}sshPrnamt")
                if sh_amt is None:
                    sh_amt = shrs_el.find("sshPrnamt")
                if sh_amt is not None and sh_amt.text:
                    shares_str = sh_amt.text.strip()

            investment_discretion = _text("investmentDiscretion")
            put_call = _text("putCall")

            # Sole/Shared/None are nested under votingAuthority, not direct
            # children of infoTable -- must search within that element.
            voting_el = entry.find("ns:votingAuthority", NS_13F)
            if voting_el is None:
                voting_el = entry.find("{*}votingAuthority")
            if voting_el is None:
                voting_el = entry.find("votingAuthority")

            def _voting_text(tag: str) -> str | None:
                if voting_el is None:
                    return None
                el = voting_el.find(f"ns:{tag}", NS_13F)
                if el is None:
                    el = voting_el.find(f"{{*}}{tag}")
                if el is None:
                    el = voting_el.find(tag)
                return el.text.strip() if el is not None and el.text else None

            voting_sole = _voting_text("Sole")
            voting_shared = _voting_text("Shared")
            voting_none = _voting_text("None")

            # Parse numeric values
            market_value = None
            if value_str:
                try:
                    market_value = float(value_str) * 1000  # Reported in thousands
                except ValueError:
                    pass

            shares = None
            if shares_str:
                try:
                    shares = float(shares_str)
                except ValueError:
                    pass

            def _voting_float(s: str | None) -> float | None:
                if not s:
                    return None
                try:
                    return float(s)
                except ValueError:
                    return None

            holdings.append({
                "name_of_issuer": name_of_issuer,
                "title_of_class": title_of_class,
                "cusip": cusip,
                "market_value": market_value,
                "shares": shares,
                "investment_discretion": investment_discretion,
                "put_call": put_call,
                "voting_sole": _voting_float(voting_sole),
                "voting_shared": _voting_float(voting_shared),
                "voting_none": _voting_float(voting_none),
            })

        return holdings

    async def _process_cik(self, cik: str) -> list[dict[str, Any]]:
        """Fetch + parse the configured 13F filings for a single CIK."""
        cik_records: list[dict[str, Any]] = []

        submissions = await self._fetch_submissions(cik)
        if submissions is None:
            return cik_records

        entity_name = submissions.get("name", "")
        recent = submissions.get("filings", {}).get("recent", {})

        forms = recent.get("form", [])
        accession_numbers = recent.get("accessionNumber", [])
        filing_dates = recent.get("filingDate", [])
        report_dates = recent.get("reportDate", [])

        filings_13f = []
        for i, form in enumerate(forms):
            if form not in ("13F-HR", "13F-HR/A"):
                continue
            filings_13f.append({
                "accession": accession_numbers[i] if i < len(accession_numbers) else "",
                "filing_date": filing_dates[i] if i < len(filing_dates) else "",
                "report_date": report_dates[i] if i < len(report_dates) else "",
                "form": form,
            })
            if len(filings_13f) >= self.max_filings_per_cik:
                break

        for filing in filings_13f:
            xml_text = await self._fetch_13f_xml(cik, filing["accession"])
            if xml_text is None:
                continue

            holdings = self._parse_13f_xml(xml_text)

            cik_records.append({
                "cik": cik,
                "institution_name": entity_name,
                "accession": filing["accession"],
                "filing_date": filing["filing_date"],
                "report_date": filing["report_date"],
                "form": filing["form"],
                "holdings": holdings,
            })
            logger.info(
                f"  13F: CIK {cik} ({entity_name}) — "
                f"{len(holdings)} holdings in {filing['report_date']}"
            )

        return cik_records

    async def extract(self) -> list[dict[str, Any]]:
        """Pull 13F filing data from SEC EDGAR for all configured CIKs.

        CIKs are processed with bounded concurrency rather than one at a time:
        every HTTP call, from any concurrent CIK task, still goes through the
        same shared ``rate_limiter`` before firing, so the aggregate request
        rate can't exceed SEC_RATE_LIMIT. What concurrency buys is overlap --
        while one task is waiting on a response, another can already be
        making progress, instead of the whole pipeline idling on one
        round-trip at a time.
        """
        if not self.ciks:
            logger.warning("No CIKs configured — skipping 13F extraction")
            return []

        semaphore = asyncio.Semaphore(self.concurrency)

        async def _bounded(cik: str) -> list[dict[str, Any]]:
            async with semaphore:
                return await self._process_cik(cik)

        results = await asyncio.gather(*(_bounded(cik) for cik in self.ciks))
        return [rec for cik_records in results for rec in cik_records]

    async def validate(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Validate 13F records — ensure required fields are present."""
        valid = []
        for rec in records:
            if not rec.get("cik"):
                continue
            if not rec.get("institution_name"):
                continue
            if not rec.get("holdings"):
                logger.debug(f"Skipping 13F for CIK {rec['cik']}: no holdings data")
                continue

            # Filter out holdings with missing CUSIP
            clean_holdings = [
                h for h in rec["holdings"]
                if h.get("cusip")
            ]
            rec["holdings"] = clean_holdings

            if clean_holdings:
                valid.append(rec)
        return valid

    async def transform(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Transform 13F data into our internal format."""
        transformed = []

        for rec in records:
            institution = {
                "cik": rec["cik"],
                "institution_name": rec["institution_name"],
                "number_of_holdings": len(rec["holdings"]),
                "aum": sum(
                    h.get("market_value", 0) or 0
                    for h in rec["holdings"]
                ),
            }

            holdings = []
            for h in rec["holdings"]:
                holdings.append({
                    "cusip": h["cusip"],
                    "name_of_issuer": h.get("name_of_issuer"),
                    "shares_held": h.get("shares"),
                    "market_value": h.get("market_value"),
                    "report_date": rec.get("report_date", rec.get("filing_date")),
                    "filing_date": rec.get("filing_date"),
                    "investment_discretion": h.get("investment_discretion"),
                    "put_call": h.get("put_call"),
                    "voting_sole": h.get("voting_sole"),
                    "voting_shared": h.get("voting_shared"),
                    "voting_none": h.get("voting_none"),
                })

            transformed.append({
                "institution": institution,
                "holdings": holdings,
            })

        logger.info(f"Transformed {len(transformed)} institutional holder records")
        return transformed

    async def load(
        self, records: list[dict[str, Any]], session: AsyncSession
    ) -> dict[str, int]:
        """Write institutional profiles and holdings to database."""
        from src.models.ownership import InstitutionalHolding, InstitutionProfile
        from src.models.security import SecurityIdentifier

        stats = {"inserted": 0, "updated": 0, "skipped": 0, "errors": 0}

        for rec in records:
            try:
                inst_data = rec["institution"]
                cik = inst_data["cik"]

                # Upsert InstitutionProfile
                result = await session.execute(
                    select(InstitutionProfile).where(
                        InstitutionProfile.cik == cik
                    )
                )
                institution = result.scalar_one_or_none()

                if institution is None:
                    institution = InstitutionProfile(
                        institution_id=uuid.uuid4(),
                        cik=cik,
                        institution_name=inst_data["institution_name"],
                        number_of_holdings=inst_data.get("number_of_holdings"),
                        aum=Decimal(str(inst_data["aum"])) if inst_data.get("aum") else None,
                    )
                    session.add(institution)
                    await session.flush()
                    stats["inserted"] += 1
                else:
                    institution.institution_name = inst_data["institution_name"]
                    institution.number_of_holdings = inst_data.get("number_of_holdings")
                    if inst_data.get("aum"):
                        institution.aum = Decimal(str(inst_data["aum"]))
                    stats["updated"] += 1

                # Load holdings
                for holding_data in rec.get("holdings", []):
                    try:
                        cusip = holding_data["cusip"]
                        report_date_str = holding_data.get("report_date")
                        if not report_date_str:
                            stats["skipped"] += 1
                            continue

                        report_date_val = date.fromisoformat(report_date_str)

                        # Resolve security_id from CUSIP
                        sec_result = await session.execute(
                            select(SecurityIdentifier).where(
                                SecurityIdentifier.identifier_type == "CUSIP",
                                SecurityIdentifier.identifier_value == cusip,
                            )
                        )
                        sec_ident = sec_result.scalar_one_or_none()
                        if sec_ident is None:
                            stats["skipped"] += 1
                            continue

                        security_id = sec_ident.security_id

                        # Check for duplicate
                        existing = await session.execute(
                            select(InstitutionalHolding).where(
                                InstitutionalHolding.institution_id == institution.institution_id,
                                InstitutionalHolding.security_id == security_id,
                                InstitutionalHolding.report_date == report_date_val,
                            )
                        )
                        if existing.scalar_one_or_none() is not None:
                            stats["skipped"] += 1
                            continue

                        filing_date_val = None
                        if holding_data.get("filing_date"):
                            filing_date_val = date.fromisoformat(holding_data["filing_date"])

                        holding = InstitutionalHolding(
                            institution_id=institution.institution_id,
                            security_id=security_id,
                            report_date=report_date_val,
                            filing_date=filing_date_val,
                            shares_held=Decimal(str(holding_data["shares_held"])) if holding_data.get("shares_held") else None,
                            market_value=Decimal(str(holding_data["market_value"])) if holding_data.get("market_value") else None,
                            source="SEC_EDGAR_13F",
                            investment_discretion=holding_data.get("investment_discretion"),
                            put_call=holding_data.get("put_call"),
                            voting_sole=Decimal(str(holding_data["voting_sole"])) if holding_data.get("voting_sole") is not None else None,
                            voting_shared=Decimal(str(holding_data["voting_shared"])) if holding_data.get("voting_shared") is not None else None,
                            voting_none=Decimal(str(holding_data["voting_none"])) if holding_data.get("voting_none") is not None else None,
                        )
                        session.add(holding)
                        stats["inserted"] += 1

                    except Exception as e:
                        logger.debug(f"    Skip holding: {e}")
                        stats["errors"] += 1

                await session.flush()

            except Exception as e:
                logger.error(f"Error loading 13F record for CIK {rec.get('institution', {}).get('cik')}: {e}")
                stats["errors"] += 1

        await session.flush()
        return stats

    async def close(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
