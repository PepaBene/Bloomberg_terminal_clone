"""Tests for the FINRA TRACE corporate bond connector.

Covers the pure normalize_trade()/aggregate_eod() pipeline (already
unit-tested logic, exercised here end-to-end), the new local-file extract
path (_extract_from_file / _map_academic_trace_row) against a realistic
pipe-delimited Academic TRACE bulk-file fixture, and the connector's
file-not-found / malformed-row defensive error handling. No network access.
"""

import uuid
from decimal import Decimal

import pytest
from sqlalchemy import select

from src.ingestion.finra_trace import (
    FINRATraceConnector,
    _map_academic_trace_row,
    aggregate_eod,
    normalize_trade,
)

# Real Academic/Historical TRACE bulk-file column header, pipe-delimited.
_HEADER = (
    "CUSIP_ID|BOND_SYM_ID|COMPANY_SYMBOL|TRD_EXCTN_DT|TRD_EXCTN_TM|"
    "RPTD_PR|YLD_PT|ENTRD_VOL_QT|RPT_SIDE_CD|CNTRA_MP_ID|SCRTY_TYPE_CD"
)

# 6 synthetic trade rows across 2 CUSIPs and 2 trade dates.
_ROWS = [
    "037833AK6|XYZ4123456|ACME|20260112|093015|101.500000|3.250000|500000|B|C001|CORP",
    "037833AK6|XYZ4123456|ACME|20260112|141522|101.750000|3.200000|250000|S|C002|CORP",
    "037833AK6|XYZ4123456|ACME|20260113|100501|102.000000|3.150000|1000000|B|C003|CORP",
    "594918BP8|MSFT987654|MSFT|20260112|110000|98.250000|4.100000|300000|B|C004|CORP",
    "594918BP8|MSFT987654|MSFT|20260113|093000|98.500000|4.050000|400000|S|C005|CORP",
    "594918BP8|MSFT987654|MSFT|20260113|153000|98.625000|4.000000|600000|B|C006|CORP",
]


def _write_fixture(tmp_path, rows=None, header=_HEADER):
    rows = _ROWS if rows is None else rows
    path = tmp_path / "academic_trace_extract.txt"
    path.write_text("\n".join([header, *rows]) + "\n")
    return str(path)


# ---------------------------------------------------------------------------
# _map_academic_trace_row — pure row-mapping tests
# ---------------------------------------------------------------------------


def test_map_academic_trace_row_maps_real_columns():
    row = {
        "CUSIP_ID": "037833AK6",
        "BOND_SYM_ID": "XYZ4123456",
        "COMPANY_SYMBOL": "ACME",
        "TRD_EXCTN_DT": "20260112",
        "TRD_EXCTN_TM": "093015",
        "RPTD_PR": "101.500000",
        "YLD_PT": "3.250000",
        "ENTRD_VOL_QT": "500000",
        "RPT_SIDE_CD": "B",
        "CNTRA_MP_ID": "C001",
        "SCRTY_TYPE_CD": "CORP",
    }
    mapped = _map_academic_trace_row(row)
    assert mapped == {
        "cusip": "037833AK6",
        "trade_date": "20260112",
        "trade_time": "093015",
        "price": "101.500000",
        "yield": "3.250000",
        "quantity": "500000",
        "side": "B",
        "bond_symbol": "XYZ4123456",
        "company_symbol": "ACME",
        "contra_party": "C001",
        "security_type": "CORP",
    }


def test_map_academic_trace_row_missing_cusip_returns_none():
    assert _map_academic_trace_row({"TRD_EXCTN_DT": "20260112"}) is None


def test_map_academic_trace_row_missing_trade_date_returns_none():
    assert _map_academic_trace_row({"CUSIP_ID": "037833AK6"}) is None


def test_map_academic_trace_row_bridges_into_normalize_trade():
    row = {
        "CUSIP_ID": "037833AK6",
        "TRD_EXCTN_DT": "20260112",
        "TRD_EXCTN_TM": "093015",
        "RPTD_PR": "101.500000",
        "YLD_PT": "3.250000",
        "ENTRD_VOL_QT": "500000",
        "RPT_SIDE_CD": "B",
    }
    mapped = _map_academic_trace_row(row)
    normalized = normalize_trade(mapped)
    assert normalized["cusip"] == "037833AK6"
    assert normalized["trade"]["price"] == Decimal("101.500000")
    assert normalized["trade"]["yield_value"] == Decimal("3.250000")
    assert normalized["trade"]["quantity"] == Decimal("500000")
    assert normalized["trade"]["trade_type"] == "BUY"
    assert normalized["trade"]["source"] == "TRACE"
    # Academic TRACE has no issuer name/CIK column.
    assert normalized["issuer_name"] is None
    assert normalized["issuer_cik"] is None


# ---------------------------------------------------------------------------
# _extract_from_file — delimiter auto-detection + file parsing
# ---------------------------------------------------------------------------


def test_extract_from_file_parses_pipe_delimited_fixture(tmp_path):
    path = _write_fixture(tmp_path)
    conn = FINRATraceConnector(local_file=path)
    records = conn._extract_from_file(path)
    assert len(records) == 6
    assert records[0]["cusip"] == "037833AK6"
    assert records[0]["trade_date"] == "20260112"
    assert records[0]["price"] == "101.500000"
    cusips = {r["cusip"] for r in records}
    assert cusips == {"037833AK6", "594918BP8"}


def test_extract_from_file_detects_comma_delimiter(tmp_path):
    header = _HEADER.replace("|", ",")
    rows = [r.replace("|", ",") for r in _ROWS]
    path = _write_fixture(tmp_path, rows=rows, header=header)
    conn = FINRATraceConnector(local_file=path)
    records = conn._extract_from_file(path)
    assert len(records) == 6
    assert records[0]["cusip"] == "037833AK6"


