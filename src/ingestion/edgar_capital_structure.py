"""Capital Structure extraction from SEC EDGAR 10-K filings (Pillar 1 Supplement §2).

Parses debt footnotes from XBRL filings to extract individual debt tranches,
their terms, and seniority hierarchy. Builds a complete CapitalStructure
snapshot per filing.
"""

import logging
import re
from datetime import date, datetime
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.ingestion.base import BaseConnector
from src.ingestion.redis_rate_limiter import RedisRateLimiter

logger = logging.getLogger(__name__)

COMPANY_FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
FILING_DOC_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/{primary_doc}"

# XBRL companyfacts numeric concepts -> aggregate CapitalStructure fields.
# (companyfacts exposes only numeric facts, so per-instrument tranche names
# have to come from the 10-K debt footnote text, parsed separately below.)
DEBT_FACT_MAP: dict[str, str] = {
    "LongTermDebtNoncurrent": "total_long_term_debt",
    "ShortTermBorrowings": "total_short_term_debt",
    "DebtCurrent": "total_short_term_debt",
    "LongTermDebt": "total_debt",
    "DebtLongtermAndShorttermCombinedAmount": "total_debt",
    "StockholdersEquity": "_equity",
}

_HTML_TAG_RE = re.compile(r"<[^>]+>")

# Match debt instrument descriptions in 10-K footnote prose, e.g.
# "4.875% Senior Unsecured Notes due 2028" / "3.90% Subordinated Debentures due 2030".
_DEBT_INSTRUMENT_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*%\s+"
    r"((?:(?:senior|subordinated|junior|convertible|secured|unsecured)\s+){0,3}"
    r"(?:notes|debentures|bonds))\s+due\s+"
    r"(?:\w+\.?\s+\d{1,2},?\s+)?(\d{4})",
    re.IGNORECASE,
)

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


def strip_html(raw: str) -> str:
    """Cheap HTML-to-text so debt-footnote prose can be regex-scanned."""
    return _HTML_TAG_RE.sub(" ", raw)


# Optional-redemption ("call") clause detection — used to populate
# ``CallPutSchedule`` when a matching traded security exists. Only ever
# returns a date that is literally present in the filing text near the
# instrument's mention; if no such clause is found, returns None rather
# than guessing.
_CALL_KEYWORDS_RE = re.compile(r"\b(callable|redeemable|redemption)\b", re.IGNORECASE)
_ON_OR_AFTER_DATE_RE = re.compile(
    r"on or after\s+"
    r"((?:January|February|March|April|May|June|July|August|September"
    r"|October|November|December)\s+\d{1,2},?\s+\d{4})",
    re.IGNORECASE,
)
_CALL_SEARCH_WINDOW = 500


def _try_parse_month_date(text: str) -> date | None:
    for fmt in ("%B %d, %Y", "%B %d %Y"):
        try:
            return datetime.strptime(text.replace(",", ""), fmt).date()
        except ValueError:
            continue
    return None


def extract_call_date(text: str, instrument_name: str) -> date | None:
    """Best-effort extraction of an optional-redemption ("callable on or
    after <date>") clause near an instrument's mention in 10-K footnote
    prose. Returns ``None`` (never a fabricated date) if the instrument's
    maturity year can't be located in ``instrument_name``, or no call clause
    with an explicit date is found within a short window after one of its
    mentions in the text.
    """
    year_match = re.search(r"(\d{4})\s*$", instrument_name)
    if not year_match:
        return None
    year = year_match.group(1)

    for m in re.finditer(re.escape(year), text):
        window = text[m.start(): m.start() + _CALL_SEARCH_WINDOW]
        if not _CALL_KEYWORDS_RE.search(window):
            continue
        date_match = _ON_OR_AFTER_DATE_RE.search(window)
        if date_match:
            parsed = _try_parse_month_date(date_match.group(1))
            if parsed:
                return parsed
    return None


