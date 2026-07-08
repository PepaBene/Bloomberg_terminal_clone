"""SEC EDGAR N-PORT fund-holdings connector.

Funds (ETFs, mutual funds) disclose their full portfolio monthly on Form
N-PORT (public quarterly). The N-PORT XML carries fund-level identity/assets
plus one ``invstOrSec`` element per holding (name, CUSIP/ISIN, balance, USD
value, % of NAV). This connector fetches N-PORT-P filings for a fund's CIK,
parses the XML and writes ``Fund`` + ``FundHolding`` rows.

The XML parse (namespace-agnostic), transform and DB load are implemented and
unit-tested against a small representative N-PORT sample.

FLAG — needs-live-data-validation:
    Real N-PORT documents are large and their exact element layout varies by
    filer/version. The parser matches on element *local names* to be robust,
    but it should be validated against a spread of live N-PORT filings (and the
    N-PORT-P index-document lookup confirmed) before production use.
"""

from __future__ import annotations

import logging
import uuid
import xml.etree.ElementTree as ET
from datetime import date
from decimal import Decimal, InvalidOperation
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
NPORT_FORMS = ("NPORT-P", "NPORT-P/A")


def _local(tag: str) -> str:
    """Strip an XML namespace from a tag, returning the local name."""
    return tag.rsplit("}", 1)[-1]


def _find(elem: ET.Element | None, name: str) -> ET.Element | None:
    if elem is None:
        return None
    for child in elem.iter():
        if _local(child.tag) == name:
            return child
    return None


def _find_direct(elem: ET.Element, name: str) -> ET.Element | None:
    for child in elem:
        if _local(child.tag) == name:
            return child
    return None


def _text(elem: ET.Element | None, name: str) -> str | None:
    found = _find(elem, name)
    if found is not None and found.text and found.text.strip():
        return found.text.strip()
    return None


def _to_decimal(value: str | None) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(value)
    except (InvalidOperation, ValueError):
        return None


def parse_nport_xml(xml_text: str) -> dict[str, Any] | None:
    """Parse an N-PORT XML document into fund + holdings dicts.

    Namespace-agnostic (matches on local element names). Pure (no I/O) —
    directly unit-testable. Returns None if no holdings are found.
    """
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:  # pragma: no cover - defensive
        logger.warning("Failed to parse N-PORT XML: %s", exc)
        return None

    gen_info = _find(root, "genInfo")
    fund_info = _find(root, "fundInfo")

    fund = {
        "fund_name": _text(gen_info, "seriesName") or _text(gen_info, "regName"),
        "series_id": _text(gen_info, "seriesId"),
        "report_date": _text(gen_info, "repPdDate") or _text(gen_info, "repPdEnd"),
        "total_net_assets": _to_decimal(_text(fund_info, "totAssets")),
    }

    holdings: list[dict[str, Any]] = []
    invst_container = _find(root, "invstOrSecs")
    if invst_container is not None:
        for sec in invst_container:
            if _local(sec.tag) != "invstOrSec":
                continue
            isin_el = _find(sec, "isin")
            isin = isin_el.get("value") if isin_el is not None else None
            if isin is None:
                isin = _text(sec, "isin")
            holdings.append(
                {
                    "security_name": _text(sec, "name"),
                    "cusip": _text(sec, "cusip"),
                    "isin": isin,
                    "quantity": _to_decimal(_text(sec, "balance")),
                    "market_value": _to_decimal(_text(sec, "valUSD")),
                    "pct_of_nav": _to_decimal(_text(sec, "pctVal")),
                    "asset_type": _text(sec, "assetCat"),
                }
            )

    if not holdings:
        return None

    fund["number_of_holdings"] = len(holdings)
    return {"fund": fund, "holdings": holdings}