def test_extract_from_file_detects_tab_delimiter(tmp_path):
    header = _HEADER.replace("|", "\t")
    rows = [r.replace("|", "\t") for r in _ROWS]
    path = _write_fixture(tmp_path, rows=rows, header=header)
    conn = FINRATraceConnector(local_file=path)
    records = conn._extract_from_file(path)
    assert len(records) == 6


def test_extract_from_file_skips_malformed_row_without_crashing(tmp_path):
    rows = list(_ROWS) + ["|||||||||"]  # blank CUSIP + trade date -> skipped
    path = _write_fixture(tmp_path, rows=rows)
    conn = FINRATraceConnector(local_file=path)
    records = conn._extract_from_file(path)
    # Only the 6 well-formed rows survive; the malformed row is skipped, not raised.
    assert len(records) == 6


def test_extract_from_file_missing_file_returns_empty_list(tmp_path):
    missing = str(tmp_path / "does_not_exist.txt")
    conn = FINRATraceConnector(local_file=missing)
    records = conn._extract_from_file(missing)
    assert records == []


@pytest.mark.asyncio
async def test_extract_prefers_local_file_over_live_feed(tmp_path):
    path = _write_fixture(tmp_path)
    conn = FINRATraceConnector(
        local_file=path, endpoint_url="https://example.invalid/trace"
    )
    records = await conn.extract()
    assert len(records) == 6


@pytest.mark.asyncio
async def test_extract_noop_when_nothing_configured():
    conn = FINRATraceConnector(local_file="", endpoint_url="")
    records = await conn.extract()
    assert records == []


# ---------------------------------------------------------------------------
# Full extract -> transform -> aggregate_eod pipeline (file-parsing bridges
# correctly into the already-tested pure functions).
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_full_local_file_pipeline_into_normalize_and_aggregate(tmp_path):
    path = _write_fixture(tmp_path)
    conn = FINRATraceConnector(local_file=path)

    raw = await conn.extract()
    assert len(raw) == 6

    normalized = [normalize_trade(r) for r in raw]
    assert all(n is not None for n in normalized)

    by_cusip: dict[str, list] = {}
    for n in normalized:
        by_cusip.setdefault(n["cusip"], []).append(n)

    assert set(by_cusip) == {"037833AK6", "594918BP8"}
    assert len(by_cusip["037833AK6"]) == 3
    assert len(by_cusip["594918BP8"]) == 3

    eod_037833 = aggregate_eod("037833AK6", by_cusip["037833AK6"])
    eod_by_date = {row["price_date"].isoformat(): row for row in eod_037833}
    assert set(eod_by_date) == {"2026-01-12", "2026-01-13"}

    day1 = eod_by_date["2026-01-12"]
    assert day1["trade_count"] == 2
    assert day1["last_trade_price"] == Decimal("101.750000")
    assert day1["high_price"] == Decimal("101.750000")
    assert day1["low_price"] == Decimal("101.500000")
    expected_vwap = (
        Decimal("101.500000") * Decimal("500000") + Decimal("101.750000") * Decimal("250000")
    ) / Decimal("750000")
    assert day1["vwap"] == expected_vwap

    day2 = eod_037833[0] if eod_037833[0]["price_date"].isoformat() == "2026-01-13" else eod_037833[1]
    assert day2["trade_count"] == 1
    assert day2["last_trade_price"] == Decimal("102.000000")


@pytest.mark.asyncio
async def test_full_pipeline_load_attaches_trades_to_existing_bond_by_cusip(session, tmp_path):
    """Academic TRACE files carry no issuer CIK/name — load() must still
    attach trades to a CUSIP that's already on file in corporate_bonds,
    and must skip (not fabricate) a CUSIP that isn't."""
    from datetime import date

    from src.models.corporate_bond import BondEODPrice, BondTrade, CorporateBond
    from src.models.entity import Entity

    entity_id = uuid.uuid4()
    session.add(
        Entity(
            entity_id=entity_id,
            entity_type="PUBLIC_COMPANY",
            legal_name="Acme Corp",
            status="ACTIVE",
            source="TEST",
        )
    )
    bond_id = uuid.uuid4()
    session.add(
        CorporateBond(
            bond_id=bond_id,
            cusip="037833AK6",
            issuer_entity_id=entity_id,
            issuer_name="Acme Corp",
            name="Acme Corp 4.5% Notes due 2030",
            maturity_date=date(2030, 1, 1),
            status="OUTSTANDING",
        )
    )
    await session.flush()

    path = _write_fixture(tmp_path)
    conn = FINRATraceConnector(local_file=path)

    raw = await conn.extract()
    valid = await conn.validate(raw)
    normalized = await conn.transform(valid)
    stats = await conn.load(normalized, session)

    # 037833AK6 (known CUSIP): bond already exists -> 3 trades + 2 EOD rows inserted.
    # 594918BP8 (unknown CUSIP, no CIK available in Academic TRACE): skipped, not fabricated.
    assert stats["skipped"] == 3
    assert stats["errors"] == 0

    trades = (
        await session.execute(select(BondTrade).where(BondTrade.bond_id == bond_id))
    ).scalars().all()
    assert len(trades) == 3

    eods = (
        await session.execute(select(BondEODPrice).where(BondEODPrice.bond_id == bond_id))
    ).scalars().all()
    assert len(eods) == 2

    # No CorporateBond row was fabricated for the unknown CUSIP.
    unknown_bond = (
        await session.execute(select(CorporateBond).where(CorporateBond.cusip == "594918BP8"))
    ).scalar_one_or_none()
    assert unknown_bond is None
