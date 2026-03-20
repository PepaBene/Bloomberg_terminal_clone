"""Tests for Pillar 2: Screening & Ranking API endpoints (E4).

Covers custom screening, pre-built screen library, saved screens,
universe management, field metadata, and multi-factor ranking.
"""

import uuid
from datetime import date

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.analytics import AnalyticsResult
from src.models.entity import Entity
from src.models.security import Security


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def seeded_screening(session: AsyncSession, client: AsyncClient):
    """Seed entities, securities, and analytics results for screening tests.

    Creates a single entity + security with several analytics metrics so
    that filter/rank endpoints have data to operate on.  Returns a tuple
    of (client, entity, security) for convenience.
    """
    entity = Entity(
        entity_id=uuid.uuid4(),
        legal_name="Screening API Test Corp",
        entity_type="PUBLIC_COMPANY",
        status="ACTIVE",
        incorporation_country="US",
        source="TEST",
        gics_sector="45",
    )
    session.add(entity)
    await session.flush()

    security = Security(
        security_id=uuid.uuid4(),
        name="Screening API Test Corp Stock",
        short_name="SCRT",
        security_type="COMMON_STOCK",
        asset_class="EQUITY",
        status="ACTIVE",
        issuer_entity_id=entity.entity_id,
        primary_exchange_mic="XNAS",
        primary_currency="USD",
    )
    session.add(security)
    await session.flush()

    today = date.today()
    for metric, value, cat in [
        ("pe_trailing", 15.0, "VALUATION"),
        ("roe", 0.20, "PROFITABILITY"),
        ("roic", 0.18, "PROFITABILITY"),
        ("pb", 1.2, "VALUATION"),
        ("current_ratio", 2.5, "LEVERAGE"),
        ("ncav_per_share", 5.0, "PER_SHARE"),
        ("gross_margin", 0.45, "PROFITABILITY"),
        ("debt_to_equity", 0.3, "LEVERAGE"),
    ]:
        session.add(AnalyticsResult(
            result_id=uuid.uuid4(),
            security_id=security.security_id,
            entity_id=entity.entity_id,
            engine_id="E1",
            metric_name=metric,
            metric_category=cat,
            value=value,
            unit="RATIO",
            period="TTM",
            as_of_date=today,
            data_quality="COMPLETE",
        ))
    await session.flush()

    return client, entity, security


# ---------------------------------------------------------------------------
# 1. List pre-built screens
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_prebuilt_screens(client: AsyncClient):
    """GET /v2/analytics/screens/library -> 200, returns 12 screens with correct keys."""
    resp = await client.get("/v2/analytics/screens/library")
    assert resp.status_code == 200

    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 12

    first = data[0]
    assert "screen_id" in first
    assert "name" in first
    assert "description" in first
    assert "tags" in first
    assert "filter_count" in first


# ---------------------------------------------------------------------------
# 2. Get pre-built screen detail
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_prebuilt_screen_detail(client: AsyncClient):
    """GET /v2/analytics/screens/library/graham-net-net -> 200, has filters dict."""
    resp = await client.get("/v2/analytics/screens/library/graham-net-net")
    assert resp.status_code == 200

    data = resp.json()
    assert data["screen_id"] == "graham-net-net"
    assert data["name"] == "Graham Net-Net"
    assert "filters" in data
    assert isinstance(data["filters"], dict)
    assert "logic" in data["filters"]
    assert "filters" in data["filters"]
    assert len(data["filters"]["filters"]) == 2
    assert "tags" in data
    assert "value" in data["tags"]


# ---------------------------------------------------------------------------
# 3. Pre-built screen not found
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_prebuilt_screen_not_found(client: AsyncClient):
    """GET /v2/analytics/screens/library/nonexistent -> 404."""
    resp = await client.get("/v2/analytics/screens/library/nonexistent")
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# 4. Run custom screen
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_custom_screen(seeded_screening):
    """POST /v2/analytics/screen with filter body -> 200, returns ScreenResult."""
    client, entity, security = seeded_screening

    body = {
        "universe": "ALL",
        "filters": {
            "logic": "AND",
            "filters": [
                {"field": "pe_trailing", "source": "ANALYTICS_RESULT", "op": "LT", "value": 20},
                {"field": "roe", "source": "ANALYTICS_RESULT", "op": "GT", "value": 0.10},
            ],
        },
        "limit": 50,
    }
    resp = await client.post("/v2/analytics/screen", json=body)
    assert resp.status_code == 200

    data = resp.json()
    assert "total_matches" in data
    assert "securities" in data
    assert "execution_time_ms" in data
    assert data["total_matches"] >= 1

    # The seeded security should pass both filters (pe=15 < 20, roe=0.20 > 0.10)
    sids = [s["security_id"] for s in data["securities"]]
    assert str(security.security_id) in sids


