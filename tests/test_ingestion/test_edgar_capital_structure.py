"""Tests for the SEC EDGAR capital structure connector.

No test previously existed for this connector at all. Covers the pure
debt-instrument / call-date extraction regexes, and the DB load including
the new DebtTranche -> Security resolution that populates
FixedIncomeDetails + CallPutSchedule (Pillar 1 Open Items #4 — both
previously had zero writers).
"""

import uuid
from datetime import date

import pytest
from sqlalchemy import select

from src.ingestion.edgar_capital_structure import (
    EdgarCapitalStructureConnector,
    classify_seniority,
    extract_call_date,
    extract_coupon_rate,
    extract_maturity_year,
    parse_debt_instruments,
)

FOOTNOTE_TEXT = (
    "In March 2020, the Company issued $500,000,000 of 4.875% Senior Notes due 2030 "
    "(the \"2030 Notes\"). The 2030 Notes are redeemable, in whole or in part, at any "
    "time on or after March 1, 2025, at the redemption prices set forth in the "
    "indenture. Interest is payable semi-annually."
)


def test_parse_debt_instruments_pure():
    tranches = parse_debt_instruments(FOOTNOTE_TEXT)
    assert len(tranches) == 1
    assert "4.875% Senior Notes due 2030" == tranches[0]["instrument_name"]


def test_extract_coupon_and_maturity_and_seniority():
    name = "4.875% Senior Notes due 2030"
    assert extract_coupon_rate(name) == pytest.approx(0.04875)
    assert extract_maturity_year(name) == 2030
    assert classify_seniority(name) == "SENIOR_UNSECURED"


def test_extract_call_date_finds_optional_redemption_clause():
    call_date = extract_call_date(FOOTNOTE_TEXT, "4.875% Senior Notes due 2030")
    assert call_date == date(2025, 3, 1)


def test_extract_call_date_returns_none_when_absent():
    text = "The Company issued 4.875% Senior Notes due 2030 with no call feature."
    assert extract_call_date(text, "4.875% Senior Notes due 2030") is None


@pytest.mark.asyncio
async def test_load_populates_fixed_income_details_and_call_schedule(session):
    from src.models.capital_structure import CapitalStructure, DebtTranche
    from src.models.entity import Entity, EntityIdentifier
    from src.models.security import CallPutSchedule, FixedIncomeDetails, Security

    entity_id = uuid.uuid4()
    session.add(Entity(
        entity_id=entity_id, entity_type="PUBLIC_COMPANY",
        legal_name="MegaCorp Inc.", status="ACTIVE", source="TEST",
    ))
    session.add(EntityIdentifier(
        id=uuid.uuid4(), entity_id=entity_id,
        identifier_type="CIK", identifier_value="0009000000",
    ))
    # A pre-existing traded FI security for the same issuer, maturing 2030 —
    # this is the "already ingested elsewhere" security the tranche resolves to.
    security_id = uuid.uuid4()
    session.add(Security(
        security_id=security_id, security_type="CORPORATE_BOND",
        issuer_entity_id=entity_id, name="MegaCorp 2030 Notes",
        status="ACTIVE", asset_class="FIXED_INCOME",
        maturity_date=date(2030, 6, 15),
    ))
    await session.flush()

    conn = EdgarCapitalStructureConnector(ciks=["0009000000"])
    rec = {
        "cik": "0009000000",
        "as_of_date": date(2025, 12, 31),
        "total_debt": 500_000_000,
        "tranches": [{
            "instrument_name": "4.875% Senior Notes due 2030",
            "first_call_date": "2025-03-01",
        }],
    }
    transformed = await conn.transform([rec])
    stats = await conn.load(transformed, session)
    assert stats["inserted"] == 1
    assert stats["fi_details_inserted"] == 1
    assert stats["call_schedule_inserted"] == 1
    await session.flush()

    tranches = (await session.execute(select(DebtTranche))).scalars().all()
    assert len(tranches) == 1
    assert tranches[0].security_id == security_id
    # DebtTranche.coupon_rate is Numeric(8, 4) -> 4 decimal places of storage.
    assert float(tranches[0].coupon_rate) == pytest.approx(0.0488, abs=1e-4)
    assert tranches[0].first_call_date == date(2025, 3, 1)

    fi_details = await session.get(FixedIncomeDetails, security_id)
    assert fi_details is not None
    assert float(fi_details.coupon_rate) == pytest.approx(0.0488, abs=1e-4)
    assert fi_details.seniority == "SENIOR_UNSECURED"

    call_rows = (await session.execute(select(CallPutSchedule))).scalars().all()
    assert len(call_rows) == 1
    assert call_rows[0].security_id == security_id
    assert call_rows[0].schedule_type == "CALL"
    assert call_rows[0].effective_date == date(2025, 3, 1)


@pytest.mark.asyncio
async def test_load_skips_fi_details_when_no_matching_security(session):
    from src.models.entity import Entity, EntityIdentifier
    from src.models.security import FixedIncomeDetails

    entity_id = uuid.uuid4()
    session.add(Entity(
        entity_id=entity_id, entity_type="PUBLIC_COMPANY",
        legal_name="MegaCorp Inc.", status="ACTIVE", source="TEST",
    ))
    session.add(EntityIdentifier(
        id=uuid.uuid4(), entity_id=entity_id,
        identifier_type="CIK", identifier_value="0009000000",
    ))
    await session.flush()

    conn = EdgarCapitalStructureConnector(ciks=["0009000000"])
    rec = {
        "cik": "0009000000",
        "as_of_date": date(2025, 12, 31),
        "total_debt": 500_000_000,
        "tranches": [{"instrument_name": "4.875% Senior Notes due 2030"}],
    }
    transformed = await conn.transform([rec])
    stats = await conn.load(transformed, session)
    assert stats["inserted"] == 1
    assert stats["fi_details_inserted"] == 0

    rows = (await session.execute(select(FixedIncomeDetails))).scalars().all()
    assert len(rows) == 0
