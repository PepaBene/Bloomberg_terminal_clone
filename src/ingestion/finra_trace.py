"""FINRA TRACE corporate bond trade ingestion connector.

Ingests OTC corporate bond trade prints from FINRA TRACE and loads them into
the bond master + pricing tables:

  * ``CorporateBond``  — bond reference (upserted by CUSIP)
  * ``BondTrade``      — individual trade prints
  * ``BondEODPrice``   — per-CUSIP end-of-day OHLC/VWAP roll-up

FLAG — TWO EXTRACT PATHS, ONE REAL TODAY AND ONE STILL A STUB
---------------------------------------------------------------
FINRA TRACE data is registration-gated either way — there is no keyless live
feed. Two extract() paths exist:

1. **Local-file path (real, usable today)** — ``local_file`` /
   ``settings.FINRA_TRACE_LOCAL_FILE``. A human registers once for FINRA's
   Academic/Historical TRACE (BTDS) program outside of this environment
   (e.g. via WRDS or direct FINRA registration for non-commercial/academic
   use), downloads a bulk dissemination extract, and this connector ingests
   that file from disk via :meth:`FINRATraceConnector._extract_from_file` —
   no live API call required. Academic TRACE bulk files are pipe-delimited
   (occasionally comma- or tab-delimited) text with one row per trade report
   and real column names resembling:

     CUSIP_ID, BOND_SYM_ID, COMPANY_SYMBOL, TRD_EXCTN_DT (YYYYMMDD),
     TRD_EXCTN_TM (HHMMSS), RPTD_PR (reported price, e.g. 101.500000),
     YLD_PT (yield), ENTRD_VOL_QT (entered volume / par value),
     RPT_SIDE_CD (B/S), CNTRA_MP_ID (contra party), SCRTY_TYPE_CD.

   These are mapped by :func:`_map_academic_trace_row` into the same dict
   shape :func:`normalize_trade` already expects. Academic TRACE files do
   **not** include an issuer CIK or issuer name — only CUSIP — so brand-new
   CUSIPs that aren't already present in the ``corporate_bonds`` table
   cannot be issuer-resolved from the file alone. ``load()`` already handles
   this correctly without any change: it looks up ``CorporateBond.cusip``
   first (so trades for CUSIPs already on file attach normally), and for a
   genuinely new CUSIP with no resolvable issuer CIK it skips + logs the
   trades rather than fabricating a bond/issuer. Bulk-loading brand-new
   issuers from an Academic TRACE extract therefore requires a supplementary
   CUSIP-to-CIK/entity mapping step (e.g. an OpenFIGI or WRDS CUSIP master)
   run before this connector, which is out of scope here.

2. **Live-feed path (still a stub)** — ``endpoint_url`` /
   ``settings.FINRA_TRACE_FEED_URL``, requiring registered subscription
   credentials and a pluggable auth-header hook. It is implemented
   to-pattern and unit-tested against a representative sample payload, but
   the exact wire schema must be validated against the live credentialed
   feed before production use.

In both paths the transform/load logic is real and shared: no fake bond rows
are ever fabricated — bonds whose issuer cannot be resolved to an existing
entity are skipped, not invented.
"""

from __future__ import annotations

import csv
import logging
import uuid
from collections import defaultdict
from datetime import date, datetime, time
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.ingestion.base import BaseConnector

logger = logging.getLogger(__name__)

# Candidate delimiters for local Academic TRACE bulk files, tried in order.
# Pipe is the documented standard delimiter for Academic/BTDS TRACE extracts.
_CANDIDATE_DELIMITERS = ("|", ",", "\t")

# Minimum distinct trades in a day for an EOD price to be considered reliable.
_LIQUID_TRADE_THRESHOLD = 5

