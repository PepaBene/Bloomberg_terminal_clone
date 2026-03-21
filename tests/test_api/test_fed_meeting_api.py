"""Tests for Central Bank (Fed) API endpoints."""

import uuid
from datetime import date

import pytest

from src.models.fed_meeting import FedMeeting


@pytest.mark.asyncio
async def test_get_latest_fed_meeting_not_found(client):
    """Test 404 when no Fed meetings exist."""
    response = await client.get("/v1/macro/central-bank/fed")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_latest_fed_meeting(client, session):
    """Test fetching the most recent FOMC meeting."""
    session.add(FedMeeting(
        meeting_id=uuid.uuid4(),
        meeting_date=date(2026, 1, 29),
        meeting_type="SCHEDULED",
        rate_decision="HOLD",
        fed_funds_lower=0.0525,
        fed_funds_upper=0.0550,
        change_bps=0,
    ))
    session.add(FedMeeting(
        meeting_id=uuid.uuid4(),
        meeting_date=date(2026, 3, 19),
        meeting_type="SCHEDULED",
        rate_decision="CUT",
        fed_funds_lower=0.0500,
        fed_funds_upper=0.0525,
        change_bps=-25,
    ))
    await session.flush()

    response = await client.get("/v1/macro/central-bank/fed")
    assert response.status_code == 200
    data = response.json()
    assert data["meeting_date"] == "2026-03-19"
    assert data["rate_decision"] == "CUT"
    assert data["change_bps"] == -25


@pytest.mark.asyncio
async def test_list_fed_meetings_empty(client):
    """Test listing Fed meetings when empty."""
    response = await client.get("/v1/macro/central-bank/fed/meetings")
    assert response.status_code == 200
    data = response.json()
    assert data["data"] == []


@pytest.mark.asyncio
async def test_list_fed_meetings(client, session):
    """Test listing FOMC meetings."""
    for i, (d, decision) in enumerate([
        (date(2026, 1, 29), "HOLD"),
        (date(2026, 3, 19), "CUT"),
        (date(2026, 5, 7), "HOLD"),
    ]):
        session.add(FedMeeting(
            meeting_id=uuid.uuid4(),
            meeting_date=d,
            meeting_type="SCHEDULED",
            rate_decision=decision,
        ))
    await session.flush()

    response = await client.get("/v1/macro/central-bank/fed/meetings")
    assert response.status_code == 200
    data = response.json()
    assert data["meta"]["total_count"] == 3


@pytest.mark.asyncio
async def test_list_fed_meetings_filter_decision(client, session):
    """Test filtering Fed meetings by rate decision."""
    session.add(FedMeeting(
        meeting_id=uuid.uuid4(),
        meeting_date=date(2026, 1, 29),
        meeting_type="SCHEDULED",
        rate_decision="HOLD",
    ))
    session.add(FedMeeting(
        meeting_id=uuid.uuid4(),
        meeting_date=date(2026, 3, 19),
        meeting_type="SCHEDULED",
        rate_decision="CUT",
    ))
    await session.flush()

    response = await client.get(
        "/v1/macro/central-bank/fed/meetings",
        params={"decision": "CUT"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["meta"]["total_count"] == 1
    assert data["data"][0]["rate_decision"] == "CUT"


@pytest.mark.asyncio
async def test_list_fed_meetings_date_range(client, session):
    """Test filtering Fed meetings by date range."""
    for d in [date(2026, 1, 29), date(2026, 3, 19), date(2026, 5, 7)]:
        session.add(FedMeeting(
            meeting_id=uuid.uuid4(),
            meeting_date=d,
            meeting_type="SCHEDULED",
            rate_decision="HOLD",
        ))
    await session.flush()

    response = await client.get(
        "/v1/macro/central-bank/fed/meetings",
        params={"start": "2026-02-01", "end": "2026-04-01"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["meta"]["total_count"] == 1
