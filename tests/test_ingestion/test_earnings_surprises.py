"""Tests for the earnings-surprise connector.

Exercises the pure surprise math, validation, transform, and the DB load of
EarningsSurprise rows against a seeded entity. Inputs are representative
actual/consensus pairs (not fabricated market data — supplied by the test).
"""

import uuid
from decimal import Decimal

import pytest
from sqlalchemy import select

from src.ingestion.earnings_surprises_ingest import (
    EarningsSurprisesConnector,
    compute_surprise,
)


def test_compute_surprise_basic():
    assert compute_surprise(1.20, 1.00) == (0.20, 20.0)
    assert compute_surprise(0.80, 1.00) == (-0.20, -20.0)


def test_compute_surprise_edge_cases():
    assert compute_surprise(None, 1.0) == (None, None)
    assert compute_surprise(1.0, None) == (None, None)
    # Zero consensus → surprise value but no percentage (no div-by-zero).
    assert compute_surprise(0.5, 0.0) == (0.5, None)


@pytest.mark.asyncio
async def test_validate_requires_a_pair():
    conn = EarningsSurprisesConnector()
    eid = uuid.uuid4()
    recs = [
        {"entity_id": eid, "fiscal_year": 2024, "fiscal_quarter": 1},  # no pair
        {"entity_id": eid, "fiscal_year": 2024, "fiscal_quarter": 2, "actual_eps": 1.1, "consensus_eps": 1.0},
    ]
    valid = await conn.validate(recs)
    assert len(valid) == 1
    assert valid[0]["fiscal_quarter"] == 2


@pytest.mark.asyncio
async def test_transform_computes_metrics():
    conn = EarningsSurprisesConnector()
    eid = uuid.uuid4()
    recs = [
        {
            "entity_id": eid,
            "fiscal_year": 2024,
            "fiscal_quarter": 1,
            "actual_eps": 1.20,
            "consensus_eps": 1.00,
            "actual_revenue": 110.0,
            "consensus_revenue": 100.0,
        }
    ]
    out = await conn.transform(recs)
    assert out[0]["eps_surprise"] == 0.20
    assert out[0]["eps_surprise_pct"] == 20.0
    assert out[0]["revenue_surprise"] == 10.0
    assert out[0]["revenue_surprise_pct"] == 10.0


@pytest.mark.asyncio
async def test_load_inserts_and_upserts(session):
    from src.models.entity import Entity

    eid = uuid.uuid4()
    session.add(Entity(entity_id=eid, entity_type="PUBLIC_COMPANY", legal_name="Acme", status="ACTIVE", source="TEST"))
    await session.flush()

    conn = EarningsSurprisesConnector()
    recs = await conn.transform(
        [
            {
                "entity_id": eid,
                "fiscal_year": 2024,
                "fiscal_quarter": 1,
                "announcement_date": "2024-04-25",
                "actual_eps": 1.20,
                "consensus_eps": 1.00,
            }
        ]
    )
    stats = await conn.load(recs, session)
    assert stats["inserted"] == 1
    await session.flush()

    from src.models.earnings_intelligence import EarningsSurprise

    rows = (await session.execute(select(EarningsSurprise))).scalars().all()
    assert len(rows) == 1
    assert rows[0].eps_surprise == Decimal("0.2000")
    assert rows[0].eps_surprise_pct == Decimal("20.0000")

    stats2 = await conn.load(recs, session)
    assert stats2["updated"] == 1
    assert stats2["inserted"] == 0