_SIDE_MAP = {
    "B": "BUY",
    "S": "SELL",
    "buy": "BUY",
    "sell": "SELL",
    "P": "BUY",
    "purchase": "BUY",
    "sale": "SELL",
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
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%Y%m%d"):
        try:
            return datetime.strptime(str(value), fmt).date()
        except ValueError:
            continue
    return None


def _parse_time(value: Any) -> time | None:
    value = _clean(value)
    if not value:
        return None
    for fmt in ("%H:%M:%S", "%H:%M", "%H%M%S"):
        try:
            return datetime.strptime(str(value), fmt).time()
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


def _map_academic_trace_row(row: dict[str, Any]) -> dict[str, Any] | None:
    """Map one raw Academic/Historical TRACE bulk-file row to the generic
    dict shape :func:`normalize_trade` expects.

    Real Academic TRACE column names (see module docstring):
        CUSIP_ID       -> cusip
        TRD_EXCTN_DT   -> trade_date        (YYYYMMDD)
        TRD_EXCTN_TM   -> trade_time        (HHMMSS)
        RPTD_PR        -> price
        YLD_PT         -> yield
        ENTRD_VOL_QT   -> quantity
        RPT_SIDE_CD    -> side              (B/S)
        BOND_SYM_ID, COMPANY_SYMBOL, CNTRA_MP_ID, SCRTY_TYPE_CD are carried
        through for logging/diagnostics but are not consumed by
        normalize_trade (Academic TRACE has no issuer name/CIK column).

    Pure (no I/O) so it can be unit-tested directly. Returns ``None`` if the
    row lacks the minimum required fields (CUSIP + trade date).
    """
    # Header names in real extracts are consistently upper-cased, but be
    # lenient about stray whitespace/case from hand-edited or re-exported files.
    normalized = {(k or "").strip().upper(): v for k, v in row.items() if k is not None}

    cusip = _clean(normalized.get("CUSIP_ID"))
    trade_date = _clean(normalized.get("TRD_EXCTN_DT"))
    if not cusip or not trade_date:
        return None

    return {
        "cusip": cusip,
        "trade_date": trade_date,
        "trade_time": _clean(normalized.get("TRD_EXCTN_TM")),
        "price": _clean(normalized.get("RPTD_PR")),
        "yield": _clean(normalized.get("YLD_PT")),
        "quantity": _clean(normalized.get("ENTRD_VOL_QT")),
        "side": _clean(normalized.get("RPT_SIDE_CD")),
        # Diagnostic-only fields; not consumed by normalize_trade().
        "bond_symbol": _clean(normalized.get("BOND_SYM_ID")),
        "company_symbol": _clean(normalized.get("COMPANY_SYMBOL")),
        "contra_party": _clean(normalized.get("CNTRA_MP_ID")),
        "security_type": _clean(normalized.get("SCRTY_TYPE_CD")),
    }


def normalize_trade(row: dict[str, Any]) -> dict[str, Any] | None:
    """Normalize one raw TRACE trade message into a BondTrade field dict.

    Pure (no I/O) so it can be unit-tested directly. The ``cusip`` and issuer
    hints are retained so the loader can attach the trade to the right bond.
    Returns ``None`` if the row lacks the minimum keys.
    """
    cusip = _clean(row.get("cusip") or row.get("CUSIP") or row.get("cusip_id"))
    trade_date = _parse_date(
        row.get("trade_date") or row.get("tradeDate") or row.get("execution_date")
    )
    if not cusip or not trade_date:
        return None

    raw_side = str(row.get("side") or row.get("buy_sell") or "").strip()
    trade_type = _SIDE_MAP.get(raw_side, _SIDE_MAP.get(raw_side.lower()))

    return {
        "cusip": cusip[:9],
        "issuer_name": _clean(row.get("issuer_name") or row.get("company_name")),
        "issuer_cik": _clean(row.get("issuer_cik") or row.get("cik")),
        "coupon_rate": _parse_decimal(row.get("coupon") or row.get("coupon_rate")),
        "maturity_date": _parse_date(row.get("maturity_date") or row.get("maturity")),
        "trade": {
            "trade_date": trade_date,
            "trade_time": _parse_time(row.get("trade_time") or row.get("execution_time")),
            "settlement_date": _parse_date(row.get("settlement_date")),
            "price": _parse_decimal(row.get("price") or row.get("dollar_price")),
            "yield_value": _parse_decimal(row.get("yield") or row.get("yield_value")),
            "quantity": _parse_decimal(row.get("quantity") or row.get("volume") or row.get("par_value")),
            "quantity_reported": _clean(row.get("quantity_reported")),
            "trade_type": trade_type,
            "is_when_issued": bool(_clean(row.get("when_issued")))
            and str(row.get("when_issued")).lower() in ("y", "yes", "true", "1"),
            "source": "TRACE",
        },
    }


def aggregate_eod(cusip: str, trades: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Roll trade prints up into per-(cusip, date) EOD price rows.

    Pure function operating on normalized trade dicts (as returned by
    :func:`normalize_trade`). Computes last/high/low, VWAP, trade count and
    total volume, and a coarse liquidity score.
    """
    by_date: dict[date, list[dict[str, Any]]] = defaultdict(list)
    for t in trades:
        by_date[t["trade"]["trade_date"]].append(t["trade"])

    eod_rows: list[dict[str, Any]] = []
    for price_date, day_trades in by_date.items():
        prices = [t["price"] for t in day_trades if t.get("price") is not None]
        if not prices:
            continue
        # Order-preserving "last" (feed is chronological); high/low by value.
        last = prices[-1]
        high = max(prices)
        low = min(prices)

        # Volume-weighted average price.
        num = Decimal(0)
        den = Decimal(0)
        for t in day_trades:
            p = t.get("price")
            q = t.get("quantity")
            if p is not None and q:
                num += p * q
                den += q
        vwap = (num / den) if den else None

        total_volume = sum(
            (t["quantity"] for t in day_trades if t.get("quantity")), Decimal(0)
        )
        trade_count = len(day_trades)
        ytm_vals = [t["yield_value"] for t in day_trades if t.get("yield_value") is not None]

        eod_rows.append(
            {
                "cusip": cusip,
                "price_date": price_date,
                "last_trade_price": last,
                "vwap": vwap,
                "high_price": high,
                "low_price": low,
                "trade_count": trade_count,
                "total_volume": total_volume or None,
                "yield_to_maturity": ytm_vals[-1] if ytm_vals else None,
                "liquidity_score": min(100, trade_count * 10),
                "has_sufficient_trades": trade_count >= _LIQUID_TRADE_THRESHOLD,
                "price_source": "TRACE",
            }
        )
    return eod_rows


class FINRATraceConnector(BaseConnector):
    """Ingest TRACE corporate-bond trades from a configurable FINRA feed."""

    name = "FINRA TRACE"
    connector_type = "BATCH_API"
    data_domain = "FIXED_INCOME"

    def __init__(
        self,
        *,
        endpoint_url: str | None = None,
        api_key: str | None = None,
        params: dict[str, Any] | None = None,
        local_file: str | None = None,
    ):
        # Configurable — the real credentialed endpoint is supplied via settings
        # or the caller. Empty by default so extract() no-ops rather than 404s.
        self.endpoint_url = endpoint_url or getattr(settings, "FINRA_TRACE_FEED_URL", "")
        self.api_key = api_key or getattr(settings, "FINRA_TRACE_API_KEY", "")
        self.params = params or {}
        # Local Academic/Historical TRACE bulk file — preferred over the live
        # feed when set, since it requires no live credentialed API call.
        self.local_file = local_file or getattr(settings, "FINRA_TRACE_LOCAL_FILE", "")

    def auth_headers(self) -> dict[str, str]:
        """Auth-header hook — override / configure for the real credentialed feed."""
        headers = {"User-Agent": settings.SEC_USER_AGENT, "Accept": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def extract(self) -> list[dict[str, Any]]:
        # Prefer the local Academic/Historical TRACE bulk file when configured
        # — it requires no live credentialed API call.
        if self.local_file:
            return self._extract_from_file(self.local_file)

        if not self.endpoint_url:
            logger.warning(
                "[%s] no FINRA_TRACE_LOCAL_FILE or FINRA_TRACE_FEED_URL configured "
                "— live feed needs credentials + live validation, and no local bulk "
                "file was given; skipping extraction",
                self.name,
            )
            return []
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.get(
                self.endpoint_url, params=self.params, headers=self.auth_headers()
            )
            resp.raise_for_status()
            data = resp.json()
        records = data if isinstance(data, list) else data.get("trades", data.get("data", []))
        logger.info("[%s] fetched %d raw trade messages", self.name, len(records))
        return records

    def _extract_from_file(self, path: str) -> list[dict[str, Any]]:
        """Read a local Academic/Historical TRACE bulk dissemination file.

        Auto-detects the delimiter (pipe first — the documented Academic
        TRACE standard — falling back to comma, then tab) and maps each row
        via :func:`_map_academic_trace_row`. File-not-found and per-row
        parsing errors are logged and skipped rather than raised, so a
        malformed row (or a missing file) never crashes the whole batch —
        extract() just returns whatever could be read.
        """
        try:
            with open(path, "r", newline="", encoding="utf-8-sig") as f:
                first_line = f.readline()
                f.seek(0)

                delimiter = _CANDIDATE_DELIMITERS[0]
                for candidate in _CANDIDATE_DELIMITERS:
                    if candidate in first_line:
                        delimiter = candidate
                        break

                reader = csv.DictReader(f, delimiter=delimiter)
                records: list[dict[str, Any]] = []
                skipped = 0
                for i, row in enumerate(reader, start=1):
                    try:
                        mapped = _map_academic_trace_row(row)
                    except Exception:
                        logger.exception(
                            "[%s] skipping malformed row %d in %s", self.name, i, path
                        )
                        skipped += 1
                        continue
                    if mapped is None:
                        skipped += 1
                        continue
                    records.append(mapped)
        except FileNotFoundError:
            logger.warning(
                "[%s] local TRACE bulk file not found: %s — skipping extraction",
                self.name,
                path,
            )
            return []
        except OSError:
            logger.exception(
                "[%s] failed to read local TRACE bulk file %s — skipping extraction",
                self.name,
                path,
            )
            return []

        logger.info(
            "[%s] read %d raw trade rows (%d skipped) from local file %s using '%s' delimiter",
            self.name,
            len(records),
            skipped,
            path,
            delimiter,
        )
        return records

    async def validate(
        self, records: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        return [
            r
            for r in records
            if _clean(r.get("cusip") or r.get("CUSIP") or r.get("cusip_id"))
        ]

    async def transform(
        self, records: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        out = []
        for r in records:
            norm = normalize_trade(r)
            if norm:
                out.append(norm)
        logger.info("[%s] normalized %d trades", self.name, len(out))
        return out

    async def load(
        self, records: list[dict[str, Any]], session: AsyncSession
    ) -> dict[str, int]:
        from src.models.corporate_bond import BondEODPrice, BondTrade, CorporateBond
        from src.models.entity import EntityIdentifier

        counts = {"inserted": 0, "updated": 0, "skipped": 0, "errors": 0}
        if getattr(self, "dry_run", False):
            return counts

        # Group normalized trades by CUSIP.
        by_cusip: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for rec in records:
            by_cusip[rec["cusip"]].append(rec)

        for cusip, trades in by_cusip.items():
            try:
                bond = (
                    await session.execute(
                        select(CorporateBond).where(CorporateBond.cusip == cusip)
                    )
                ).scalar_one_or_none()

                if bond is None:
                    # Resolve the issuer to an existing entity — never invent one.
                    first = trades[0]
                    issuer_entity_id = None
                    cik = first.get("issuer_cik")
                    if cik:
                        issuer_entity_id = (
                            await session.execute(
                                select(EntityIdentifier.entity_id).where(
                                    EntityIdentifier.identifier_type == "CIK",
                                    EntityIdentifier.identifier_value == str(cik),
                                )
                            )
                        ).scalar_one_or_none()
                    if issuer_entity_id is None:
                        logger.info(
                            "[%s] skipping CUSIP %s — issuer not resolvable to an "
                            "existing entity (no fabricated bond created)",
                            self.name,
                            cusip,
                        )
                        counts["skipped"] += len(trades)
                        continue
                    maturity = first.get("maturity_date")
                    if maturity is None:
                        counts["skipped"] += len(trades)
                        continue
                    bond = CorporateBond(
                        bond_id=uuid.uuid4(),
                        cusip=cusip,
                        issuer_entity_id=issuer_entity_id,
                        issuer_name=first.get("issuer_name"),
                        issuer_cik=str(cik) if cik else None,
                        name=first.get("issuer_name") or f"Bond {cusip}",
                        coupon_rate=first.get("coupon_rate"),
                        maturity_date=maturity,
                        status="OUTSTANDING",
                    )
                    session.add(bond)
                    await session.flush()
                    counts["inserted"] += 1

                # Insert trade prints.
                for t in trades:
                    session.add(
                        BondTrade(trade_id=uuid.uuid4(), bond_id=bond.bond_id, **t["trade"])
                    )
                    counts["inserted"] += 1

                # Upsert EOD roll-ups.
                for eod in aggregate_eod(cusip, trades):
                    eod_data = {k: v for k, v in eod.items() if k != "cusip"}
                    existing_eod = (
                        await session.execute(
                            select(BondEODPrice).where(
                                BondEODPrice.bond_id == bond.bond_id,
                                BondEODPrice.price_date == eod_data["price_date"],
                            )
                        )
                    ).scalar_one_or_none()
                    if existing_eod:
                        for key, val in eod_data.items():
                            setattr(existing_eod, key, val)
                        counts["updated"] += 1
                    else:
                        session.add(
                            BondEODPrice(id=uuid.uuid4(), bond_id=bond.bond_id, **eod_data)
                        )
                        counts["inserted"] += 1
            except Exception:  # pragma: no cover - defensive
                logger.exception("[%s] failed to load CUSIP %s", self.name, cusip)
                counts["errors"] += 1
        await session.flush()
        return counts
