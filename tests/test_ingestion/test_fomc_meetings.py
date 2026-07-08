"""Tests for the FOMC meetings connector (FRED target-range derivation).

Exercises the pure change-point derivation, the transform, and the DB load of
FedMeeting rows against a representative FRED observations payload. No network.
"""

from decimal import Decimal

import httpx
import pytest
from sqlalchemy import select

from src.ingestion.fomc_meetings import (
    FomcMeetingsConnector,
    derive_rate_decisions,
)

# Representative DFEDTARU / DFEDTARL observation slices spanning two decisions:
# a +25bps hike then a -50bps cut.
UPPER_OBS = [
    {"date": "2023-07-25", "value": "5.25"},
    {"date": "2023-07-26", "value": "5.50"},  # hike +25bps
    {"date": "2023-07-27", "value": "5.50"},
    {"date": "2024-09-18", "value": "5.00"},  # cut -50bps
    {"date": "2024-09-19", "value": "5.00"},
]
LOWER_OBS = [
    {"date": "2023-07-25", "value": "5.00"},
    {"date": "2023-07-26", "value": "5.25"},
    {"date": "2023-07-27", "value": "5.25"},
    {"date": "2024-09-18", "value": "4.75"},
    {"date": "2024-09-19", "value": "4.75"},
]


def test_derive_rate_decisions_detects_changes():
    out = derive_rate_decisions(UPPER_OBS, LOWER_OBS)
    assert len(out) == 2
    hike, cut = out
    assert hike["meeting_date"] == "2023-07-26"
    assert hike["rate_decision"] == "HIKE"
    assert hike["change_bps"] == 25
    assert hike["fed_funds_upper"] == 5.50
    assert cut["meeting_date"] == "2024-09-18"
    assert cut["rate_decision"] == "CUT"
    assert cut["change_bps"] == -50


def test_derive_handles_missing_values():
    out = derive_rate_decisions(
        [{"date": "2023-01-01", "value": "."}, {"date": "2023-01-02", "value": "5.00"}],
        [],
    )
    # First real value establishes baseline; no change detected → empty.
    assert out == []


@pytest.mark.asyncio
async def test_extract_mocked_http(monkeypatch):
    class _Resp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"observations": UPPER_OBS}

    class _Client:
        def __init__(self, *a, **k):
            pass

        async def get(self, url, params=None):
            return _Resp()

        async def aclose(self):
            pass

    monkeypatch.setattr(httpx, "AsyncClient", _Client)
    conn = FomcMeetingsConnector(api_key="test")
    raw = await conn.extract()
    assert len(raw) == 1
    assert raw[0]["upper"] == UPPER_OBS


@pytest.mark.asyncio
async def test_load_inserts_and_upserts(session):
    conn = FomcMeetingsConnector(api_key="test")
    recs = await conn.transform([{"upper": UPPER_OBS, "lower": LOWER_OBS}])
    stats = await conn.load(recs, session)
    assert stats["inserted"] == 2
    await session.flush()

    from src.models.fed_meeting import FedMeeting

    rows = (await session.execute(select(FedMeeting).order_by(FedMeeting.meeting_date))).scalars().all()
    assert len(rows) == 2
    assert rows[0].rate_decision == "HIKE"
    assert rows[0].fed_funds_upper == Decimal("5.50")
    assert rows[0].change_bps == 25

    # Re-load upserts existing rows.
    stats2 = await conn.load(recs, session)
    assert stats2["updated"] == 2
    assert stats2["inserted"] == 0
