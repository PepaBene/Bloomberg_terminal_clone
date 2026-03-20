"""Reference data loader — seeds DB from static JSON files (Spec 10)."""

import json
import logging
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

    await session.flush()

    logger.info("Reference data load complete:")
    for name, stats in results.items():
        logger.info(f"  {name}: {stats}")

    return results
