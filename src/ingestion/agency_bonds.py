"""Agency (GSE) bond ingestion connector.

Ingests U.S. federal-agency / GSE debt reference data (FNMA, FHLMC, FHLB,
FFCB, TVA, GNMA, SBA, ...) into the ``AgencyBond`` table.

VALIDATED AGAINST LIVE DATA (2026-07-22)
------------------------------------------
``extract()`` fetches ``settings.FHLB_OF_DATA_URL`` — confirmed live at
``https://cdn.fhlb-of.com/files/Debt%20Statistics/debtstatistics.xlsx``, the
FHLB (Federal Home Loan Banks) Office of Finance's free, keyless debt
statistics workbook (their old CSV/JSON "Bond Data Files" page no longer
exists after a site redesign; the "Browse Our Debt Securities Data" UI's
"Download Data" button is JS-driven with no static endpoint — this workbook
is the only keyless, directly-fetchable file found). The FHLBanks are the
one GSE issuer group that publishes this data through a single "Office of
Finance" umbrella site rather than per-bank paid feeds, which is why this
connector targets FHLB specifically rather than the full agency universe
(Fannie Mae / Freddie Mac debt-issuance data lives on their own
investor-relations sites with different, unconfirmed schemas — out of scope
here).

The response is parsed as CSV, JSON, or XLSX depending on the response
``Content-Type``/URL suffix/body-sniffing (in that priority order — CSV via
Python's built-in ``csv`` module, this codebase's ingestion connectors avoid
pandas for row parsing, e.g. ``sanctions_entries.py``; XLSX via ``openpyxl``,
since that's the only format the live FHLB file is actually served in).
For XLSX, the workbook's **"Outstanding TAP Issues"** sheet is read (falls
back to the first sheet whose header row contains "CUSIP" if that name
changes) — real per-CUSIP rows (~230 as of this writing): CUSIP, maturity
date, original settlement date, and principal outstanding amount/weighted
average coupon. Known limitation: this sheet is FHLB's "TAP" (reopened)
issuance list, not the full ~$850B+ outstanding universe across all
CUSIPs — it's real, live, unfabricated data, just partial coverage. Parsed
rows are mapped through the documented column mappings below
(``_CSV_COLUMN_MAP`` for CSV/JSON, ``_XLSX_COLUMN_MAP`` for the XLSX sheet)
into the exact dict shape ``transform()``/``load()`` expect. Fields the XLSX
sheet doesn't carry (``issuer_name``, ``coupon_type``, ``original_amount_mm``,
call schedule) are defaulted (``issuer_name="Federal Home Loan Banks"``,
``coupon_type="FIXED"``) or left ``None`` rather than fabricated.

Fannie Mae, Freddie Mac, FFCB, TVA, GNMA and SBA debt are NOT covered by this
extract() path; the pre-existing configurable JSON feed
(``AGENCY_BONDS_FEED_URL`` / ``--feed-url``) remains available as a
fallback/override for a consolidated paid feed covering the full agency
universe, and takes priority over the FHLB path when configured.
"""

from __future__ import annotations

import csv
import io
import json
import logging
import uuid
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx
from openpyxl import load_workbook
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.ingestion.base import BaseConnector

logger = logging.getLogger(__name__)

# Documented expected column mapping for the FHLB Office of Finance
# consolidated-obligation debt-issuance CSV/XML-as-CSV export.
# ⚠ UNCONFIRMED against a live file — see module docstring. Column names are
# our best guess at FHLB Office of Finance's conventional field naming
# (matching the terminology used in their public debt-issuance summaries);
# override via ``AgencyBondsConnector(column_map=...)`` once the real header
# row is known, without needing a code change.
_CSV_COLUMN_MAP: dict[str, str] = {
    "cusip": "CUSIP",
    "issuer_name": "Issuer",
    "coupon_rate": "Coupon Rate",
    "coupon_type": "Coupon Type",
    "maturity_date": "Maturity Date",
    "issue_date": "Issue Date",
    "original_amount_mm": "Issue Amount ($MM)",
    "outstanding_amount_mm": "Amount Outstanding ($MM)",
    "first_call_date": "First Call Date",
    "is_callable": "Callable",
}