# ---------------------------------------------------------------------------
# 5. Screen fields metadata
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_screen_fields(client: AsyncClient):
    """GET /v2/analytics/screen/fields -> 200, returns total_fields and fields list."""
    resp = await client.get("/v2/analytics/screen/fields")
    assert resp.status_code == 200

    data = resp.json()
    assert "total_fields" in data
    assert "fields" in data
    assert data["total_fields"] > 0
    assert len(data["fields"]) == data["total_fields"]

    # Verify field structure
    field = data["fields"][0]
    assert "field_name" in field
    assert "source" in field
    assert "data_type" in field
    assert "description" in field
    assert "category" in field


# ---------------------------------------------------------------------------
# 6. Save screen
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_save_screen(client: AsyncClient):
    """POST /v2/analytics/screens/save -> 200, returns screen_id."""
    body = {
        "name": "My Test Screen",
        "description": "A test saved screen",
        "definition": {
            "universe": "ALL",
            "filters": {
                "logic": "AND",
                "filters": [
                    {"field": "pe_trailing", "source": "ANALYTICS_RESULT", "op": "LT", "value": 15},
                ],
            },
            "limit": 100,
        },
        "tags": ["test", "value"],
    }
    resp = await client.post("/v2/analytics/screens/save", json=body)
    assert resp.status_code == 200

    data = resp.json()
    assert "screen_id" in data
    assert data["name"] == "My Test Screen"
    assert data["description"] == "A test saved screen"
    assert data["screen_type"] == "CUSTOM"
    assert data["is_prebuilt"] is False


# ---------------------------------------------------------------------------
# 7. List saved screens
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_saved_screens(client: AsyncClient):
    """GET /v2/analytics/screens/saved -> 200, returns list.

    First saves a screen, then verifies it appears in the listing.
    """
    save_body = {
        "name": "Saved List Test Screen",
        "definition": {
            "universe": "ALL",
            "filters": {
                "logic": "AND",
                "filters": [
                    {"field": "roe", "source": "ANALYTICS_RESULT", "op": "GT", "value": 0.10},
                ],
            },
            "limit": 50,
        },
    }
    save_resp = await client.post("/v2/analytics/screens/save", json=save_body)
    assert save_resp.status_code == 200

    resp = await client.get("/v2/analytics/screens/saved")
    assert resp.status_code == 200

    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1

    names = [s["name"] for s in data]
    assert "Saved List Test Screen" in names


# ---------------------------------------------------------------------------
# 8. Universe: US equities
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_universe_us_equities(seeded_screening):
    """GET /v2/analytics/universe/us-equities -> 200, returns UniverseResponse.

    The seeded security has primary_exchange_mic=XNAS so it should appear.
    """
    client, entity, security = seeded_screening

    resp = await client.get("/v2/analytics/universe/us-equities")
    assert resp.status_code == 200

    data = resp.json()
    assert data["universe_name"] == "US_EQUITIES"
    assert "security_count" in data
    assert "security_ids" in data
    assert data["security_count"] >= 1
    assert str(security.security_id) in data["security_ids"]


# ---------------------------------------------------------------------------
# 9. Universe: S&P 500
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_universe_sp500(client: AsyncClient):
    """GET /v2/analytics/universe/sp500 -> 200, returns empty or populated."""
    resp = await client.get("/v2/analytics/universe/sp500")
    assert resp.status_code == 200

    data = resp.json()
    assert data["universe_name"] == "SP500"
    assert "security_count" in data
    assert "security_ids" in data
    assert isinstance(data["security_ids"], list)
    # No S&P 500 universe seeded, so expect empty
    assert data["security_count"] == 0


# ---------------------------------------------------------------------------
# 10. Create custom universe
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_custom_universe(client: AsyncClient):
    """POST /v2/analytics/universe/custom -> 200, returns UniverseResponse."""
    sid1 = uuid.uuid4()
    sid2 = uuid.uuid4()

    body = {
        "name": "My Custom Universe",
        "security_ids": [str(sid1), str(sid2)],
    }
    resp = await client.post("/v2/analytics/universe/custom", json=body)
    assert resp.status_code == 200

    data = resp.json()
    assert data["universe_name"] == "My Custom Universe"
    assert data["security_count"] == 2
    assert len(data["security_ids"]) == 2
    assert str(sid1) in data["security_ids"]
    assert str(sid2) in data["security_ids"]
