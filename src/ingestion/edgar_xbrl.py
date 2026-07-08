"""SEC EDGAR XBRL connector for company fundamentals ingestion.

Fetches XBRL JSON from the SEC company facts API and maps US-GAAP tags
to our standardized IncomeStatement, BalanceSheet, and CashFlowStatement models.
"""

import logging
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
from src.ingestion.xbrl_taxonomy import (
    BALANCE_SHEET_MAP,
    CASH_FLOW_MAP,
    INCOME_STATEMENT_MAP,
)

logger = logging.getLogger(__name__)

COMPANY_FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"


class EdgarXBRLConnector(BaseConnector):
    """Ingest financial statements from SEC EDGAR XBRL company facts API."""

    name = "SEC EDGAR XBRL"
    connector_type = "BATCH_API"
    data_domain = "FUNDAMENTALS"

    def __init__(self, ciks: list[str] | None = None):
        """Initialize connector.

        Args:
            ciks: List of CIK numbers to fetch. If None, must be set before extract().
        """
        self.ciks = ciks or []
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

    async def _fetch_company_facts(self, cik: str) -> dict[str, Any] | None:
        """Fetch XBRL company facts for a single CIK."""
        padded_cik = cik.zfill(10)
        url = COMPANY_FACTS_URL.format(cik=padded_cik)

        await self.rate_limiter.acquire()
        client = await self._get_client()

        try:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            logger.warning(f"Failed to fetch XBRL for CIK {cik}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error fetching XBRL for CIK {cik}: {e}")
            return None

    async def extract(self) -> list[dict[str, Any]]:
        """Pull XBRL company facts from SEC EDGAR for all configured CIKs."""
        if not self.ciks:
            logger.warning("No CIKs configured — skipping XBRL extraction")
            return []

        records: list[dict[str, Any]] = []

        for cik in self.ciks:
            data = await self._fetch_company_facts(cik)
            if data is None:
                continue

            entity_name = data.get("entityName", "")
            cik_value = str(data.get("cik", cik))
            facts = data.get("facts", {})
            us_gaap = facts.get("us-gaap", {})

            if not us_gaap:
                logger.info(f"  XBRL: No US-GAAP facts for CIK {cik}")
                continue

            records.append({
                "cik": cik_value,
                "entity_name": entity_name,
                "us_gaap_facts": us_gaap,
            })
            logger.info(
                f"  XBRL: CIK {cik} ({entity_name}) — "
                f"{len(us_gaap)} US-GAAP concepts"
            )

        return records

    async def validate(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Validate XBRL records — ensure required fields are present."""
        valid = []
        for rec in records:
            if not rec.get("cik"):
                logger.debug("Skipping record with missing CIK")
                continue
            if not rec.get("us_gaap_facts"):
                logger.debug(f"Skipping CIK {rec['cik']}: no US-GAAP facts")
                continue
            valid.append(rec)
        return valid

    def _extract_period_values(
        self, us_gaap: dict[str, Any], tag_map: dict[str, str]
    ) -> dict[str, dict[str, Any]]:
        """Extract values grouped by period end date from XBRL facts.

        Returns:
            Dict keyed by (period_end_date, form_type) -> {field_name: value, ...}
        """
        period_data: dict[str, dict[str, Any]] = {}

        for xbrl_tag, field_name in tag_map.items():
            # Tags in company facts omit the namespace prefix
            concept_key = xbrl_tag.split(":")[-1] if ":" in xbrl_tag else xbrl_tag
            concept = us_gaap.get(concept_key)
            if concept is None:
                continue

            units = concept.get("units", {})
            # Most financial values are in USD or shares
            for unit_key, entries in units.items():
                for entry in entries:
                    end_date = entry.get("end")
                    form = entry.get("form", "")
                    val = entry.get("val")

                    if end_date is None or val is None:
                        continue

                    # Only process 10-K and 10-Q filings
                    if form not in ("10-K", "10-Q", "10-K/A", "10-Q/A"):
                        continue

                    period_key = f"{end_date}|{form.replace('/A', '')}"
                    if period_key not in period_data:
                        period_data[period_key] = {
                            "_end_date": end_date,
                            "_form": form,
                            "_start_date": entry.get("start"),
                            "_accession": entry.get("accn", ""),
                            "_filed": entry.get("filed", ""),
                            "_fiscal_year": entry.get("fy"),
                            "_fiscal_quarter": entry.get("fp"),
                        }

                    # Only set if not already set (first-seen wins for duplicates)
                    if field_name not in period_data[period_key]:
                        period_data[period_key][field_name] = float(val)

        return period_data

    async def transform(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Transform XBRL data into structured financial statement records."""
        transformed = []

        for rec in records:
            cik = rec["cik"]
            entity_name = rec["entity_name"]
            us_gaap = rec["us_gaap_facts"]

            # Extract period values for each statement type
            income_periods = self._extract_period_values(us_gaap, INCOME_STATEMENT_MAP)
            balance_periods = self._extract_period_values(us_gaap, BALANCE_SHEET_MAP)
            cashflow_periods = self._extract_period_values(us_gaap, CASH_FLOW_MAP)

            # Collect all unique period keys
            all_period_keys = set(income_periods.keys()) | set(balance_periods.keys()) | set(cashflow_periods.keys())

            for period_key in all_period_keys:
                income = income_periods.get(period_key, {})
                balance = balance_periods.get(period_key, {})
                cashflow = cashflow_periods.get(period_key, {})

                # Get metadata from whichever statement has it
                meta = {}
                for stmt in (income, balance, cashflow):
                    for key in ("_end_date", "_form", "_start_date", "_accession",
                                "_filed", "_fiscal_year", "_fiscal_quarter"):
                        if key in stmt and key not in meta:
                            meta[key] = stmt[key]

                end_date = meta.get("_end_date")
                if not end_date:
                    continue

                form = meta.get("_form", "10-K")
                period_type = "ANNUAL" if "10-K" in form else "QUARTERLY"
                fiscal_quarter_raw = meta.get("_fiscal_quarter", "")
                fiscal_quarter = None
                if fiscal_quarter_raw and fiscal_quarter_raw not in ("FY",):
                    try:
                        fiscal_quarter = int(fiscal_quarter_raw.replace("Q", ""))
                    except (ValueError, AttributeError):
                        pass

                # Strip metadata keys from statement dicts
                income_fields = {k: v for k, v in income.items() if not k.startswith("_")}
                balance_fields = {k: v for k, v in balance.items() if not k.startswith("_")}
                cashflow_fields = {k: v for k, v in cashflow.items() if not k.startswith("_")}

                # dividends_paid follows a cash-outflow sign convention in the
                # schema (CHECK dividends_paid <= 0); XBRL reports it as a
                # positive magnitude, so normalize it to non-positive.
                if cashflow_fields.get("dividends_paid") is not None:
                    try:
                        cashflow_fields["dividends_paid"] = -abs(float(cashflow_fields["dividends_paid"]))
                    except (TypeError, ValueError):
                        cashflow_fields.pop("dividends_paid", None)

                # Skip periods with no actual data
                if not income_fields and not balance_fields and not cashflow_fields:
                    continue

                transformed.append({
                    "cik": cik,
                    "entity_name": entity_name,
                    "filing": {
                        "filing_type": form.replace("/A", ""),
                        "accession_number": meta.get("_accession", ""),
                        "filing_date": meta.get("_filed", end_date),
                        "period_end_date": end_date,
                        "fiscal_year": meta.get("_fiscal_year"),
                        "fiscal_quarter": fiscal_quarter,
                        "period_type": period_type,
                        "is_amendment": "/A" in (meta.get("_form", "") or ""),
                    },
                    "period": {
                        "period_start_date": meta.get("_start_date"),
                        "period_end_date": end_date,
                        "period_type": period_type,
                        "fiscal_year": meta.get("_fiscal_year"),
                        "fiscal_quarter": fiscal_quarter,
                        "accounting_standard": "US-GAAP",
                        "data_version": "AS_REPORTED",
                    },
                    "income_statement": income_fields,
                    "balance_sheet": balance_fields,
                    "cash_flow": cashflow_fields,
                })

        logger.info(f"Transformed {len(transformed)} financial period records")
        return transformed

    async def load(
        self, records: list[dict[str, Any]], session: AsyncSession
    ) -> dict[str, int]:
        """Write financial statements to database."""
        from src.models.entity import EntityIdentifier
        from src.models.fundamentals import (
            BalanceSheet,
            CashFlowStatement,
            Filing,
            FinancialPeriod,
            IncomeStatement,
        )

        stats = {"inserted": 0, "updated": 0, "skipped": 0, "errors": 0}

        # Within-run dedup: the same period_end is reported across multiple
        # filings (as comparatives), and one filing backs several periods.
        seen_periods: set[tuple] = set()
        seen_filings: dict[str, uuid.UUID] = {}

        for rec in records:
            try:
                cik = rec["cik"]

                # Resolve entity_id from CIK
                result = await session.execute(
                    select(EntityIdentifier).where(
                        EntityIdentifier.identifier_type == "CIK",
                        EntityIdentifier.identifier_value == cik,
                    )
                )
                entity_ident = result.scalar_one_or_none()
                if entity_ident is None:
                    logger.debug(f"No entity found for CIK {cik} — skipping")
                    stats["skipped"] += 1
                    continue

                entity_id = entity_ident.entity_id

                filing_data = rec["filing"]
                period_data = rec["period"]

                # Parse dates
                filing_date = date.fromisoformat(filing_data["filing_date"])
                period_end = date.fromisoformat(filing_data["period_end_date"])
                fiscal_year = filing_data.get("fiscal_year")
                if fiscal_year is None:
                    fiscal_year = period_end.year

                accession = filing_data.get("accession_number", "")
                if not accession:
                    stats["skipped"] += 1
                    continue

                # Dedup the financial period (uq_financial_period is on
                # entity_id + period_end_date + data_version). The same period
                # is reported across multiple filings, so skip the record if we
                # already captured this period this run or it's already in the DB.
                period_key = (entity_id, period_end, "AS_REPORTED")
                if period_key in seen_periods:
                    stats["skipped"] += 1
                    continue
                existing_period = await session.execute(
                    select(FinancialPeriod.period_id).where(
                        FinancialPeriod.entity_id == entity_id,
                        FinancialPeriod.period_end_date == period_end,
                        FinancialPeriod.data_version == "AS_REPORTED",
                    )
                )
                if existing_period.scalar_one_or_none() is not None:
                    seen_periods.add(period_key)
                    stats["skipped"] += 1
                    continue

                # Reuse or create the filing (one filing can back several periods).
                filing_id = seen_filings.get(accession)
                if filing_id is None:
                    existing_filing = (
                        await session.execute(
                            select(Filing.filing_id).where(
                                Filing.accession_number == accession
                            )
                        )
                    ).scalar_one_or_none()
                    if existing_filing is not None:
                        filing_id = existing_filing
                    else:
                        filing_id = uuid.uuid4()
                        session.add(Filing(
                            filing_id=filing_id,
                            entity_id=entity_id,
                            filing_type=filing_data["filing_type"],
                            accession_number=accession,
                            filing_date=filing_date,
                            period_end_date=period_end,
                            fiscal_year=fiscal_year,
                            fiscal_quarter=filing_data.get("fiscal_quarter"),
                            period_type=filing_data.get("period_type"),
                            is_amendment=filing_data.get("is_amendment", False),
                            processing_status="PROCESSED",
                            processed_at=datetime.now(timezone.utc),
                            source="SEC_EDGAR_XBRL",
                        ))
                    seen_filings[accession] = filing_id

                # Create FinancialPeriod
                period_start = None
                if period_data.get("period_start_date"):
                    period_start = date.fromisoformat(period_data["period_start_date"])

                period_id = uuid.uuid4()
                period = FinancialPeriod(
                    period_id=period_id,
                    entity_id=entity_id,
                    filing_id=filing_id,
                    period_start_date=period_start,
                    period_end_date=period_end,
                    period_type=period_data.get("period_type", "ANNUAL"),
                    fiscal_year=fiscal_year,
                    fiscal_quarter=period_data.get("fiscal_quarter"),
                    reporting_currency="USD",
                    accounting_standard="US-GAAP",
                    data_version="AS_REPORTED",
                )
                session.add(period)
                seen_periods.add(period_key)

                # Create IncomeStatement if we have data
                income_fields = rec.get("income_statement", {})
                if income_fields:
                    stmt = IncomeStatement(
                        statement_id=uuid.uuid4(),
                        period_id=period_id,
                        **{k: Decimal(str(v)) for k, v in income_fields.items()},
                    )
                    session.add(stmt)

                # Create BalanceSheet if we have data
                balance_fields = rec.get("balance_sheet", {})
                if balance_fields:
                    stmt = BalanceSheet(
                        statement_id=uuid.uuid4(),
                        period_id=period_id,
                        **{k: Decimal(str(v)) for k, v in balance_fields.items()},
                    )
                    session.add(stmt)

                # Create CashFlowStatement if we have data
                cashflow_fields = rec.get("cash_flow", {})
                if cashflow_fields:
                    stmt = CashFlowStatement(
                        statement_id=uuid.uuid4(),
                        period_id=period_id,
                        **{k: Decimal(str(v)) for k, v in cashflow_fields.items()},
                    )
                    session.add(stmt)

                stats["inserted"] += 1
                await session.flush()

            except Exception as e:
                logger.error(f"Error loading XBRL record: {e}")
                stats["errors"] += 1

        await session.flush()
        return stats

    async def close(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
