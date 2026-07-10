"""On-demand data freshness.

When a user opens a company (or its news), the app triggers a targeted refresh
of just that company so the view reflects the latest data — without blocking the
response and without hammering rate limits.

Policy: **stale-while-revalidate**. The endpoint serves what's in the DB now and
schedules a background refresh; the freshly-fetched data lands in the DB for the
next load. Each (entity, data_type) has a freshness TTL and a hard cooldown so
repeated views don't trigger a refresh stampede.

The ``ingestion_progress`` table doubles as the freshness ledger: its
``last_success_at`` is when a company's data was last refreshed, so this service
and the scheduled backfill share one source of truth.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_session_factory

logger = logging.getLogger(__name__)

# How long each data type stays "fresh" before a view re-fetches it (seconds).
TTL_SECONDS: dict[str, int] = {
    "news": 15 * 60,             # 15 minutes
    "corporate_actions": 60 * 60,  # 1 hour
    "xbrl": 12 * 60 * 60,        # 12 hours
}
# Never re-trigger the same (entity, type) more often than this, regardless of
# how many concurrent views arrive.
COOLDOWN_SECONDS = 5 * 60

DEFAULT_TYPES = ("news", "corporate_actions", "xbrl")


# --------------------------------------------------------------------------- #
# Resolution helpers
# --------------------------------------------------------------------------- #
async def _resolve_cik(session: AsyncSession, entity_id: uuid.UUID) -> str | None:
    return await session.scalar(
        text(
            "SELECT identifier_value FROM entity_identifiers "
            "WHERE entity_id = :e AND identifier_type = 'CIK' LIMIT 1"
        ),
        {"e": entity_id},
    )


async def _resolve_ticker(session: AsyncSession, entity_id: uuid.UUID) -> str | None:
    ticker = await session.scalar(
        text(
            "SELECT si.identifier_value FROM securities s "
            "JOIN security_identifiers si ON si.security_id = s.security_id "
            "  AND si.identifier_type = 'TICKER' "
            "WHERE s.issuer_entity_id = :e LIMIT 1"
        ),
        {"e": entity_id},
    )
    if ticker:
        return ticker
    return await session.scalar(
        text(
            "SELECT name_value FROM entity_names "
            "WHERE entity_id = :e AND name_type = 'TRADING' LIMIT 1"
        ),
        {"e": entity_id},
    )


# --------------------------------------------------------------------------- #
# Freshness ledger
# --------------------------------------------------------------------------- #
async def _times(session, subject_key: str, data_type: str):
    row = (
        await session.execute(
            text(
                "SELECT last_success_at, last_attempt_at FROM ingestion_progress "
                "WHERE data_type = :dt AND subject_key = :sk"
            ),
            {"dt": data_type, "sk": subject_key},
        )
    ).first()
    return (row[0], row[1]) if row else (None, None)


def _needs_refresh(success_at, attempt_at, ttl: int, now: datetime) -> bool:
    if attempt_at and (now - attempt_at).total_seconds() < COOLDOWN_SECONDS:
        return False  # within cooldown — a refresh just ran or is running
    if success_at is None:
        return True
    return (now - success_at).total_seconds() > ttl


async def _claim(session, data_type, subject_key: str, entity_uuid, now) -> None:
    """Mark an attempt immediately so concurrent views don't double-fetch."""
    await session.execute(
        text(
            """
            INSERT INTO ingestion_progress
                (id, data_type, subject_key, entity_id, status, attempts,
                 last_attempt_at, created_at, updated_at)
            VALUES (:id, :dt, :sk, :eid, 'PENDING', 1, :now, :now, :now)
            ON CONFLICT (data_type, subject_key) DO UPDATE SET
                attempts = ingestion_progress.attempts + 1,
                last_attempt_at = :now,
                updated_at = :now
            """
        ),
        {"id": uuid.uuid4(), "dt": data_type, "sk": subject_key,
         "eid": entity_uuid, "now": now},
    )
    await session.commit()


async def _mark_success(session, data_type, subject_key: str, now) -> None:
    await session.execute(
        text(
            "UPDATE ingestion_progress SET status='SUCCESS', last_success_at=:now, "
            "updated_at=:now WHERE data_type=:dt AND subject_key=:sk"
        ),
        {"now": now, "dt": data_type, "sk": subject_key},
    )
    await session.commit()


async def _entity_has(session, table: str, entity_id) -> bool:
    return bool(
        await session.scalar(
            text(f"SELECT EXISTS(SELECT 1 FROM {table} WHERE entity_id = :e)"),
            {"e": entity_id},
        )
    )


async def _has_news(session, entity_id) -> bool:
    return bool(
        await session.scalar(
            text("SELECT EXISTS(SELECT 1 FROM article_entity_links WHERE entity_id = :e)"),
            {"e": entity_id},
        )
    )


