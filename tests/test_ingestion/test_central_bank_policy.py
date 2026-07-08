"""Tests for the central-bank policy connector (FRED derivation).

Exercises the pure change-point derivation, transform, and DB load of
CentralBankPolicy rows against a representative FRED payload. No network.
"""

from decimal import Decimal

import httpx
import pytest
from sqlalchemy import select

from src.ingestion.central_bank_policy import (
    CentralBankPolicyConnector,
    derive_policy_changes,
)

OBS = [
    {"date": "2022-03-16", "value": "0.50"},
    {"date": "2022-05-04", "value": "1.00"},  # +50bps hike
    {"date": "2022-05-05", "value": "1.00"},
    {"date": "2024-09-18", "value": "0.50"},  # -50bps cut
]


def test_derive_policy_changes():
    out = derive_policy_changes("FED", OBS)
    assert len(out) == 2
    hike, cut = out
    assert hike["meeting_date"] == "2022-05-04"
    assert hike["policy_rate"] == 1.00
    assert hike["previous_rate"] == 0.50
    assert hike["rate_change"] == 0.50
    assert hike["rate_direction"] == "HIKE"
    assert cut["rate_direction"] == "CUT"
    assert cut["bank_code"] == "FED"


def test_derive_ignores_missing():
    out = derive_policy_changes("ECB", [{"date": "2023-01-01", "value": "."}])
    assert out == []


@pytest.mark.asyncio
async def test_extract_mocked_http(monkeypatch):
    class _Resp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"observations": OBS}

    class _Client:
        def __init__(self, *a, **k):
            pass

        async def get(self, url, params=None):
            return _Resp()

        async def aclose(self):
            pass

    monkeypatch.setattr(httpx, "AsyncClient", _Client)
    conn = CentralBankPolicyConnector(api_key="test", banks={"FED": "DFEDTARU"})
    raw = await conn.extract()
    assert len(raw) == 1
    assert raw[0]["bank_code"] == "FED"


@pytest.mark.asyncio
async def test_load_inserts_and_upserts(session):
    conn = CentralBankPolicyConnector(api_key="test", banks={"FED": "DFEDTARU"})
    recs = await conn.transform([{"bank_code": "FED", "observations": OBS}])
    stats = await conn.load(recs, session)
    assert stats["inserted"] == 2
    await session.flush()

    from src.models.macro import CentralBankPolicy

    rows = (
        await session.execute(
            select(CentralBankPolicy).order_by(CentralBankPolicy.meeting_date)
        )
    ).scalars().all()
    assert len(rows) == 2
    assert rows[0].bank_code == "FED"
    assert rows[0].policy_rate == Decimal("1.00")
    assert rows[0].rate_direction == "HIKE"

    stats2 = await conn.load(recs, session)
    assert stats2["updated"] == 2
    assert stats2["inserted"] == 0