class EdgarNportFundsConnector(BaseConnector):
    """Ingest fund holdings from SEC EDGAR N-PORT filings."""

    name = "SEC EDGAR N-PORT"
    connector_type = "BATCH_API"
    data_domain = "OWNERSHIP"

    def __init__(self, fund_ciks: list[str] | None = None, days_back: int = 120):
        self.fund_ciks = fund_ciks or []
        self.days_back = days_back
        self.rate_limiter = RateLimiter(max_requests=settings.SEC_RATE_LIMIT, per_seconds=1.0)
        self.headers = {"User-Agent": settings.SEC_USER_AGENT}
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(headers=self.headers, timeout=60.0)
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

    async def _fetch_nport_xml(self, cik: str, accession: str) -> str | None:
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
            logger.warning("Failed to fetch N-PORT index for %s: %s", accession, exc)
            return None
        xml_doc = None
        for item in items:
            name = item.get("name", "").lower()
            if name in ("primary_doc.xml",) or (name.endswith(".xml") and "nport" in name):
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
            logger.warning("Failed to fetch N-PORT XML for %s: %s", accession, exc)
            return None

    async def extract(self) -> list[dict[str, Any]]:
        if not self.fund_ciks:
            logger.warning("No fund CIKs configured — skipping N-PORT extraction")
            return []
        from datetime import timedelta

        cutoff = date.today() - timedelta(days=self.days_back)
        records: list[dict[str, Any]] = []
        for cik in self.fund_ciks:
            submissions = await self._fetch_submissions(cik)
            if submissions is None:
                continue
            recent = submissions.get("filings", {}).get("recent", {})
            forms = recent.get("form", [])
            accessions = recent.get("accessionNumber", [])
            filed = recent.get("filingDate", [])
            for i, form in enumerate(forms):
                if form not in NPORT_FORMS:
                    continue
                filing_date_str = filed[i] if i < len(filed) else ""
                try:
                    if date.fromisoformat(filing_date_str) < cutoff:
                        continue
                except (ValueError, TypeError):
                    continue
                accession = accessions[i] if i < len(accessions) else ""
                xml_text = await self._fetch_nport_xml(cik, accession)
                if xml_text is None:
                    continue
                parsed = parse_nport_xml(xml_text)
                if parsed is None:
                    continue
                parsed["cik"] = cik
                parsed["accession_number"] = accession
                records.append(parsed)
        return records

    async def validate(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        valid = []
        for r in records:
            fund = r.get("fund", {})
            if not fund.get("fund_name"):
                continue
            if not fund.get("report_date"):
                continue
            if not r.get("holdings"):
                continue
            valid.append(r)
        return valid

    async def transform(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Normalize parsed N-PORT docs into Fund + FundHolding field dicts."""
        out: list[dict[str, Any]] = []
        for r in records:
            fund = dict(r["fund"])
            fund["cik"] = r.get("cik")
            out.append(
                {
                    "fund": fund,
                    "holdings": r["holdings"],
                    "report_date": fund.get("report_date"),
                    "accession_number": r.get("accession_number"),
                }
            )
        return out

    async def load(
        self, records: list[dict[str, Any]], session: AsyncSession
    ) -> dict[str, int]:
        from src.models.entity import EntityIdentifier
        from src.models.fund_holdings import Fund, FundHolding

        stats = {"inserted": 0, "updated": 0, "skipped": 0, "errors": 0}
        if getattr(self, "dry_run", False):
            return stats

        for rec in records:
            try:
                fund_data = rec["fund"]
                cik = fund_data.get("cik")
                report_date = date.fromisoformat(rec["report_date"])
                accession = rec.get("accession_number")

                # Optionally resolve entity_id from the fund CIK.
                entity_id = None
                if cik:
                    ident = (
                        await session.execute(
                            select(EntityIdentifier).where(
                                EntityIdentifier.identifier_type == "CIK",
                                EntityIdentifier.identifier_value == cik,
                            )
                        )
                    ).scalar_one_or_none()
                    entity_id = ident.entity_id if ident else None

                # Upsert the fund by CIK + name (CIK alone may host many series).
                fund = (
                    await session.execute(
                        select(Fund).where(
                            Fund.cik == cik,
                            Fund.fund_name == fund_data["fund_name"],
                        )
                    )
                ).scalar_one_or_none()
                if fund is None:
                    fund = Fund(
                        fund_id=uuid.uuid4(),
                        entity_id=entity_id,
                        fund_name=fund_data["fund_name"],
                        series_id=fund_data.get("series_id"),
                        cik=cik,
                        total_net_assets=fund_data.get("total_net_assets"),
                        number_of_holdings=fund_data.get("number_of_holdings"),
                    )
                    session.add(fund)
                    await session.flush()
                    stats["updated"] += 0  # fund creation counted via holdings
                else:
                    fund.total_net_assets = fund_data.get("total_net_assets")
                    fund.number_of_holdings = fund_data.get("number_of_holdings")

                for h in rec["holdings"]:
                    # Dedupe holdings by fund + report_date + cusip/name.
                    existing = (
                        await session.execute(
                            select(FundHolding).where(
                                FundHolding.fund_id == fund.fund_id,
                                FundHolding.report_date == report_date,
                                FundHolding.cusip == h.get("cusip"),
                                FundHolding.security_name == h.get("security_name"),
                            )
                        )
                    ).scalar_one_or_none()
                    if existing is not None:
                        stats["skipped"] += 1
                        continue
                    session.add(
                        FundHolding(
                            holding_id=uuid.uuid4(),
                            fund_id=fund.fund_id,
                            report_date=report_date,
                            security_name=h.get("security_name"),
                            cusip=h.get("cusip"),
                            isin=h.get("isin"),
                            quantity=h.get("quantity"),
                            market_value=h.get("market_value"),
                            pct_of_nav=h.get("pct_of_nav"),
                            asset_type=(h.get("asset_type") or None),
                            nport_accession=accession[:25] if accession else None,
                        )
                    )
                    stats["inserted"] += 1

                await session.flush()
            except Exception:  # pragma: no cover - defensive
                logger.exception("[%s] failed to load N-PORT record", self.name)
                stats["errors"] += 1

        await session.flush()
        return stats

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None
