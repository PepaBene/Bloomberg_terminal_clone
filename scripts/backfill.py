"""Resumable, rate-limit-aware backfill orchestrator.

The problem this solves: a full backfill of every company is far longer than any
single process can run (rate limits + wall-clock), and a killed run must not lose
work or re-fetch what's already done.

Design:
  * A ``ingestion_progress`` row per (data_type, subject) records SUCCESS /
    NO_DATA / PENDING so work is never repeated and dead-ends aren't retried
    forever.
  * The orchestrator processes only the *next* un-done subjects, commits per
    batch, and stops cleanly once a time budget (``--max-minutes``) elapses — so
    it always exits gracefully before anything external kills it.
  * Run it repeatedly (a loop, cron, or Windows Task Scheduler — see BACKFILL.md)
    and it converges to 100% coverage.

Usage:
    python -m scripts.backfill --status
    python -m scripts.backfill --type xbrl --batch-size 25 --max-minutes 8
    python -m scripts.backfill --type prices --batch-size 6
    python -m scripts.backfill --type sc13 --batch-size 10 --max-minutes 8
    python -m scripts.backfill --all --max-minutes 20
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import re
import sys
import time
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.database import get_session_factory
from src.ingestion.edgar_13d13g import Edgar13D13GConnector
from src.ingestion.edgar_13f import Edgar13FConnector
from src.ingestion.edgar_8k import Edgar8KConnector
from src.ingestion.edgar_capital_structure import EdgarCapitalStructureConnector
from src.ingestion.edgar_credit_ratings import EdgarCreditRatingConnector
from src.ingestion.edgar_esg import EdgarESGConnector
from src.ingestion.edgar_esg_environmental import EdgarESGEnvironmentalConnector
from src.ingestion.edgar_executives import EdgarExecutivesConnector
from src.ingestion.edgar_exhibit21 import EdgarExhibit21Connector
from src.ingestion.edgar_filing_diff import EdgarFilingDiffConnector
from src.ingestion.edgar_form4 import EdgarForm4Connector
from src.ingestion.edgar_ipo import EdgarIpoConnector
from src.ingestion.edgar_ma_deals import EdgarMaDealsConnector
from src.ingestion.edgar_nport_funds import EdgarNportFundsConnector
from src.ingestion.edgar_proxy import EdgarProxyConnector
from src.ingestion.edgar_segments import EdgarSegmentsConnector
from src.ingestion.edgar_xbrl import EdgarXBRLConnector
from src.ingestion.bond_issuances import BondIssuancesConnector
from src.ingestion.guidance_extraction import GuidanceExtractionConnector
from src.ingestion.polygon_eod import PolygonEODConnector

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("backfill")

MAX_ATTEMPTS = 3  # give up on a subject (mark NO_DATA) after this many empty tries


# --------------------------------------------------------------------------- #
# Data-type registry
# --------------------------------------------------------------------------- #
@dataclass
class EntityCikType:
    """A company-scoped, CIK-driven SEC data type."""

    key: str
    connector_cls: type
    kwarg: str              # connector constructor arg name for the CIK list
    target_table: str       # table that gets a row when the subject has data
    target_fk: str          # FK column on that table pointing at the entity
    extra_kwargs: dict = field(default_factory=dict)
    # Optional SQL fragment (e.g. "AND provider = 'X'") disambiguating a
    # has-data check on a table shared by more than one data type/connector.
    extra_where: str = ""
    # Per-type override for --batch-size. A single round-robin "turn" calls
    # connector.run() once for the whole batch with no internal deadline
    # check (unlike prices), so a type whose connector fetches multiple
    # documents per subject (e.g. esg_environmental's 5 historical 10-Ks +
    # an EPA lookup per CIK) can single-handedly burn an entire pass's time
    # budget in one turn -- starving every type that comes after it in the
    # rotation. Cap batch_size here for measured-slow types instead.
    batch_size: int | None = None
    kind: str = "entity_cik"


# Registry is intentionally simple to extend: add a connector + its target table.
ENTITY_TYPES: dict[str, EntityCikType] = {
    "xbrl": EntityCikType(
        "xbrl", EdgarXBRLConnector, "ciks", "financial_periods", "entity_id"
    ),
    # 8-K corporate events. days_back is a HISTORICAL window here (5y), not the
    # connector's 30-day freshness default — the backfill wants event history,
    # not just the last month (Apple returns 0 8-Ks at 30d, 91 at 10y).
    "corporate_actions": EntityCikType(
        "corporate_actions", Edgar8KConnector, "ciks", "eight_k_events", "entity_id",
        extra_kwargs={"days_back": 1825},
    ),
    "esg": EntityCikType(
        "esg", EdgarESGConnector, "cik_list", "esg_scores", "entity_id"
    ),
    # NOTE: 13F ownership is intentionally NOT here — see FILER_TYPES below.
    # 13F-HR filings are filed BY institutional managers, not by the issuer, so
    # querying an issuer's CIK returns nothing (confirmed live 2026-07-22: a
    # standalone run against 8,006 issuer CIKs produced 3 institution_profiles
    # in 10 minutes — only the handful of issuers that are themselves also
    # registered 13F filers, e.g. bank holding companies). Real 13F ingestion
    # needs an institution-CIK-driven universe instead (~8-9k active filers,
    # discovered from SEC's own quarterly full-index — see
    # ``_discover_13f_filers`` / ``FILER_TYPES``).
    # SEC Form 4 insider transactions (per issuer CIK). 2y historical window
    # (cut from 5y to speed up the backfill; 2y rarely exceeds the 500-filing cap
    # even for active issuers, so history within the window isn't truncated).
    "insider": EntityCikType(
        "insider", EdgarForm4Connector, "issuer_ciks", "insider_transactions_p3", "entity_id",
        extra_kwargs={"days_back": 730, "max_filings_per_cik": 500},
    ),
    # DEF 14A proxy governance (proxy_filings + comp/board/proposals).
    "governance": EntityCikType(
        "governance", EdgarProxyConnector, "ciks", "proxy_filings", "entity_id"
    ),
    # 10-K/10-Q section diffs (heavy: fetches two full filings per company).
    "filing_diff": EntityCikType(
        "filing_diff", EdgarFilingDiffConnector, "cik_list", "filing_diffs", "entity_id"
    ),
    # -- Added: per-CIK types that had a real connector + scheduled ingest
    # script but no resumable/cursored backfill path (they only ever ran as
    # "load every CIK, whatever finishes in the SLA window" with no memory of
    # what was already tried) -- see run_backfill_loop.py's completion gap.
    "capital_structure": EntityCikType(
        "capital_structure", EdgarCapitalStructureConnector, "ciks",
        "capital_structures", "entity_id",
    ),
    "credit_ratings": EntityCikType(
        "credit_ratings", EdgarCreditRatingConnector, "ciks",
        "credit_rating_events", "entity_id",
    ),
    # Executive is person-level (no entity_id) -- ExecutiveRole is the join
    # table that actually links a person to a company, so it's the correct
    # "did this CIK get data" signal.
    # Measured ~5.8s/CIK live (365d ownership-filing lookup) -- batch_size
    # capped so one turn doesn't run ~150s+ and crowd out other types.
    "executives": EntityCikType(
        "executives", EdgarExecutivesConnector, "issuer_ciks",
        "executive_roles", "entity_id", extra_kwargs={"days_back": 365},
        batch_size=10,
    ),
    # Guidance is tied to earnings-release 8-Ks (roughly quarterly); 730d
    # mirrors the "insider" override above so a backfill pass captures ~8
    # quarters instead of the connector's 30-day freshness default.
    "guidance": EntityCikType(
        "guidance", GuidanceExtractionConnector, "ciks",
        "guidance_tracking", "entity_id", extra_kwargs={"days_back": 730},
    ),
    # Shares esg_scores with the "esg" type above (EdgarESGConnector writes
    # provider='SEC_EDGAR'); this connector writes provider='EDGAR_DISCLOSURE_PROXY'
    # (see PROVIDER in edgar_esg_environmental.py). Without the provider filter,
    # any company already covered by "esg" would look done here too.
    # Measured ~10s/CIK live *sequentially* (up to 5 historical 10-K fetches +
    # an EPA Envirofacts lookup per CIK, one company at a time) -- the
    # heaviest of the new types. The connector now fans out CIKs concurrently
    # (bounded by `concurrency`, still gated by its own SEC rate limiter, so
    # this can't exceed the fair-access request rate) and trims filing_limit
    # from the connector's live-use default of 5 years to 3, so batch_size
    # can go well past the old sequential-era cap of 5.
    "esg_environmental": EntityCikType(
        "esg_environmental", EdgarESGEnvironmentalConnector, "cik_list",
        "esg_scores", "entity_id",
        extra_where="AND provider = 'EDGAR_DISCLOSURE_PROXY'",
        extra_kwargs={"filing_limit": 3, "concurrency": 8},
        batch_size=25,
    ),
    "subsidiaries": EntityCikType(
        "subsidiaries", EdgarExhibit21Connector, "ciks",
        "subsidiaries", "parent_entity_id",
    ),
    "segments": EntityCikType(
        "segments", EdgarSegmentsConnector, "ciks",
        "segment_data", "entity_id",
    ),
    # -- Migrated from the standalone scripts/ingest_*.py one-shot runner:
    # same connector_cls(**{kwarg: ciks}, **extra_kwargs) -> connector.run()
    # shape as everything else here, so they get the same chunked/resumable/
    # ingestion_progress-tracked treatment for free instead of re-running
    # from scratch on every restart.
    "ipo": EntityCikType(
        "ipo", EdgarIpoConnector, "ciks",
        "ipo_events", "entity_id", extra_kwargs={"days_back": 365},
    ),
    "ma_deals": EntityCikType(
        "ma_deals", EdgarMaDealsConnector, "ciks",
        "ma_deals", "acquirer_entity_id", extra_kwargs={"days_back": 90},
    ),
    # fund_holdings rows don't carry entity_id directly (they key off
    # fund_id) -- the has-data check targets `funds` instead, which does
    # (funds.entity_id, populated when the connector discovers an N-PORT
    # filer for that CIK).
    "nport": EntityCikType(
        "nport", EdgarNportFundsConnector, "fund_ciks",
        "funds", "entity_id", extra_kwargs={"days_back": 120},
    ),
    "bond_issuances": EntityCikType(
        "bond_issuances", BondIssuancesConnector, "ciks",
        "bond_issuances", "issuer_entity_id", extra_kwargs={"days_back": 180},
    ),
}

# NOTE: three more per-CIK external jobs were considered and deliberately left
# out because their connectors don't fit this registry's shape
# (``connector_cls(**{kwarg: ciks}, **extra_kwargs)`` then a single
# ``connector.run(session)``):
#   - earnings_surprises_ingest (FinnhubEarningsConnector): no batch ciks/run()
#     entry point at all -- driven per-entity via connector.fetch_for_entity().
#   - consensus_estimates_ingest (AlphaVantageEstimatesConnector): ticker-driven
#     (security_identifiers, identifier_type='TICKER'), not CIK-driven, and
#     Alpha Vantage's free tier is a hard 25 requests/DAY cap -- unsafe to fold
#     into an unattended round-robin loop.
#   - esg_controversies_ingest (EsgControversiesConnector): needs
#     entities=[{cik, legal_name, entity_id}, ...] dicts, not a plain CIK list.


@dataclass
class FilerCikType:
    """A data type driven by a CIK universe that is NOT our issuer entities
    (e.g. 13F institutional managers) -- subjects live directly in
    ``ingestion_progress`` (seeded by a discovery step) rather than being
    derived from ``entity_identifiers``.
    """

    key: str
    connector_cls: type
    kwarg: str
    target_table: str        # table that gets a row when the subject has data
    target_key_col: str      # column on that table holding the filer's CIK
    extra_kwargs: dict = field(default_factory=dict)
    kind: str = "filer_cik"
    # Full `SELECT EXISTS(...)` expression (binds :cik) overriding the default
    # `target_table`/`target_key_col` template, for when "has data" can't be
    # expressed as a single-table cik-column lookup.
    has_data_sql: str | None = None


FILER_TYPES: dict[str, FilerCikType] = {
    # [Bug fix] target_table was "institution_profiles", which gets a row
    # for every discovered filer unconditionally (see Edgar13FConnector.load)
    # regardless of whether any real per-position holding was ever parsed --
    # this made every filer look "done" after one attempt even when 100% of
    # its holdings were silently skipped (see edgar_13f.py's CUSIP-resolution
    # fix). The real signal is a row in institutional_holdings, joined back
    # to institution_profiles for the cik.
    "ownership_13f": FilerCikType(
        "ownership_13f", Edgar13FConnector, "ciks", "institution_profiles", "cik",
        has_data_sql=(
            "SELECT EXISTS("
            "SELECT 1 FROM institutional_holdings ih "
            "JOIN institution_profiles ip ON ip.institution_id = ih.institution_id "
            "WHERE ip.cik = :cik)"
        ),
    ),
}

DATE_TYPES = {"prices", "sc13"}
# Explicit round-robin order (NOT dict-derived). A single turn has no
# internal deadline check (prices excepted), so a type positioned late can be
# starved entirely if the types ahead of it in rotation are individually
# slow -- this happened live: ownership_13f (by far the largest remaining
# backlog) went untouched for 55+ minutes once the newer, heavier per-CIK
# types (esg_environmental especially -- 5 historical 10-K fetches + an EPA
# lookup per CIK) were added ahead of it and started eating whole passes.
# Placing it right after the original six protects it regardless of how the
# newer types perform.
ALL_TYPES = [
    "xbrl", "corporate_actions", "esg", "insider", "governance", "filing_diff",
    "ownership_13f",
    "capital_structure", "credit_ratings", "executives", "guidance",
    "esg_environmental", "subsidiaries", "segments",
    "ipo", "ma_deals", "nport", "bond_issuances",
    "prices", "sc13",
]
assert set(ALL_TYPES) == set(ENTITY_TYPES) | set(FILER_TYPES) | DATE_TYPES, (
    "ALL_TYPES must list every registered type exactly once -- "
    f"missing: {(set(ENTITY_TYPES) | set(FILER_TYPES) | DATE_TYPES) - set(ALL_TYPES)}, "
    f"unknown: {set(ALL_TYPES) - (set(ENTITY_TYPES) | set(FILER_TYPES) | DATE_TYPES)}"
)

# --------------------------------------------------------------------------- #
# 13F filer discovery -- SEC's own quarterly full-index is the authoritative,
# free, keyless list of "who filed a 13F-HR" (institutional managers aren't
# enumerable any other way; they're not in our issuer-driven `entities` table).
# --------------------------------------------------------------------------- #
_FULL_INDEX_LINE_RE = re.compile(r"^13F-HR\s+(.+?)\s+(\d+)\s+(\d{4}-\d{2}-\d{2})\s+(\S+)\s*$")


def _recent_quarters(n: int) -> list[tuple[int, int]]:
    """Last ``n`` (year, quarter) pairs ending with the most recently
    completed quarter (today's in-progress quarter is skipped -- its index
    is usually still thin)."""
    today = date.today()
    year, q = today.year, (today.month - 1) // 3 + 1
    q -= 1
    if q == 0:
        year, q = year - 1, 4
    out = []
    for _ in range(n):
        out.append((year, q))
        q -= 1
        if q == 0:
            year, q = year - 1, 4
    return out


async def _discover_13f_filers(session: AsyncSession) -> int:
    """Seed PENDING ingestion_progress rows for every unique 13F-HR filer CIK
    found in SEC's last 4 quarterly full-indexes (trailing ~1yr, so filers who
    miss a single quarter's deadline are still caught). Idempotent -- already
    known subjects (any status) are left untouched via ON CONFLICT DO NOTHING.
    """
    ciks: set[str] = set()
    async with httpx.AsyncClient(timeout=60.0, headers={"User-Agent": settings.SEC_USER_AGENT}) as client:
        for year, q in _recent_quarters(4):
            url = f"https://www.sec.gov/Archives/edgar/full-index/{year}/QTR{q}/form.idx"
            try:
                resp = await client.get(url)
                if resp.status_code != 200:
                    continue
            except httpx.HTTPError as e:
                logger.warning("13F filer discovery: %s failed: %s", url, e)
                continue
            for line in resp.text.splitlines():
                m = _FULL_INDEX_LINE_RE.match(line)
                if m:
                    ciks.add(m.group(2))

    if not ciks:
        return 0

    now = datetime.now(timezone.utc)
    rows = [
        {
            "id": uuid.uuid4(), "dt": "ownership_13f", "sk": cik, "eid": None,
            "status": "PENDING", "attempts": 0, "rows": 0, "now": now,
        }
        for cik in ciks
    ]
    # Plain per-row upsert via raw SQL (consistent with the rest of this
    # module's ingestion_progress access, which is all text()-based).
    for row in rows:
        await session.execute(
            text(
                """
                INSERT INTO ingestion_progress
                    (id, data_type, subject_key, entity_id, status, attempts,
                     rows_ingested, last_attempt_at, last_success_at, created_at, updated_at)
                VALUES
                    (:id, :dt, :sk, :eid, :status, :attempts, :rows, NULL, NULL, :now, :now)
                ON CONFLICT (data_type, subject_key) DO NOTHING
                """
            ),
            row,
        )
    await session.commit()
    logger.info("13F filer discovery: %d unique filer CIKs found (trailing 4 quarters).", len(ciks))
    return len(ciks)

# Prioritization knob: BACKFILL_SKIP="insider" (comma-separated) drops those
# types from this run so the shared SEC 10/s budget goes entirely to the rest.
# All EDGAR types share one rate limit, so they can't finish faster in parallel —
# pausing the heavy insider backfill lets the light xbrl/corporate_actions types
# drain far quicker. Clear the env var to resume the skipped types.
import os as _os  # noqa: E402
_BACKFILL_SKIP = {t.strip() for t in _os.environ.get("BACKFILL_SKIP", "").split(",") if t.strip()}
if _BACKFILL_SKIP:
    for _t in list(_BACKFILL_SKIP):
        ENTITY_TYPES.pop(_t, None)
    ALL_TYPES = [t for t in ALL_TYPES if t not in _BACKFILL_SKIP]


# --------------------------------------------------------------------------- #
# Progress helpers
# --------------------------------------------------------------------------- #
async def _record(
    session: AsyncSession,
    data_type: str,
    subject_key: str,
    *,
    entity_id: uuid.UUID | None,
    has_data: bool,
    rows: int = 0,
    error: str | None = None,
) -> None:
    """Upsert a progress row, advancing attempts / status appropriately."""
    now = datetime.now(timezone.utc)
    prior = await session.scalar(
        text(
            "SELECT attempts FROM ingestion_progress "
            "WHERE data_type = :dt AND subject_key = :sk"
        ),
        {"dt": data_type, "sk": subject_key},
    )
    attempts = (prior or 0) + 1
    if has_data:
        status, success_at = "SUCCESS", now
    elif attempts >= MAX_ATTEMPTS:
        status, success_at = "NO_DATA", None
    else:
        status, success_at = "PENDING", None

    await session.execute(
        text(
            """
            INSERT INTO ingestion_progress
                (id, data_type, subject_key, entity_id, status, attempts,
                 rows_ingested, last_attempt_at, last_success_at, error,
                 created_at, updated_at)
            VALUES
                (:id, :dt, :sk, :eid, :status, :attempts, :rows, :now,
                 CAST(:success_at AS timestamptz), :err, :now, :now)
            ON CONFLICT (data_type, subject_key) DO UPDATE SET
                status = :status,
                attempts = :attempts,
                rows_ingested = GREATEST(ingestion_progress.rows_ingested, :rows),
                last_attempt_at = :now,
                last_success_at = COALESCE(
                    CAST(:success_at AS timestamptz), ingestion_progress.last_success_at
                ),
                error = :err,
                updated_at = :now
            """
        ),
        {
            "id": uuid.uuid4(),
            "dt": data_type,
            "sk": subject_key,
            "eid": entity_id,
            "status": status,
            "attempts": attempts,
            "rows": rows,
            "now": now,
            "success_at": success_at,
            "err": (error or None),
        },
    )


async def _pending_entities(
    session: AsyncSession, data_type: str, limit: int
) -> list[tuple[uuid.UUID, str]]:
    """Next batch of (entity_id, cik) not yet done for this data type."""
    rows = await session.execute(
        text(
            """
            SELECT ei.entity_id, ei.identifier_value AS cik
            FROM entity_identifiers ei
            LEFT JOIN ingestion_progress ip
              ON ip.data_type = :dt AND ip.subject_key = ei.entity_id::text
            WHERE ei.identifier_type = 'CIK'
              AND (ip.id IS NULL OR (ip.status = 'PENDING' AND ip.attempts < :max))
            ORDER BY ip.last_attempt_at ASC NULLS FIRST, ei.identifier_value
            LIMIT :n
            """
        ),
        {"dt": data_type, "max": MAX_ATTEMPTS, "n": limit},
    )
    return [(r[0], r[1]) for r in rows.all()]


async def _entity_has_data(
    session: AsyncSession, table: str, fk: str, entity_id: uuid.UUID, extra_where: str = ""
) -> bool:
    # table/fk/extra_where are registry constants (never user input) — safe to interpolate.
    return bool(
        await session.scalar(
            text(f"SELECT EXISTS(SELECT 1 FROM {table} WHERE {fk} = :eid {extra_where})"),
            {"eid": entity_id},
        )
    )


# --------------------------------------------------------------------------- #
# Backfill drivers
# --------------------------------------------------------------------------- #
async def _run_entity_batch(
    session: AsyncSession, cfg: EntityCikType, batch_size: int
) -> int:
    """Process one batch of a CIK-driven type. Returns subjects processed."""
    subjects = await _pending_entities(session, cfg.key, cfg.batch_size or batch_size)
    if not subjects:
        return 0

    ciks = [cik for _, cik in subjects]
    connector = cfg.connector_cls(**{cfg.kwarg: ciks}, **cfg.extra_kwargs)
    err: str | None = None
    try:
        await connector.run(session)
        await session.commit()
    except Exception as e:  # whole-batch failure (e.g. network) — retry later
        await session.rollback()
        err = f"{type(e).__name__}: {e}"[:400]
        logger.warning("[%s] batch failed: %s", cfg.key, err)

    for entity_id, _cik in subjects:
        has = False if err else await _entity_has_data(
            session, cfg.target_table, cfg.target_fk, entity_id, cfg.extra_where
        )
        await _record(
            session, cfg.key, str(entity_id), entity_id=entity_id,
            has_data=has, error=err,
        )
    await session.commit()
    return len(subjects)


async def _pending_filers(session: AsyncSession, data_type: str, limit: int) -> list[str]:
    """Next batch of filer CIKs not yet done for this data type.

    Unlike ``_pending_entities``, the subject universe already lives in
    ``ingestion_progress`` (seeded by ``_discover_13f_filers``) rather than
    being derived from ``entity_identifiers`` on the fly.
    """
    rows = await session.execute(
        text(
            """
            SELECT subject_key FROM ingestion_progress
            WHERE data_type = :dt AND status = 'PENDING' AND attempts < :max
            ORDER BY last_attempt_at ASC NULLS FIRST, subject_key
            LIMIT :n
            """
        ),
        {"dt": data_type, "max": MAX_ATTEMPTS, "n": limit},
    )
    return [r[0] for r in rows.all()]


async def _run_filer_batch(session: AsyncSession, cfg: FilerCikType, batch_size: int) -> int:
    """Process one batch of a filer-CIK-driven type. Returns subjects processed."""
    if not await session.scalar(
        text("SELECT EXISTS(SELECT 1 FROM ingestion_progress WHERE data_type=:dt)"),
        {"dt": cfg.key},
    ):
        await _discover_13f_filers(session)

    ciks = await _pending_filers(session, cfg.key, batch_size)
    if not ciks:
        return 0

    connector = cfg.connector_cls(**{cfg.kwarg: ciks}, **cfg.extra_kwargs)
    err: str | None = None
    try:
        await connector.run(session)
        await session.commit()
    except Exception as e:  # whole-batch failure (e.g. network) — retry later
        await session.rollback()
        err = f"{type(e).__name__}: {e}"[:400]
        logger.warning("[%s] batch failed: %s", cfg.key, err)

    has_data_query = cfg.has_data_sql or (
        f"SELECT EXISTS(SELECT 1 FROM {cfg.target_table} WHERE {cfg.target_key_col} = :cik)"
    )
    for cik in ciks:
        has = False if err else bool(
            await session.scalar(text(has_data_query), {"cik": cik})
        )
        await _record(session, cfg.key, cik, entity_id=None, has_data=has, error=err)
    await session.commit()
    return len(ciks)


async def _pending_price_dates(
    session: AsyncSession, limit: int, lookback_days: int
) -> list[str]:
    """Next batch of trading days (most recent first) with no prices yet."""
    # Pass real date objects — asyncpg encodes a DATE comparison from a date,
    # not an ISO string.
    yesterday = date.today() - timedelta(days=1)
    earliest = date.today() - timedelta(days=lookback_days)
    rows = await session.execute(
        text(
            """
            SELECT DISTINCT td.date::text AS d
            FROM trading_days td
            LEFT JOIN ingestion_progress ip
              ON ip.data_type = 'prices' AND ip.subject_key = td.date::text
            WHERE td.is_trading_day = true
              AND td.date <= :yst AND td.date >= :earliest
              AND (ip.id IS NULL OR (ip.status = 'PENDING' AND ip.attempts < :max))
            ORDER BY d DESC
            LIMIT :n
            """
        ),
        {"yst": yesterday, "earliest": earliest, "max": MAX_ATTEMPTS, "n": limit},
    )
    return [r[0] for r in rows.all()]


async def _run_price_batch(
    session: AsyncSession, batch_size: int, lookback_days: int, deadline: float
) -> int:
    """Fetch grouped-daily prices for the next un-done trading days."""
    dates = await _pending_price_dates(session, batch_size, lookback_days)
    if not dates:
        return 0

    processed = 0
    for idx, d in enumerate(dates):
        if time.monotonic() > deadline:
            break
        err: str | None = None
        try:
            connector = PolygonEODConnector(target_date=d)
            await connector.run(session)
            await session.commit()
        except Exception as e:
            await session.rollback()
            err = f"{type(e).__name__}: {e}"[:400]
            logger.warning("[prices] %s failed: %s", d, err)

        has = False if err else bool(
            await session.scalar(
                text("SELECT EXISTS(SELECT 1 FROM eod_prices WHERE price_date = :d)"),
                {"d": date.fromisoformat(d)},
            )
        )
        await _record(session, "prices", d, entity_id=None, has_data=has, error=err)
        await session.commit()
        processed += 1
        # Respect Polygon's free-tier limit (~5 req/min) between dates.
        if idx < len(dates) - 1 and time.monotonic() < deadline:
            await asyncio.sleep(13)
    return processed


async def _pending_sc13_dates(
    session: AsyncSession, limit: int, lookback_days: int
) -> list[str]:
    """Next batch of trading days (most recent first) with no Schedule
    13D/13G sweep yet. Reuses ``trading_days`` as the "did SEC EDGAR accept
    filings that day" calendar -- close enough to EDGAR's own business-day
    calendar (both are closed weekends/federal holidays); a mismatched day
    just means ``Edgar13D13GConnector`` sees a 404 and records zero filings,
    which is harmless.
    """
    yesterday = date.today() - timedelta(days=1)
    earliest = date.today() - timedelta(days=lookback_days)
    rows = await session.execute(
        text(
            """
            SELECT DISTINCT td.date::text AS d
            FROM trading_days td
            LEFT JOIN ingestion_progress ip
              ON ip.data_type = 'sc13' AND ip.subject_key = td.date::text
            WHERE td.is_trading_day = true
              AND td.date <= :yst AND td.date >= :earliest
              AND (ip.id IS NULL OR (ip.status = 'PENDING' AND ip.attempts < :max))
            ORDER BY d DESC
            LIMIT :n
            """
        ),
        {"yst": yesterday, "earliest": earliest, "max": MAX_ATTEMPTS, "n": limit},
    )
    return [r[0] for r in rows.all()]


async def _run_sc13_batch(
    session: AsyncSession, batch_size: int, lookback_days: int, deadline: float
) -> int:
    """Sweep Schedule 13D/13G filings for the next un-done days.

    One day per ``Edgar13D13GConnector(target_date=...)`` call, same shape as
    ``_run_price_batch``. No inter-day sleep needed (unlike Polygon's 5/min
    free-tier cap) -- the connector's own ``RateLimiter`` already paces every
    HTTP call against ``SEC_RATE_LIMIT``.
    """
    dates = await _pending_sc13_dates(session, batch_size, lookback_days)
    if not dates:
        return 0

    processed = 0
    for d in dates:
        if time.monotonic() > deadline:
            break
        err: str | None = None
        try:
            connector = Edgar13D13GConnector(target_date=d)
            await connector.run(session)
            await session.commit()
        except Exception as e:
            await session.rollback()
            err = f"{type(e).__name__}: {e}"[:400]
            logger.warning("[sc13] %s failed: %s", d, err)

        has = False if err else bool(
            await session.scalar(
                text("SELECT EXISTS(SELECT 1 FROM beneficial_ownership_filings WHERE filing_date = :d)"),
                {"d": date.fromisoformat(d)},
            )
        )
        await _record(session, "sc13", d, entity_id=None, has_data=has, error=err)
        await session.commit()
        processed += 1
    return processed


# --------------------------------------------------------------------------- #
# Reconcile — mark subjects that already have data as SUCCESS (no fetching)
# --------------------------------------------------------------------------- #
async def reconcile(session: AsyncSession) -> None:
    """Seed progress from data already in the DB so we never re-fetch it."""
    for cfg in ENTITY_TYPES.values():
        await session.execute(
            text(
                f"""
                INSERT INTO ingestion_progress
                    (id, data_type, subject_key, entity_id, status, attempts,
                     rows_ingested, last_attempt_at, last_success_at, created_at, updated_at)
                SELECT gen_random_uuid(), :dt, d.eid::text, d.eid, 'SUCCESS', 1, 0,
                       now(), now(), now(), now()
                FROM (SELECT DISTINCT {cfg.target_fk} AS eid FROM {cfg.target_table}
                      WHERE {cfg.target_fk} IS NOT NULL {cfg.extra_where}) d
                ON CONFLICT (data_type, subject_key) DO NOTHING
                """
            ),
            {"dt": cfg.key},
        )
    for cfg in FILER_TYPES.values():
        # Same institution_profiles-vs-institutional_holdings distinction as
        # the per-batch has-data check above -- reuse cfg.has_data_sql's cik
        # source (institutional_holdings JOIN institution_profiles) instead
        # of a bare institution_profiles.cik scan, so a freshly-discovered
        # filer that merely has a profile (no real holdings yet) doesn't get
        # seeded straight to SUCCESS.
        cik_source = (
            "SELECT DISTINCT ip.cik AS cik FROM institutional_holdings ih "
            "JOIN institution_profiles ip ON ip.institution_id = ih.institution_id "
            "WHERE ip.cik IS NOT NULL"
            if cfg.has_data_sql else
            f"SELECT DISTINCT {cfg.target_key_col} AS cik FROM {cfg.target_table} "
            f"WHERE {cfg.target_key_col} IS NOT NULL"
        )
        await session.execute(
            text(
                f"""
                INSERT INTO ingestion_progress
                    (id, data_type, subject_key, entity_id, status, attempts,
                     rows_ingested, last_attempt_at, last_success_at, created_at, updated_at)
                SELECT gen_random_uuid(), :dt, d.cik, NULL, 'SUCCESS', 1, 0,
                       now(), now(), now(), now()
                FROM ({cik_source}) d
                ON CONFLICT (data_type, subject_key) DO NOTHING
                """
            ),
            {"dt": cfg.key},
        )
    await session.execute(
        text(
            """
            INSERT INTO ingestion_progress
                (id, data_type, subject_key, entity_id, status, attempts,
                 rows_ingested, last_attempt_at, last_success_at, created_at, updated_at)
            SELECT gen_random_uuid(), 'prices', d.pd::text, NULL, 'SUCCESS', 1, 0,
                   now(), now(), now(), now()
            FROM (SELECT DISTINCT price_date AS pd FROM eod_prices) d
            ON CONFLICT (data_type, subject_key) DO NOTHING
            """
        )
    )
    await session.execute(
        text(
            """
            INSERT INTO ingestion_progress
                (id, data_type, subject_key, entity_id, status, attempts,
                 rows_ingested, last_attempt_at, last_success_at, created_at, updated_at)
            SELECT gen_random_uuid(), 'sc13', d.fd::text, NULL, 'SUCCESS', 1, 0,
                   now(), now(), now(), now()
            FROM (SELECT DISTINCT filing_date AS fd FROM beneficial_ownership_filings) d
            ON CONFLICT (data_type, subject_key) DO NOTHING
            """
        )
    )
    await session.commit()
    logger.info("Reconciled progress from existing data.")


# --------------------------------------------------------------------------- #
# Status
# --------------------------------------------------------------------------- #
async def print_status(session: AsyncSession) -> None:
    total_ciks = await session.scalar(
        text("SELECT count(*) FROM entity_identifiers WHERE identifier_type='CIK'")
    )
    print(f"\nUniverse: {total_ciks} companies (by CIK)\n")
    print(f"{'data_type':20} {'SUCCESS':>9} {'NO_DATA':>9} {'PENDING':>9} {'remaining':>10} {'coverage':>9}")
    print("-" * 72)
    for key in ENTITY_TYPES:
        counts = dict(
            (r[0], r[1])
            for r in (
                await session.execute(
                    text(
                        "SELECT status, count(*) FROM ingestion_progress "
                        "WHERE data_type=:k GROUP BY status"
                    ),
                    {"k": key},
                )
            ).all()
        )
        succ = counts.get("SUCCESS", 0)
        nodata = counts.get("NO_DATA", 0)
        pend = counts.get("PENDING", 0)
        done = succ + nodata
        remaining = (total_ciks or 0) - done
        cov = (done / total_ciks * 100) if total_ciks else 0
        print(f"{key:20} {succ:>9} {nodata:>9} {pend:>9} {remaining:>10} {cov:>8.1f}%")

    # Filer-CIK-driven types (universe = however many subjects discovery has
    # seeded into ingestion_progress so far, not the issuer CIK count above).
    for key in FILER_TYPES:
        counts = dict(
            (r[0], r[1])
            for r in (
                await session.execute(
                    text(
                        "SELECT status, count(*) FROM ingestion_progress "
                        "WHERE data_type=:k GROUP BY status"
                    ),
                    {"k": key},
                )
            ).all()
        )
        succ = counts.get("SUCCESS", 0)
        nodata = counts.get("NO_DATA", 0)
        pend = counts.get("PENDING", 0)
        universe = succ + nodata + pend
        done = succ + nodata
        cov = (done / universe * 100) if universe else 0
        print(f"{key:20} {succ:>9} {nodata:>9} {pend:>9} {pend:>10} {cov:>8.1f}%  (of {universe} discovered filers)")

    # Prices coverage (date-based)
    total_days = await session.scalar(
        text(
            "SELECT count(DISTINCT date) FROM trading_days td "
            "JOIN trading_calendars tc ON tc.calendar_id=td.calendar_id "
            "WHERE td.is_trading_day=true AND td.date <= CURRENT_DATE"
        )
    )
    priced = await session.scalar(
        text("SELECT count(*) FROM ingestion_progress WHERE data_type='prices' AND status='SUCCESS'")
    )
    print(f"{'prices (days)':20} {priced or 0:>9} {'-':>9} {'-':>9} {'-':>10} "
          f"{'(recent window)':>9}")

    # SC 13D/13G coverage (date-based, same shape as prices)
    sc13_done = await session.scalar(
        text("SELECT count(*) FROM ingestion_progress WHERE data_type='sc13' AND status='SUCCESS'")
    )
    print(f"{'sc13 (days)':20} {sc13_done or 0:>9} {'-':>9} {'-':>9} {'-':>10} "
          f"{'(recent window)':>9}")
    print()


# --------------------------------------------------------------------------- #
# Refresh — re-queue companies whose data has gone stale
# --------------------------------------------------------------------------- #
async def reopen_stale(session: AsyncSession, days: int) -> int:
    """Re-queue entity subjects last refreshed more than ``days`` ago.

    Companies file new data continuously, so once the historical backfill is
    complete this keeps it fresh: a SUCCESS row older than the window flips back
    to PENDING and the next pass re-fetches it (dedup skips unchanged periods).
    Price days are immutable history, so they're never reopened.
    """
    result = await session.execute(
        text(
            """
            UPDATE ingestion_progress
            SET status = 'PENDING', attempts = 0, updated_at = now()
            WHERE data_type = ANY(:types)
              AND status = 'SUCCESS'
              AND last_success_at < now() - make_interval(days => :days)
            """
        ),
        {"types": list(ENTITY_TYPES.keys()) + list(FILER_TYPES.keys()), "days": days},
    )
    await session.commit()
    logger.info("Reopened %d stale subjects for refresh (older than %dd).",
                result.rowcount or 0, days)
    return result.rowcount or 0


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Resumable backfill orchestrator")
    p.add_argument("--type", choices=ALL_TYPES, help="Backfill a single data type")
    p.add_argument("--all", action="store_true", help="Cycle through all data types")
    p.add_argument("--status", action="store_true", help="Print coverage and exit")
    p.add_argument("--reconcile", action="store_true",
                   help="Mark subjects that already have data as done, then exit")
    p.add_argument("--batch-size", type=int, default=25, help="Subjects per batch")
    p.add_argument("--max-minutes", type=float, default=8.0, help="Wall-clock budget")
    p.add_argument("--prices-lookback-days", type=int, default=120,
                   help="How far back to backfill daily prices")
    p.add_argument("--sc13-lookback-days", type=int, default=180,
                   help="How far back to backfill Schedule 13D/13G filings")
    p.add_argument("--refresh-days", type=int, default=0,
                   help="Before running, re-queue companies last refreshed more "
                        "than N days ago (0 = disabled)")
    return p.parse_args()


async def _backfill_type(session, key, args, deadline) -> int:
    if key == "prices":
        return await _run_price_batch(
            session, args.batch_size, args.prices_lookback_days, deadline
        )
    if key == "sc13":
        return await _run_sc13_batch(
            session, args.batch_size, args.sc13_lookback_days, deadline
        )
    if key in FILER_TYPES:
        return await _run_filer_batch(session, FILER_TYPES[key], args.batch_size)
    return await _run_entity_batch(session, ENTITY_TYPES[key], args.batch_size)


async def main() -> None:
    args = parse_args()
    async with get_session_factory()() as session:
        if args.reconcile:
            await reconcile(session)
            await print_status(session)
            return
        if args.status or (not args.type and not args.all):
            await print_status(session)
            return

        if args.refresh_days > 0:
            await reopen_stale(session, args.refresh_days)

        deadline = time.monotonic() + args.max_minutes * 60
        types = ALL_TYPES if args.all else [args.type]
        totals = {t: 0 for t in types}
        # Round-robin so --all spreads the budget across types.
        idx = 0
        exhausted: set[str] = set()
        while time.monotonic() < deadline and len(exhausted) < len(types):
            key = types[idx % len(types)]
            idx += 1
            if key in exhausted:
                continue
            n = await _backfill_type(session, key, args, deadline)
            totals[key] += n
            if n == 0:
                exhausted.add(key)
                logger.info("[%s] no remaining subjects — complete", key)
            else:
                logger.info("[%s] processed %d (running total %d)", key, n, totals[key])

        elapsed = args.max_minutes * 60 - max(0.0, deadline - time.monotonic())
        logger.info("Backfill chunk done in %.0fs. Processed: %s", elapsed, totals)
        await print_status(session)


if __name__ == "__main__":
    asyncio.run(main())
