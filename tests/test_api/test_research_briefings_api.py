"""API tests for Research Briefings endpoints (Pillar 3 Phase 4A).

M-004: user_id is now derived from the authenticated caller
(Depends(get_current_active_user)) rather than an arbitrary caller-supplied
query param, so every test authenticates as a real seeded User via the
shared `test_user`/`auth_headers` fixtures (tests/test_api/conftest.py).
"""

import uuid
from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth.security import hash_password
from src.models.auth import User
from src.models.morning_briefing import MorningBriefing, BriefingPreference


# ── Helpers ──────────────────────────────────────────────────────────


async def _seed_briefing(session, user_id, briefing_date=None):
    bid = uuid.uuid4()
    bdate = briefing_date or date.today()
    briefing = MorningBriefing(
        id=bid,
        user_id=user_id,
        briefing_date=bdate,
        regional_context="US",
        executive_summary="Markets rallied on positive earnings.",
        portfolio_impact={"top_movers": [{"ticker": "AAPL", "change_pct": 2.1}]},
        key_news={"headlines": ["Fed holds rates steady"]},
        thesis_updates={"updates": [{"entity": "GOOGL", "status": "ON_TRACK"}]},
        macro_context={"us_10y": 4.15, "vix": 16.5},
        actionable_insights={"actions": ["Increase AAPL weighting"]},
        delivery_format="FULL",
        ai_enabled=True,
    )
    session.add(briefing)
    await session.flush()
    return briefing


async def _seed_preference(session, user_id):
    pid = uuid.uuid4()
    pref = BriefingPreference(
        id=pid,
        user_id=user_id,
        portfolio_entity_ids={"ids": ["id1", "id2"]},
        watchlist_entity_ids={"ids": ["id3"]},
        sector_focus={"sectors": ["Technology"]},
        risk_tolerance="MODERATE",
        delivery_time_utc="06:30",
        delivery_format="SUMMARY",
        timezone="America/New_York",
        is_active=True,
    )
    session.add(pref)
    await session.flush()
    return pref


async def _seed_other_user(session) -> User:
    """A second real user, distinct from `test_user`, so tests can prove
    data scoping (querying as A never returns B's rows)."""
    user = User(
        user_id=uuid.uuid4(),
        username=f"other_user_{uuid.uuid4().hex[:8]}",
        email=f"{uuid.uuid4().hex[:8]}@test.example",
        hashed_password=hash_password("other-password"),
        role="ANALYST",
        is_active=True,
    )
    session.add(user)
    await session.flush()
    return user


# ── Auth enforcement ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_briefings_require_auth(client: AsyncClient, session: AsyncSession):
    """No Bearer token -> 401, not a silent 'default_user' fallback."""
    resp = await client.get("/v4/research/briefings/today")
    assert resp.status_code == 401


# ── GET /research/briefings/today ────────────────────────────────────