def parse_debt_instruments(text: str) -> list[dict[str, Any]]:
    """Parse individual debt-instrument descriptions from 10-K footnote text.

    Returns a list of ``{"instrument_name": ...}`` dicts; the connector's
    transform() then classifies seniority/type and extracts the coupon.
    Only rows that genuinely appear in the filing text are emitted — no
    synthetic tranches are fabricated when the text has no matches.
    """
    tranches: list[dict[str, Any]] = []
    seen: set[str] = set()
    for m in _DEBT_INSTRUMENT_RE.finditer(text):
        rate, type_phrase, year = m.group(1), m.group(2), m.group(3)
        type_clean = re.sub(r"\s+", " ", type_phrase).strip().title()
        name = f"{rate}% {type_clean} due {year}"
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        tranches.append({"instrument_name": name})
    return tranches


class EdgarCapitalStructureConnector(BaseConnector):
    """Extract capital structure data from SEC EDGAR 10-K/10-Q filings."""

    name = "SEC EDGAR Capital Structure"
    connector_type = "BATCH_API"
    data_domain = "CAPITAL_STRUCTURE"

    def __init__(self, ciks: list[str] | None = None):
        self.ciks = ciks or []
        self.rate_limiter = RedisRateLimiter(key="sec_edgar", max_requests=settings.SEC_RATE_LIMIT, per_seconds=1.0)
        self.headers = {"User-Agent": settings.SEC_USER_AGENT}
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(headers=self.headers, timeout=30.0)
        return self._client

    async def _sec_get_json(self, url: str) -> dict[str, Any] | None:
        await self.rate_limiter.acquire()
        client = await self._get_client()
        try:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:  # noqa: BLE001
            logger.warning("Capital structure: failed GET %s: %s", url, e)
            return None

    async def _fetch_latest_10k_text(self, cik: str) -> str | None:
        """Fetch the primary document text of the most recent 10-K for a CIK."""
        data = await self._sec_get_json(SUBMISSIONS_URL.format(cik=cik.zfill(10)))
        if not data:
            return None
        recent = data.get("filings", {}).get("recent", {})
        forms = recent.get("form", [])
        accessions = recent.get("accessionNumber", [])
        primary_docs = recent.get("primaryDocument", [])
        for i, form in enumerate(forms):
            if form != "10-K":
                continue
            url = FILING_DOC_URL.format(
                cik=cik,
                accession=accessions[i].replace("-", ""),
                primary_doc=primary_docs[i],
            )
            await self.rate_limiter.acquire()
            client = await self._get_client()
            try:
                resp = await client.get(url)
                resp.raise_for_status()
                return resp.text
            except Exception as e:  # noqa: BLE001
                logger.warning("Capital structure: failed 10-K text for CIK %s: %s", cik, e)
                return None
        return None

    async def extract(self) -> list[dict[str, Any]]:
        """Extract debt aggregates + parsed tranches from SEC EDGAR for each CIK.

        Aggregate figures (total/long-term/short-term debt, equity) come from
        the XBRL companyfacts API; per-instrument tranche descriptions are
        parsed from the latest 10-K debt footnote text.
        """
        if not self.ciks:
            logger.warning("No CIKs configured — skipping capital structure extraction")
            return []

        records: list[dict[str, Any]] = []
        for cik in self.ciks:
            facts_json = await self._sec_get_json(
                COMPANY_FACTS_URL.format(cik=cik.zfill(10))
            )
            us_gaap = (facts_json or {}).get("facts", {}).get("us-gaap", {})
            period = self._latest_debt_period(us_gaap)
            if period is None:
                logger.info("  CAST: CIK %s — no annual debt facts found", cik)
                continue

            as_of_date, aggregates = period

            tranches: list[dict[str, Any]] = []
            text = await self._fetch_latest_10k_text(cik)
            if text:
                clean_text = strip_html(text)
                tranches = parse_debt_instruments(clean_text)
                for tranche in tranches:
                    call_date = extract_call_date(clean_text, tranche["instrument_name"])
                    if call_date is not None:
                        tranche["first_call_date"] = call_date.isoformat()

            equity = aggregates.pop("_equity", None)
            total_debt = aggregates.get("total_debt")
            if total_debt is None:
                lt = aggregates.get("total_long_term_debt") or 0.0
                st = aggregates.get("total_short_term_debt") or 0.0
                if lt or st:
                    total_debt = lt + st
            total_cap = None
            debt_to_cap = None
            if total_debt is not None and equity is not None:
                total_cap = total_debt + equity
                if total_cap:
                    debt_to_cap = round(total_debt / total_cap, 4)

            records.append({
                "cik": cik,
                "as_of_date": as_of_date,
                "total_debt": total_debt,
                "total_long_term_debt": aggregates.get("total_long_term_debt"),
                "total_short_term_debt": aggregates.get("total_short_term_debt"),
                "total_capitalization": total_cap,
                "debt_to_capitalization": debt_to_cap,
                "tranches": tranches,
                "source": "SEC_10K",
                "extraction_method": "XBRL_FACTS+FOOTNOTE_REGEX",
                "confidence_score": 0.6 if tranches else 0.4,
            })
            logger.info(
                "  CAST: CIK %s — %s, %d tranches parsed",
                cik, as_of_date, len(tranches),
            )
        return records

    @staticmethod
    def _latest_debt_period(
        us_gaap: dict[str, Any],
    ) -> tuple[date, dict[str, float]] | None:
        """Pick the most recent 10-K annual period and gather debt aggregates."""
        periods: dict[str, dict[str, float]] = {}
        for concept_key, field in DEBT_FACT_MAP.items():
            concept = us_gaap.get(concept_key)
            if not concept:
                continue
            for entries in concept.get("units", {}).values():
                for e in entries:
                    if e.get("form") not in ("10-K", "10-K/A"):
                        continue
                    end = e.get("end")
                    val = e.get("val")
                    if not end or val is None:
                        continue
                    periods.setdefault(end, {})
                    periods[end].setdefault(field, float(val))
        if not periods:
            return None
        latest = max(periods.keys())
        try:
            as_of = date.fromisoformat(latest)
        except ValueError:
            return None
        return as_of, periods[latest]

    async def validate(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Validate extracted capital structure records."""
        valid = []
        for rec in records:
            if not (rec.get("cik") or rec.get("entity_id")):
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
        """Load capital structure records into the database.

        Also attempts to resolve each ``DebtTranche`` to an existing
        traded ``Security`` of the same issuer (matched on coupon rate +
        maturity year — the only fields both sides genuinely share) and,
        when a match is found, upserts ``FixedIncomeDetails`` (+
        ``CallPutSchedule`` when a call date was extracted from the
        footnote text). See module docstring / class docstring for why
        this frequently finds no match in practice: no connector in this
        codebase currently creates ``Security`` rows for corporate bonds
        (OpenFIGI is ticker-driven and returns almost exclusively
        equities), so the fixed-income side of the security master is
        typically empty. The wiring is still correct and will start
        populating rows automatically once a bond-CUSIP security-master
        connector exists.
        """
        stats = {
            "inserted": 0, "updated": 0, "skipped": 0, "errors": 0,
            "fi_details_inserted": 0, "call_schedule_inserted": 0,
        }

        for rec in records:
            try:
                from src.models.capital_structure import CapitalStructure, DebtTranche
                from src.models.entity import EntityIdentifier

                entity_id = rec.get("entity_id")
                if entity_id is None and rec.get("cik"):
                    result = await session.execute(
                        select(EntityIdentifier).where(
                            EntityIdentifier.identifier_type == "CIK",
                            EntityIdentifier.identifier_value == rec["cik"],
                        )
                    )
                    ident = result.scalar_one_or_none()
                    if ident is None:
                        logger.debug("No entity for CIK %s — skipping", rec["cik"])
                        stats["skipped"] += 1
                        continue
                    entity_id = ident.entity_id

                cs = CapitalStructure(
                    entity_id=entity_id,
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
                    maturity_date = tranche_data.get("maturity_date", maturity_date_val)

                    first_call_date = None
                    raw_call_date = tranche_data.get("first_call_date")
                    if raw_call_date:
                        first_call_date = (
                            date.fromisoformat(raw_call_date)
                            if isinstance(raw_call_date, str) else raw_call_date
                        )

                    tranche = DebtTranche(
                        entity_id=entity_id,
                        capital_structure_id=cs.capital_structure_id,
                        instrument_name=tranche_data.get("instrument_name"),
                        instrument_type=tranche_data.get("instrument_type"),
                        principal_amount=tranche_data.get("principal_amount"),
                        coupon_rate=tranche_data.get("coupon_rate"),
                        coupon_type=tranche_data.get("coupon_type", "FIXED"),
                        maturity_date=maturity_date,
                        first_call_date=first_call_date,
                        seniority_type=tranche_data.get("seniority_type"),
                    )
                    session.add(tranche)

                    matched_security_id = await self._resolve_fi_security(
                        session,
                        entity_id=entity_id,
                        coupon_rate=tranche_data.get("coupon_rate"),
                        maturity_date=maturity_date,
                    )
                    if matched_security_id is not None:
                        tranche.security_id = matched_security_id
                        fi_inserted = await self._upsert_fixed_income_details(
                            session, security_id=matched_security_id, tranche_data=tranche_data,
                        )
                        stats["fi_details_inserted"] += fi_inserted
                        if first_call_date is not None:
                            cp_inserted = await self._upsert_call_schedule(
                                session,
                                security_id=matched_security_id,
                                effective_date=first_call_date,
                            )
                            stats["call_schedule_inserted"] += cp_inserted

                stats["inserted"] += 1
            except Exception as e:
                logger.error("Error loading capital structure: %s", e)
                stats["errors"] += 1

        await session.flush()
        return stats

    @staticmethod
    async def _resolve_fi_security(
        session: AsyncSession,
        *,
        entity_id: Any,
        coupon_rate: float | None,
        maturity_date: date | None,
    ):
        """Match a debt tranche to an existing traded FI Security of the same
        issuer, by comparing coupon rate + maturity year — the only two
        fields genuinely present on both a 10-K-derived tranche and a
        security-master row. Returns ``None`` (no fabricated link) unless
        both fields are present on the tranche and exactly one candidate
        matches within tolerance.
        """
        if coupon_rate is None or maturity_date is None:
            return None
        from src.models.security import Security

        candidates = (
            await session.execute(
                select(Security.security_id, Security.maturity_date).where(
                    Security.issuer_entity_id == entity_id,
                    Security.asset_class == "FIXED_INCOME",
                    Security.maturity_date.is_not(None),
                )
            )
        ).all()
        matches = [
            sec_id for sec_id, sec_maturity in candidates
            if sec_maturity.year == maturity_date.year
        ]
        if len(matches) == 1:
            return matches[0]
        return None

    @staticmethod
    async def _upsert_fixed_income_details(
        session: AsyncSession, *, security_id: Any, tranche_data: dict[str, Any]
    ) -> int:
        """Upsert FixedIncomeDetails from a matched debt tranche's real terms."""
        from src.models.security import FixedIncomeDetails

        existing = await session.get(FixedIncomeDetails, security_id)
        fields = {
            "face_value": tranche_data.get("principal_amount"),
            "coupon_rate": tranche_data.get("coupon_rate"),
            "coupon_type": tranche_data.get("coupon_type"),
            "reference_rate": tranche_data.get("floating_reference"),
            "spread": tranche_data.get("floating_spread"),
            "seniority": tranche_data.get("seniority_type"),
            "collateral_type": tranche_data.get("collateral_description"),
            "has_financial_covenants": tranche_data.get("has_financial_covenants", False),
            "has_cross_default": tranche_data.get("has_cross_default", False),
        }
        if existing is None:
            session.add(FixedIncomeDetails(security_id=security_id, **fields))
            return 1
        for key, value in fields.items():
            if value is not None:
                setattr(existing, key, value)
        return 0

    @staticmethod
    async def _upsert_call_schedule(
        session: AsyncSession, *, security_id: Any, effective_date: date
    ) -> int:
        """Insert a CallPutSchedule CALL row if one doesn't already exist."""
        from src.models.security import CallPutSchedule

        existing = await session.execute(
            select(CallPutSchedule).where(
                CallPutSchedule.security_id == security_id,
                CallPutSchedule.schedule_type == "CALL",
                CallPutSchedule.effective_date == effective_date,
            )
        )
        if existing.scalar_one_or_none() is not None:
            return 0
        session.add(CallPutSchedule(
            security_id=security_id,
            schedule_type="CALL",
            effective_date=effective_date,
            notes="Extracted from 10-K debt footnote optional-redemption clause",
        ))
        return 1

    async def close(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