# Real column headers of the FHLB Office of Finance "debtstatistics.xlsx"
# workbook's "Outstanding TAP Issues" sheet — confirmed against the live file
# (2026-07-22). Header row is row 3 (row 1 is a merged title, row 2 is a
# spacer row), 7 columns: CUSIP, Original Maturity Length, Original
# Settlement Date, Remaining Maturity Length, Maturity Date, Principal
# Outstanding Amount ($ mil), Weighted Average Coupon (%). Only the fields
# we can populate without fabricating are mapped below.
_XLSX_COLUMN_MAP: dict[str, str] = {
    "cusip": "CUSIP",
    "maturity_date": "Maturity Date",
    "issue_date": "Original Settlement Date",
    "outstanding_amount_mm": "Principal Outstanding Amount ($ mil)",
    "coupon_rate": "Weighted Average Coupon (%)",
}
_XLSX_SHEET_NAME = "Outstanding TAP Issues"

# Normalize common issuer descriptors onto our short agency_type codes.
_AGENCY_TYPE_MAP = {
    "fannie mae": "FNMA",
    "federal national mortgage association": "FNMA",
    "fnma": "FNMA",
    "freddie mac": "FHLMC",
    "federal home loan mortgage corporation": "FHLMC",
    "fhlmc": "FHLMC",
    "federal home loan bank": "FHLB",
    "fhlb": "FHLB",
    "federal farm credit": "FFCB",
    "ffcb": "FFCB",
    "tennessee valley authority": "TVA",
    "tva": "TVA",
    "ginnie mae": "GNMA",
    "gnma": "GNMA",
    "small business administration": "SBA",
    "sba": "SBA",
}

# Backing/guarantee inference by agency type.
_BACKING_MAP = {
    "GNMA": "EXPLICIT_GUARANTEE",
    "TVA": "EXPLICIT_GUARANTEE",
    "SBA": "EXPLICIT_GUARANTEE",
    "FNMA": "CONSERVATORSHIP",
    "FHLMC": "CONSERVATORSHIP",
    "FHLB": "IMPLICIT_SUPPORT",
    "FFCB": "IMPLICIT_SUPPORT",
}


def _clean(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, str):
        v = value.strip()
        if v == "" or v.lower() in ("null", "none", "n/a"):
            return None
        return v
    return value


def _parse_date(value: Any) -> date | None:
    value = _clean(value)
    if not value:
        return None
    # openpyxl (data_only=True) resolves date-formatted XLSX cells directly
    # to date/datetime objects rather than strings.
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%Y%m%d"):
        try:
            return datetime.strptime(str(value), fmt).date()
        except ValueError:
            continue
    return None


def _parse_decimal(value: Any) -> Decimal | None:
    value = _clean(value)
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _agency_type(issuer: Any, explicit: Any = None) -> str | None:
    explicit = _clean(explicit)
    if explicit:
        return str(explicit).upper()[:20]
    issuer = _clean(issuer)
    if not issuer:
        return None
    text = str(issuer).lower()
    for needle, code in _AGENCY_TYPE_MAP.items():
        if needle in text:
            return code
    return None


