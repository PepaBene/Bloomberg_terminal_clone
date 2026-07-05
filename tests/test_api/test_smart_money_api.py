"""API tests for the Financial Analysis Suite: smart-money, auto-model, structure."""

import uuid

import pytest


# ── Smart-money registry & congress ──────────────────────────────────────

@pytest.mark.asyncio
async def test_list_notable_investors(client):
    resp = await client.get("/v1/smart-money/investors")
    assert resp.status_code == 200
    names = {i["display_name"] for i in resp.json()}
    assert {"Michael Burry", "Jamie Dimon", "Nancy Pelosi"} <= names


@pytest.mark.asyncio
async def test_filter_investors_by_category(client):
    resp = await client.get("/v1/smart-money/investors", params={"category": "POLITICIAN"})
    assert resp.status_code == 200
    data = resp.json()
    assert data
    assert all(i["category"] == "POLITICIAN" for i in data)


@pytest.mark.asyncio
async def test_get_investor_by_key(client):
    resp = await client.get("/v1/smart-money/investors/michael_burry")
    assert resp.status_code == 200
    assert resp.json()["category"] == "GURU_13F"


@pytest.mark.asyncio
async def test_get_investor_not_found(client):
    resp = await client.get("/v1/smart-money/investors/does-not-exist")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_profile_rejects_non_13f_filer(client):
    # Jamie Dimon is an insider, not a 13F filer → 400.
    resp = await client.get("/v1/smart-money/filers/jamie_dimon/profile")
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_congress_empty(client):
    resp = await client.get("/v1/smart-money/congress")
    assert resp.status_code == 200
    assert resp.json() == []


# ── Auto Model Builder ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_model_scopes(client):
    resp = await client.get("/v1/models/scopes")
    assert resp.status_code == 200
    assert "COMPANY" in resp.json()["scopes"]


@pytest.mark.asyncio
async def test_build_company_model(client):
    resp = await client.post(
        "/v1/models/build",
        json={
            "scope": "COMPANY",
            "subject": "TestCo",
            "data": {"revenue_growth": 20, "dcf_upside_pct": 30, "piotroski": 8,
                     "altman_z": 6, "smart_money_signal": "BULLISH"},
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["scope"] == "COMPANY"
    assert body["rating"] in ("BUY", "STRONG_BUY", "NEUTRAL")
    assert 0 <= body["composite_score"] <= 100


@pytest.mark.asyncio
async def test_build_unknown_scope_400(client):
    resp = await client.post("/v1/models/build", json={"scope": "BOGUS", "data": {}})
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_build_economic_model(client):
    resp = await client.post(
        "/v1/models/build",
        json={"scope": "ECONOMIC", "data": {"gdp_growth": 3.0, "inflation": 2.0, "policy_rate": 2.0}},
    )
    assert resp.status_code == 200
    assert resp.json()["rating"] == "EXPANSION"


@pytest.mark.asyncio
async def test_company_model_entity_404(client):
    resp = await client.get(f"/v1/models/company/{uuid.uuid4()}")
    assert resp.status_code == 404


# ── Complex Structure ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_analyze_structure_payload(client):
    resp = await client.post(
        "/v1/complex-structure/analyze",
        json={
            "subject": "MegaCorp",
            "share_classes": [
                {"class_name": "A", "shares_outstanding": 90, "votes_per_share": 1},
                {"class_name": "B", "shares_outstanding": 10, "votes_per_share": 10},
            ],
            "off_balance_sheet": {"vie_assets": 80},
            "total_assets": 100,
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["share_classes"]["is_dual_class"] is True
    assert body["complexity_rating"] in ("MODERATE", "COMPLEX", "VERY_COMPLEX")


@pytest.mark.asyncio
async def test_structure_entity_404(client):
    resp = await client.get(f"/v1/complex-structure/entity/{uuid.uuid4()}")
    assert resp.status_code == 404
