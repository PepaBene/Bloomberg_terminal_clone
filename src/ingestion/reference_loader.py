"""Reference data loader — seeds DB from static JSON files (Spec 10)."""

import json
import logging
import uuid
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.reference import (
    Country,
    Currency,
    Exchange,
    GICSClassification,
    NAICSCode,
    SICCode,
    SICToGICSMapping,
    TradingCalendar,
    TradingDay,
)

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"


def _load_json(filename: str) -> list[dict[str, Any]]:
    """Load a JSON file from the data directory."""
    filepath = DATA_DIR / filename
    with open(filepath, encoding="utf-8") as f:
        return json.load(f)


async def _upsert_batch(
    session: AsyncSession,
    model,
    records: list[dict[str, Any]],
    pk_columns: list[str],
    label: str,
) -> dict[str, int]:
    """Generic upsert using PostgreSQL ON CONFLICT DO UPDATE."""
    if not records:
        return {"inserted": 0, "updated": 0}

    table = model.__table__
    valid_cols = {c.name for c in table.columns}

    inserted = 0
    updated = 0

    for record in records:
        # Filter to only valid columns
        filtered = {k: v for k, v in record.items() if k in valid_cols}

        stmt = pg_insert(table).values(**filtered)

        # Build update dict (all non-PK columns)
        update_cols = {k: v for k, v in filtered.items() if k not in pk_columns}

        if update_cols:
            stmt = stmt.on_conflict_do_update(
                index_elements=pk_columns,
                set_=update_cols,
            )
        else:
            stmt = stmt.on_conflict_do_nothing(index_elements=pk_columns)

        result = await session.execute(stmt)

        if result.rowcount > 0:
            # Can't distinguish insert from update with ON CONFLICT, count as upserted
            inserted += 1

    await session.flush()
    logger.info(f"[{label}] Upserted {inserted} of {len(records)} records")
    return {"inserted": inserted, "total": len(records)}


async def load_currencies(session: AsyncSession) -> dict[str, int]:
    """Load ISO 4217 currencies from currencies.json."""
    records = _load_json("currencies.json")
    return await _upsert_batch(session, Currency, records, ["currency_code"], "currencies")


async def load_countries(session: AsyncSession) -> dict[str, int]:
    """Load ISO 3166 countries from countries.json."""
    records = _load_json("countries.json")
    return await _upsert_batch(
        session, Country, records, ["country_code_alpha2"], "countries"
    )


async def load_exchanges(session: AsyncSession) -> dict[str, int]:
    """Load ISO 10383 exchanges from exchanges.json."""
    records = _load_json("exchanges.json")
    return await _upsert_batch(session, Exchange, records, ["mic"], "exchanges")


async def load_gics(session: AsyncSession) -> dict[str, int]:
    """Load GICS classification hierarchy from gics.json."""
    records = _load_json("gics.json")
    return await _upsert_batch(
        session, GICSClassification, records, ["sub_industry_code"], "gics"
    )


async def load_sic_codes(session: AsyncSession) -> dict[str, int]:
    """Load SIC codes from sic_codes.json."""
    records = _load_json("sic_codes.json")
    return await _upsert_batch(session, SICCode, records, ["sic_code"], "sic_codes")


async def load_naics_codes(session: AsyncSession) -> dict[str, int]:
    """Load NAICS codes from naics_codes.json."""
    records = _load_json("naics_codes.json")
    return await _upsert_batch(session, NAICSCode, records, ["naics_code"], "naics_codes")


async def load_sic_gics_mapping(session: AsyncSession) -> dict[str, int]:
    """Load SIC-to-GICS crosswalk from sic_to_gics_mapping.json."""
    records = _load_json("sic_to_gics_mapping.json")
    return await _upsert_batch(
        session, SICToGICSMapping, records, ["sic_code"], "sic_to_gics_mapping"
    )


# Stable namespace so calendar ids are deterministic across re-runs (keeps the
# trading_days FK stable and makes the upsert idempotent).
_TRADING_CAL_NAMESPACE = uuid.UUID("6f1a7c2e-0000-4000-8000-0000cafe0001")


def _easter(year: int) -> date:
    """Easter Sunday via the anonymous Gregorian computus."""
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    ell = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * ell) // 451
    month = (h + ell - 7 * m + 114) // 31
    day = ((h + ell - 7 * m + 114) % 31) + 1
    return date(year, month, day)


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    """The nth (1-based) ``weekday`` (Mon=0) of a month."""
    first = date(year, month, 1)
    offset = (weekday - first.weekday()) % 7
    return first + timedelta(days=offset + 7 * (n - 1))