class AgencyBondsConnector(BaseConnector):
    """Ingest GSE/agency debt reference data.

    Primary path: the FHLB Office of Finance's free, keyless
    consolidated-obligation debt-issuance download (``fhlb_url`` /
    ``settings.FHLB_OF_DATA_URL``), parsed as CSV or JSON depending on the
    response ``Content-Type`` (see module docstring for the column-mapping
    caveats).

    Fallback path: a configurable JSON feed (``feed_url`` /
    ``AGENCY_BONDS_FEED_URL``), preserved for a future consolidated paid feed
    covering the full agency universe (Fannie Mae, Freddie Mac, FFCB, TVA,
    GNMA, SBA, ...). If ``feed_url`` is set it takes priority over the FHLB
    path.
    """

    name = "Agency Bonds"
    connector_type = "BATCH_API"
    data_domain = "FIXED_INCOME"

    def __init__(
        self,
        *,
        feed_url: str | None = None,
        api_key: str | None = None,
        fhlb_url: str | None = None,
        column_map: dict[str, str] | None = None,
        xlsx_column_map: dict[str, str] | None = None,
    ):
        self.feed_url = feed_url or getattr(settings, "AGENCY_BONDS_FEED_URL", "")
        self.api_key = api_key or getattr(settings, "AGENCY_BONDS_API_KEY", "")
        self.fhlb_url = fhlb_url or getattr(settings, "FHLB_OF_DATA_URL", "")
        # Overridable so the real column names can be supplied without a code
        # change once confirmed against a live FHLB Office of Finance file.
        self.column_map = dict(column_map) if column_map else dict(_CSV_COLUMN_MAP)
        self.xlsx_column_map = (
            dict(xlsx_column_map) if xlsx_column_map else dict(_XLSX_COLUMN_MAP)
        )

    def auth_headers(self) -> dict[str, str]:
        headers = {"User-Agent": settings.SEC_USER_AGENT, "Accept": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _normalize_row(
        self, row: dict[str, Any], column_map: dict[str, str] | None = None
    ) -> dict[str, Any]:
        """Map a raw FHLB row (CSV ``DictReader`` row, JSON object, or XLSX
        sheet row) onto our internal field names via ``column_map`` (defaults
        to ``self.column_map``, the CSV/JSON mapping).

        Tries the internal field name directly first (covers a JSON endpoint
        that already happens to use our field names), then falls back to the
        documented source column name (covers CSV/XLSX rows, and a JSON
        endpoint that just serializes the CSV's own column headers as JSON
        keys). Every row from this connector's FHLB path is FHLB debt by
        construction, so ``agency_type`` defaults to "FHLB" unless the source
        row explicitly overrides it.
        """
        column_map = column_map if column_map is not None else self.column_map
        mapped: dict[str, Any] = {}
        for internal_key, source_col in column_map.items():
            direct = row.get(internal_key)
            mapped[internal_key] = direct if direct not in (None, "") else row.get(source_col)
        mapped.setdefault("agency_type", None)
        if not mapped.get("agency_type"):
            mapped["agency_type"] = row.get("agency_type") or "FHLB"
        mapped.setdefault("issuer_name", row.get("issuer_name"))
        return mapped

    def _parse_csv_body(self, body: str) -> list[dict[str, Any]]:
        reader = csv.DictReader(io.StringIO(body))
        return [self._normalize_row(row) for row in reader]

    def _parse_json_body(self, body: str) -> list[dict[str, Any]]:
        try:
            data = json.loads(body)
        except (json.JSONDecodeError, ValueError):
            logger.warning("[%s] FHLB response was not valid JSON", self.name)
            return []
        if isinstance(data, dict):
            data = data.get("bonds") or data.get("data") or data.get("issuances") or []
        if not isinstance(data, list):
            return []
        return [self._normalize_row(r) for r in data if isinstance(r, dict)]

    def _parse_xlsx_body(self, content: bytes) -> list[dict[str, Any]]:
        """Parse the FHLB Office of Finance debt-statistics workbook.

        Reads the ``_XLSX_SHEET_NAME`` sheet (falls back to the first sheet
        whose header row contains "CUSIP" if that name isn't found — sheet
        names/positions have shifted before). The header isn't necessarily
        row 1 (the live file has a merged title row + a blank spacer row
        before it), so this scans the first 10 rows for the one containing
        "CUSIP" rather than assuming a fixed offset.
        """
        try:
            wb = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
        except Exception:
            logger.warning("[%s] FHLB response was not a readable XLSX workbook", self.name)
            return []

        sheet = wb[_XLSX_SHEET_NAME] if _XLSX_SHEET_NAME in wb.sheetnames else None
        candidates = [sheet] if sheet else wb.worksheets

        for ws in candidates:
            rows_iter = ws.iter_rows(values_only=True)
            header: list[str] | None = None
            for _ in range(10):
                try:
                    candidate_row = next(rows_iter)
                except StopIteration:
                    break
                cells = [str(c).strip() if c is not None else "" for c in candidate_row]
                if any(c.upper() == "CUSIP" for c in cells):
                    header = cells
                    break
            if header is None:
                continue

            records: list[dict[str, Any]] = []
            for data_row in rows_iter:
                row_dict = dict(zip(header, data_row))
                if not row_dict.get("CUSIP"):
                    continue
                row_dict.setdefault("issuer_name", "Federal Home Loan Banks")
                records.append(self._normalize_row(row_dict, column_map=self.xlsx_column_map))
            return records

        logger.warning("[%s] no sheet with a CUSIP header found in FHLB workbook", self.name)
        return []

    async def _extract_from_fhlb(self) -> list[dict[str, Any]]:
        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
            resp = await client.get(
                self.fhlb_url, headers={"User-Agent": settings.SEC_USER_AGENT}
            )
            resp.raise_for_status()
            content_type = (resp.headers.get("content-type") or "").lower()
            content = resp.content

        is_xlsx = (
            "spreadsheetml" in content_type
            or "ms-excel" in content_type
            or self.fhlb_url.lower().split("?")[0].endswith((".xlsx", ".xls"))
            or content[:4] == b"PK\x03\x04"  # zip magic bytes (xlsx is a zip container)
        )

        if is_xlsx:
            records = self._parse_xlsx_body(content)
        else:
            body = content.decode("utf-8", errors="replace")
            if "json" in content_type:
                records = self._parse_json_body(body)
            elif "csv" in content_type:
                records = self._parse_csv_body(body)
            else:
                # Content-Type is missing or generic (static-file hosts commonly
                # serve CSV as text/plain or application/octet-stream) — sniff
                # the body instead.
                stripped = body.lstrip()
                if stripped[:1] in ("[", "{"):
                    records = self._parse_json_body(body)
                else:
                    records = self._parse_csv_body(body)

        logger.info(
            "[%s] fetched %d raw rows from FHLB Office of Finance (content-type=%s)",
            self.name, len(records), content_type or "unknown",
        )
        return records

    async def _extract_from_feed(self) -> list[dict[str, Any]]:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.get(self.feed_url, headers=self.auth_headers())
            resp.raise_for_status()
            data = resp.json()
        records = data if isinstance(data, list) else data.get("bonds", data.get("data", []))
        logger.info("[%s] fetched %d raw rows from configured feed", self.name, len(records))
        return records

    async def extract(self) -> list[dict[str, Any]]:
        if self.feed_url:
            return await self._extract_from_feed()
        if not self.fhlb_url:
            logger.warning(
                "[%s] no FHLB_OF_DATA_URL / AGENCY_BONDS_FEED_URL configured — "
                "skipping extraction",
                self.name,
            )
            return []
        return await self._extract_from_fhlb()

    async def validate(
        self, records: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        return [
            r
            for r in records
            if _clean(r.get("cusip")) and _parse_date(r.get("maturity_date"))
        ]

    async def transform(
        self, records: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Normalize raw feed rows into AgencyBond field dicts (pure)."""
        out: list[dict[str, Any]] = []
        seen: set[str] = set()
        for r in records:
            cusip = _clean(r.get("cusip"))
            maturity = _parse_date(r.get("maturity_date"))
            if not cusip or not maturity or cusip in seen:
                continue
            seen.add(cusip)

            agency_type = _agency_type(r.get("issuer_name"), r.get("agency_type"))
            backing = _clean(r.get("backing_type")) or (
                _BACKING_MAP.get(agency_type) if agency_type else None
            )
            first_call = _parse_date(r.get("first_call_date"))
            out.append(
                {
                    "cusip": str(cusip)[:9],
                    "issuer_name": _clean(r.get("issuer_name")),
                    "agency_type": agency_type,
                    "backing_type": backing[:25] if backing else None,
                    "coupon_rate": _parse_decimal(r.get("coupon_rate") or r.get("coupon")),
                    "coupon_type": (_clean(r.get("coupon_type")) or "FIXED").upper()[:20],
                    "coupon_frequency": int(r["coupon_frequency"])
                    if _clean(r.get("coupon_frequency")) is not None
                    else 2,
                    "maturity_date": maturity,
                    "issue_date": _parse_date(r.get("issue_date")),
                    "original_amount_mm": _parse_decimal(r.get("original_amount_mm")),
                    "outstanding_amount_mm": _parse_decimal(r.get("outstanding_amount_mm")),
                    "currency": (_clean(r.get("currency")) or "USD")[:3],
                    "is_callable": bool(first_call)
                    or str(r.get("is_callable")).lower() in ("y", "yes", "true", "1"),
                    "first_call_date": first_call,
                    "is_outstanding": True,
                    "status": "OUTSTANDING",
                }
            )
        logger.info("[%s] transformed %d unique agency bonds", self.name, len(out))
        return out

    async def load(
        self, records: list[dict[str, Any]], session: AsyncSession
    ) -> dict[str, int]:
        from src.models.agency_bond import AgencyBond

        counts = {"inserted": 0, "updated": 0, "skipped": 0, "errors": 0}
        if getattr(self, "dry_run", False):
            return counts

        for rec in records:
            try:
                existing = (
                    await session.execute(
                        select(AgencyBond).where(AgencyBond.cusip == rec["cusip"])
                    )
                ).scalar_one_or_none()
                if existing:
                    for key, val in rec.items():
                        if val is not None:
                            setattr(existing, key, val)
                    counts["updated"] += 1
                else:
                    session.add(AgencyBond(bond_id=uuid.uuid4(), **rec))
                    counts["inserted"] += 1
            except Exception:  # pragma: no cover - defensive
                logger.exception("[%s] failed to load row", self.name)
                counts["errors"] += 1
        await session.flush()
        return counts
