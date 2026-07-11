"""Tests for the Polygon.io corporate actions connector.

Exercises the pure validate/transform logic on representative Polygon
dividend/split payloads, and the DB load against a seeded security. No
network access.
"""

import uuid

import pytest
from sqlalchemy import select

from src.ingestion.polygon_corporate_actions import PolygonCorporateActionsConnector

SAMPLE_DIVIDEND = {
    "kind": "DIVIDEND",
    "ticker": "AAPL",
    "cash_amount": 0.25,
    "currency": "usd",
    "declaration_date": "2026-01-30",
    "dividend_type": "CD",
    "ex_dividend_date": "2026-02-10",
    "frequency": 4,
    "pay_date": "2026-02-13",
    "record_date": "2026-02-10",
}

SAMPLE_SPLIT = {
    "kind": "SPLIT",
    "ticker": "AAPL",
    "execution_date": "2026-03-15",
    "split_from": 1,
    "split_to": 4,
}

SAMPLE_INCOMPLETE_DIVIDEND = {
    "kind": "DIVIDEND",
    "ticker": "AAPL",
    # missing cash_amount and ex_dividend_date
}


@pytest.mark.asyncio
async def test_validate_drops_incomplete_records():
    conn = PolygonCorporateActionsConnector()
    valid = await conn.validate([SAMPLE_DIVIDEND, SAMPLE_SPLIT, SAMPLE_INCOMPLETE_DIVIDEND])
    assert len(valid) == 2


@pytest.mark.asyncio
async def test_transform_dividend():
    conn = PolygonCorporateActionsConnector()
    out = await conn.transform([SAMPLE_DIVIDEND])
    assert len(out) == 1
    rec = out[0]
    assert rec["action_type"] == "CASH_DIVIDEND"
    assert rec["ex_date"].isoformat() == "2026-02-10"
    assert rec["record_date"].isoformat() == "2026-02-10"
    assert rec["payment_date"].isoformat() == "2026-02-13"
    assert rec["announcement_date"].isoformat() == "2026-01-30"
    assert rec["dividend_type"] == "REGULAR"
    assert rec["frequency"] == "QUARTERLY"
    assert rec["gross_amount"] == 0.25
    assert rec["currency"] == "USD"


@pytest.mark.asyncio
async def test_transform_split():
    conn = PolygonCorporateActionsConnector()
    out = await conn.transform([SAMPLE_SPLIT])
    assert len(out) == 1
    rec = out[0]
    assert rec["action_type"] == "STOCK_SPLIT"
    assert rec["split_ratio_from"] == 1
    assert rec["split_ratio_to"] == 4
    assert rec["split_factor"] == 4.0
    assert rec["ex_date"].isoformat() == "2026-03-15"


@pytest.mark.asyncio
async def test_transform_reverse_split():
    conn = PolygonCorporateActionsConnector()
    rec = dict(SAMPLE_SPLIT, split_from=4, split_to=1)
    out = await conn.transform([rec])
    assert out[0]["action_type"] == "REVERSE_SPLIT"


@pytest.mark.asyncio
async def test_load_writes_corporate_action_with_dates(session):
    from src.models.corporate_actions import CorporateAction, DividendAction
    from src.models.entity import Entity
    from src.models.security import Security, SecurityIdentifier

    entity_id = uuid.uuid4()
    session.add(Entity(
        entity_id=entity_id, entity_type="PUBLIC_COMPANY",
        legal_name="Apple Inc.", status="ACTIVE", source="TEST",
    ))
    security_id = uuid.uuid4()
    session.add(Security(
        security_id=security_id, security_type="COMMON_STOCK",
        issuer_entity_id=entity_id, name="Apple Inc.", status="ACTIVE",
        asset_class="EQUITY",
    ))
    session.add(SecurityIdentifier(
        id=uuid.uuid4(), security_id=security_id,
        identifier_type="TICKER", identifier_value="AAPL",
    ))
    await session.flush()

    conn = PolygonCorporateActionsConnector(tickers=["AAPL"])
    transformed = await conn.transform(await conn.validate([SAMPLE_DIVIDEND]))
    stats = await conn.load(transformed, session)
    assert stats["inserted"] == 1
    await session.flush()

    rows = (await session.execute(select(CorporateAction))).scalars().all()
    assert len(rows) == 1
    action = rows[0]
    assert action.security_id == security_id
    assert action.entity_id == entity_id
    assert action.ex_date.isoformat() == "2026-02-10"
    assert action.record_date.isoformat() == "2026-02-10"
    assert action.payment_date.isoformat() == "2026-02-13"

    div_rows = (await session.execute(select(DividendAction))).scalars().all()
    assert len(div_rows) == 1
    assert div_rows[0].action_id == action.action_id
    assert float(div_rows[0].gross_amount) == 0.25


@pytest.mark.asyncio
async def test_load_skips_unknown_ticker(session):
    conn = PolygonCorporateActionsConnector(tickers=["ZZZZ"])
    transformed = await conn.transform(await conn.validate([SAMPLE_DIVIDEND]))
    stats = await conn.load(transformed, session)
    assert stats["skipped"] == 1
    assert stats["inserted"] == 0


@pytest.mark.asyncio
async def test_load_dedupes_on_rerun(session):
    from src.models.entity import Entity
    from src.models.security import Security, SecurityIdentifier

    entity_id = uuid.uuid4()
    session.add(Entity(
        entity_id=entity_id, entity_type="PUBLIC_COMPANY",
        legal_name="Apple Inc.", status="ACTIVE", source="TEST",
    ))
    security_id = uuid.uuid4()
    session.add(Security(
        security_id=security_id, security_type="COMMON_STOCK",
        issuer_entity_id=entity_id, name="Apple Inc.", status="ACTIVE",
        asset_class="EQUITY",
    ))
    session.add(SecurityIdentifier(
        id=uuid.uuid4(), security_id=security_id,
        identifier_type="TICKER", identifier_value="AAPL",
    ))
    await session.flush()

    conn = PolygonCorporateActionsConnector(tickers=["AAPL"])
    transformed = await conn.transform(await conn.validate([SAMPLE_DIVIDEND]))
    await conn.load(transformed, session)
    await session.flush()
    stats2 = await conn.load(transformed, session)
    assert stats2["inserted"] == 0
    assert stats2["skipped"] == 1