def _last_weekday(year: int, month: int, weekday: int) -> date:
    """The last ``weekday`` (Mon=0) of a month."""
    nxt = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
    last = nxt - timedelta(days=1)
    return last - timedelta(days=(last.weekday() - weekday) % 7)


def _observed(d: date) -> date:
    """NYSE weekend-observation rule for fixed-date holidays."""
    if d.weekday() == 5:      # Saturday -> observed the preceding Friday
        return d - timedelta(days=1)
    if d.weekday() == 6:      # Sunday -> observed the following Monday
        return d + timedelta(days=1)
    return d


def us_market_holidays(year: int) -> dict[date, str]:
    """Full-day US equity-market (NYSE/NASDAQ) holidays for a calendar year."""
    holidays = {
        _observed(date(year, 1, 1)): "New Year's Day",
        _nth_weekday(year, 1, 0, 3): "Martin Luther King Jr. Day",
        _nth_weekday(year, 2, 0, 3): "Washington's Birthday",
        _easter(year) - timedelta(days=2): "Good Friday",
        _last_weekday(year, 5, 0): "Memorial Day",
        _observed(date(year, 7, 4)): "Independence Day",
        _nth_weekday(year, 9, 0, 1): "Labor Day",
        _nth_weekday(year, 11, 3, 4): "Thanksgiving Day",
        _observed(date(year, 12, 25)): "Christmas Day",
    }
    if year >= 2022:  # Juneteenth first observed by the exchanges in 2022
        holidays[_observed(date(year, 6, 19))] = "Juneteenth"
    return holidays


async def load_trading_calendars(
    session: AsyncSession, start_year: int = 2020, end_year: int = 2030
) -> dict[str, int]:
    """Seed trading-calendar definitions and generate their trading-day rows.

    Calendar definitions come from ``trading_calendars.json``. Trading days are
    generated deterministically (weekdays minus US market holidays) over
    ``[start_year, end_year]``. Idempotent via deterministic calendar ids and
    ON CONFLICT upserts. FK values (exchange_mic / country) are only set when
    the referenced row already exists, so the load never fails on a missing FK.
    """
    defs = _load_json("trading_calendars.json")

    existing_mics = set(
        (await session.execute(select(Exchange.mic))).scalars().all()
    )
    existing_countries = set(
        (await session.execute(select(Country.country_code_alpha2))).scalars().all()
    )

    cal_records: list[dict[str, Any]] = []
    day_records: list[dict[str, Any]] = []
    for d in defs:
        code = d["calendar_code"]
        cal_id = uuid.uuid5(_TRADING_CAL_NAMESPACE, code)
        mic = d.get("exchange_mic")
        country = d.get("country")
        cal_records.append({
            "calendar_id": cal_id,
            "calendar_code": code,
            "name": d.get("name"),
            "exchange_mic": mic if mic in existing_mics else None,
            "country": country if country in existing_countries else None,
        })
        for year in range(start_year, end_year + 1):
            holidays = us_market_holidays(year)
            day = date(year, 1, 1)
            year_end = date(year, 12, 31)
            while day <= year_end:
                is_weekend = day.weekday() >= 5
                holiday_name = holidays.get(day)
                is_trading = (not is_weekend) and (holiday_name is None)
                # Record weekday trading days and weekday holidays; weekends are
                # implicitly non-trading and skipped to keep the table compact.
                if not is_weekend:
                    day_records.append({
                        "calendar_id": cal_id,
                        "date": day,
                        "is_trading_day": is_trading,
                        "holiday_name": holiday_name,
                    })
                day += timedelta(days=1)

    cal_stats = await _upsert_batch(
        session, TradingCalendar, cal_records, ["calendar_id"], "trading_calendars"
    )
    day_stats = await _upsert_batch(
        session, TradingDay, day_records, ["calendar_id", "date"], "trading_days"
    )
    return {
        "calendars": cal_stats.get("inserted", 0),
        "trading_days": day_stats.get("inserted", 0),
    }


async def load_all_reference_data(session: AsyncSession) -> dict[str, dict[str, int]]:
    """Load all reference data in dependency order."""
    results = {}

    # Order matters: currencies before countries (FK), countries before exchanges (FK)
    results["currencies"] = await load_currencies(session)
    results["countries"] = await load_countries(session)
    results["exchanges"] = await load_exchanges(session)
    results["gics"] = await load_gics(session)
    results["sic_codes"] = await load_sic_codes(session)
    results["naics_codes"] = await load_naics_codes(session)
    results["sic_to_gics_mapping"] = await load_sic_gics_mapping(session)
    # Trading calendars depend on exchanges + countries being present (FK).
    results["trading_calendars"] = await load_trading_calendars(session)

    await session.flush()

    logger.info("Reference data load complete:")
    for name, stats in results.items():
        logger.info(f"  {name}: {stats}")

    return results