@pytest.mark.asyncio
async def test_today_briefing_empty(client: AsyncClient, session: AsyncSession, auth_headers):
    """GET /v4/research/briefings/today returns empty list when no data for this user."""
    resp = await client.get("/v4/research/briefings/today", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_today_briefing_with_data(client: AsyncClient, session: AsyncSession, test_user, auth_headers):
    """GET /v4/research/briefings/today returns today's briefing for the authenticated user."""
    await _seed_briefing(session, user_id=test_user.user_id, briefing_date=date.today())
    resp = await client.get("/v4/research/briefings/today", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert data[0]["user_id"] == str(test_user.user_id)


@pytest.mark.asyncio
async def test_today_briefing_scoped_to_caller(client: AsyncClient, session: AsyncSession, auth_headers):
    """A briefing seeded for a different user never appears for the caller."""
    other = await _seed_other_user(session)
    await _seed_briefing(session, user_id=other.user_id, briefing_date=date.today())
    resp = await client.get("/v4/research/briefings/today", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_today_briefing_wrong_date(client: AsyncClient, session: AsyncSession, test_user, auth_headers):
    """GET /v4/research/briefings/today does not return old briefings."""
    await _seed_briefing(session, user_id=test_user.user_id, briefing_date=date(2020, 1, 1))
    resp = await client.get("/v4/research/briefings/today", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json() == []


# ── GET /research/briefings/history ──────────────────────────────────


@pytest.mark.asyncio
async def test_briefing_history_empty(client: AsyncClient, session: AsyncSession, auth_headers):
    """GET /v4/research/briefings/history returns empty when nothing seeded."""
    resp = await client.get("/v4/research/briefings/history", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_briefing_history_with_data(client: AsyncClient, session: AsyncSession, test_user, auth_headers):
    """GET /v4/research/briefings/history returns all briefings for the caller."""
    await _seed_briefing(session, user_id=test_user.user_id, briefing_date=date(2025, 10, 1))
    await _seed_briefing(session, user_id=test_user.user_id, briefing_date=date(2025, 10, 2))
    resp = await client.get("/v4/research/briefings/history", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2


@pytest.mark.asyncio
async def test_briefing_history_limit(client: AsyncClient, session: AsyncSession, test_user, auth_headers):
    """GET /v4/research/briefings/history respects limit."""
    await _seed_briefing(session, user_id=test_user.user_id, briefing_date=date(2025, 10, 1))
    await _seed_briefing(session, user_id=test_user.user_id, briefing_date=date(2025, 10, 2))
    resp = await client.get(
        "/v4/research/briefings/history", params={"limit": 1}, headers=auth_headers,
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 1


# ── GET /research/briefings/preferences ──────────────────────────────


@pytest.mark.asyncio
async def test_preferences_none(client: AsyncClient, session: AsyncSession, auth_headers):
    """GET /v4/research/briefings/preferences returns null when none set."""
    resp = await client.get("/v4/research/briefings/preferences", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json() is None


@pytest.mark.asyncio
async def test_preferences_with_data(client: AsyncClient, session: AsyncSession, test_user, auth_headers):
    """GET /v4/research/briefings/preferences returns preferences."""
    await _seed_preference(session, user_id=test_user.user_id)
    resp = await client.get("/v4/research/briefings/preferences", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["user_id"] == str(test_user.user_id)
    assert data["risk_tolerance"] == "MODERATE"
    assert data["delivery_format"] == "SUMMARY"


# ── PUT /research/briefings/preferences ──────────────────────────────


@pytest.mark.asyncio
async def test_create_preferences(client: AsyncClient, session: AsyncSession, test_user, auth_headers):
    """PUT /v4/research/briefings/preferences creates new preferences for the caller."""
    resp = await client.put(
        "/v4/research/briefings/preferences",
        json={
            "risk_tolerance": "AGGRESSIVE",
            "delivery_format": "FULL",
            "timezone": "Europe/London",
            "is_active": True,
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["user_id"] == str(test_user.user_id)
    assert data["risk_tolerance"] == "AGGRESSIVE"


@pytest.mark.asyncio
async def test_update_preferences(client: AsyncClient, session: AsyncSession, test_user, auth_headers):
    """PUT /v4/research/briefings/preferences updates existing preferences."""
    await _seed_preference(session, user_id=test_user.user_id)
    resp = await client.put(
        "/v4/research/briefings/preferences",
        json={
            "risk_tolerance": "CONSERVATIVE",
            "delivery_format": "FULL",
            "is_active": False,
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["risk_tolerance"] == "CONSERVATIVE"
    assert data["is_active"] is False


# ── GET /research/briefings/portfolio-impact ─────────────────────────


@pytest.mark.asyncio
async def test_portfolio_impact_no_briefing(client: AsyncClient, session: AsyncSession, auth_headers):
    """GET /v4/research/briefings/portfolio-impact returns null impact when no briefing."""
    resp = await client.get("/v4/research/briefings/portfolio-impact", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["portfolio_impact"] is None


@pytest.mark.asyncio
async def test_portfolio_impact_with_data(client: AsyncClient, session: AsyncSession, test_user, auth_headers):
    """GET /v4/research/briefings/portfolio-impact returns impact from today's briefing."""
    await _seed_briefing(session, user_id=test_user.user_id, briefing_date=date.today())
    resp = await client.get("/v4/research/briefings/portfolio-impact", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["portfolio_impact"] is not None
    assert data["portfolio_impact"]["top_movers"][0]["ticker"] == "AAPL"


# ── GET /research/briefings/macro-summary ────────────────────────────


@pytest.mark.asyncio
async def test_macro_summary_no_briefing(client: AsyncClient, session: AsyncSession, auth_headers):
    """GET /v4/research/briefings/macro-summary returns null when no briefing."""
    resp = await client.get("/v4/research/briefings/macro-summary", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["macro_context"] is None


@pytest.mark.asyncio
async def test_macro_summary_with_data(client: AsyncClient, session: AsyncSession, test_user, auth_headers):
    """GET /v4/research/briefings/macro-summary returns macro from today."""
    await _seed_briefing(session, user_id=test_user.user_id, briefing_date=date.today())
    resp = await client.get("/v4/research/briefings/macro-summary", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["macro_context"] is not None


# ── POST /research/briefings/generate ────────────────────────────────


@pytest.mark.asyncio
async def test_generate_briefing(client: AsyncClient, session: AsyncSession, test_user, auth_headers):
    """POST /v4/research/briefings/generate creates a new briefing for the caller."""
    resp = await client.post("/v4/research/briefings/generate", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["user_id"] == str(test_user.user_id)
    # No ANTHROPIC_API_KEY in the test environment — executive_summary must
    # be None (honest "AI unavailable"), not a fabricated placeholder string.
    assert data["executive_summary"] is None
    assert data["ai_enabled"] is False
    assert data["briefing_date"] == str(date.today())


# ── GET /research/briefings/{briefing_id} ────────────────────────────


@pytest.mark.asyncio
async def test_get_briefing_by_id_not_found(client: AsyncClient, session: AsyncSession, auth_headers):
    """GET /v4/research/briefings/{briefing_id} returns 404 for unknown."""
    resp = await client.get(f"/v4/research/briefings/{uuid.uuid4()}", headers=auth_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_briefing_by_id_with_data(client: AsyncClient, session: AsyncSession, test_user, auth_headers):
    """GET /v4/research/briefings/{briefing_id} returns the specific briefing."""
    briefing = await _seed_briefing(session, user_id=test_user.user_id)
    resp = await client.get(f"/v4/research/briefings/{briefing.id}", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["user_id"] == str(test_user.user_id)
    assert data["regional_context"] == "US"