# --------------------------------------------------------------------------- #
# Refresh drivers
# --------------------------------------------------------------------------- #
async def _refresh_one(session, entity_id, data_type, cik, now) -> None:
    # Local imports keep API startup light and avoid import cycles.
    if data_type == "news":
        ticker = await _resolve_ticker(session, entity_id)
        if not ticker:
            return
        from src.ingestion.finnhub_news import FinnhubNewsConnector
        await FinnhubNewsConnector().fetch_for_entity(session, entity_id, ticker, days=7)
        has = await _has_news(session, entity_id)
    elif data_type == "xbrl":
        if not cik:
            return
        from src.ingestion.edgar_xbrl import EdgarXBRLConnector
        await EdgarXBRLConnector(ciks=[cik]).run(session)
        await session.commit()
        has = await _entity_has(session, "financial_periods", entity_id)
    elif data_type == "corporate_actions":
        if not cik:
            return
        from src.ingestion.edgar_8k import Edgar8KConnector
        await Edgar8KConnector(ciks=[cik]).run(session)
        await session.commit()
        has = await _entity_has(session, "eight_k_events", entity_id)
    else:
        return

    if has:
        await _mark_success(session, data_type, str(entity_id), now)


async def refresh_entity(session: AsyncSession, entity_id: uuid.UUID,
                         data_types=DEFAULT_TYPES) -> list[str]:
    """Refresh the stale data types for one entity using the given session.

    Returns the list of types actually refreshed (after TTL/cooldown gating).
    """
    now = datetime.now(timezone.utc)
    cik = await _resolve_cik(session, entity_id)
    refreshed: list[str] = []
    for dt in data_types:
        success_at, attempt_at = await _times(session, str(entity_id), dt)
        if not _needs_refresh(success_at, attempt_at, TTL_SECONDS[dt], now):
            continue
        await _claim(session, dt, str(entity_id), entity_id, now)  # debounce concurrent
        try:
            await _refresh_one(session, entity_id, dt, cik, now)
            refreshed.append(dt)
        except Exception as e:  # never let a refresh break the request path
            await session.rollback()
            logger.warning("freshness: %s refresh failed for %s: %s", dt, entity_id, e)

    # New fundamentals mean the computed analytics (ratios, valuations, scores)
    # are now stale — recompute this company's securities so the view reflects
    # the fresh data. Recompute for one company is only a second or two.
    if "xbrl" in refreshed:
        try:
            await _recompute_entity_analytics(session, entity_id)
        except Exception as e:
            await session.rollback()
            logger.warning("freshness: analytics recompute failed for %s: %s", entity_id, e)
    return refreshed


async def _recompute_entity_analytics(session: AsyncSession, entity_id: uuid.UUID) -> None:
    """Recompute analytics for every security issued by this entity."""
    from scripts.run_analytics_batch import recompute_security

    rows = await session.execute(
        text("SELECT security_id FROM securities WHERE issuer_entity_id = :e"),
        {"e": entity_id},
    )
    for (security_id,) in rows.all():
        await recompute_security(session, security_id)


# Major US companies used to keep the global news feed fresh and recognizable.
MAJOR_TICKERS = [
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "JPM", "V", "UNH",
    "XOM", "JNJ", "WMT", "MA", "PG", "HD", "COST", "ORCL", "BAC", "KO",
    "PEP", "CVX", "MRK", "ABBV", "NFLX",
]
_GLOBAL_NEWS_KEY = "__GLOBAL__"


async def _entity_for_ticker(session, ticker: str) -> uuid.UUID | None:
    return await session.scalar(
        text(
            "SELECT s.issuer_entity_id FROM security_identifiers si "
            "JOIN securities s ON s.security_id = si.security_id "
            "WHERE si.identifier_type = 'TICKER' AND si.identifier_value = :t "
            "AND s.issuer_entity_id IS NOT NULL LIMIT 1"
        ),
        {"t": ticker},
    )


async def refresh_global_news(limit: int = 25) -> int:
    """Refresh the global news feed by pulling news for major companies.

    Debounced via a single ('news', __GLOBAL__) ledger row so the feed refreshes
    at most once per cooldown no matter how many people open the news page.
    """
    total = 0
    try:
        async with get_session_factory()() as session:
            now = datetime.now(timezone.utc)
            success_at, attempt_at = await _times(session, _GLOBAL_NEWS_KEY, "news")
            if not _needs_refresh(success_at, attempt_at, TTL_SECONDS["news"], now):
                return 0
            await _claim(session, "news", _GLOBAL_NEWS_KEY, None, now)

            from src.ingestion.finnhub_news import FinnhubNewsConnector
            connector = FinnhubNewsConnector()
            for ticker in MAJOR_TICKERS[:limit]:
                entity_id = await _entity_for_ticker(session, ticker)
                if entity_id is None:
                    continue
                total += await connector.fetch_for_entity(session, entity_id, ticker, days=3)
            await _mark_success(session, "news", _GLOBAL_NEWS_KEY, now)
    except Exception as e:
        logger.warning("freshness: global news refresh failed: %s", e)
    return total


async def trigger_entity_refresh(entity_id: uuid.UUID, data_types=DEFAULT_TYPES) -> None:
    """Background-task entrypoint: refreshes an entity on its own DB session.

    Safe to hand to FastAPI ``BackgroundTasks`` — it opens and closes its own
    session so it doesn't touch the request's session lifecycle.
    """
    try:
        async with get_session_factory()() as session:
            await refresh_entity(session, entity_id, data_types)
    except Exception as e:  # background tasks must never raise
        logger.warning("freshness: background refresh failed for %s: %s", entity_id, e)
