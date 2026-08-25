"""API tests for the Layer 1 Interpreter endpoints (src/api/routers/interpret.py).

No live ANTHROPIC_API_KEY in the test env, so these exercise the
not-yet-cached (AI disabled -> 503/empty) and already-cached (seeded
Interpretation row -> served without needing AI) paths -- the AI
computation path itself is covered by tests/test_ai/test_interpret_store.py's
FakeStructuredClient tests.
"""
from __future__ import annotations

import uuid
from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.analytics import AnalyticsResult
from src.models.entity import Entity
from src.models.interpretation import Interpretation
from src.models.security import Security


async def _seed_entity(session: AsyncSession, name: str = "Interpret Test Corp") -> uuid.UUID:
    entity_id = uuid.uuid4()
    session.add(Entity(
        entity_id=entity_id, entity_type="PUBLIC_COMPANY",
        legal_name=name, status="ACTIVE", source="TEST",
    ))
    await session.commit()
    return entity_id


async def _seed_entity_with_roe(session: AsyncSession) -> uuid.UUID:
    entity_id = await _seed_entity(session)
    security_id = uuid.uuid4()
    session.add(Security(
        security_id=security_id, security_type="COMMON_STOCK",
        issuer_entity_id=entity_id, name="Common Stock",
        status="ACTIVE", asset_class="EQUITY",
    ))
    session.add(AnalyticsResult(
        result_id=uuid.uuid4(), security_id=security_id, entity_id=entity_id,
        engine_id="E1", metric_name="ROE", metric_category="PROFITABILITY",
        value=18.0, unit="PERCENT", period="FY2025", as_of_date=date(2026, 1, 1),
    ))
    await session.commit()
    return entity_id


@pytest.mark.asyncio
async def test_entity_interpretation_404_for_unknown_entity(client: AsyncClient):
    resp = await client.get(f"/v5/interpret/entities/{uuid.uuid4()}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_entity_interpretation_no_analytics_returns_empty(client: AsyncClient, session: AsyncSession):
    entity_id = await _seed_entity(session)
    resp = await client.get(f"/v5/interpret/entities/{entity_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["entity_id"] == str(entity_id)
    assert data["metrics"] == {}
    assert data["subject"] is None


@pytest.mark.asyncio
async def test_entity_interpretation_serves_fresh_cached_metric_without_ai(
    client: AsyncClient, session: AsyncSession
):
    entity_id = await _seed_entity_with_roe(session)

    # Pre-seed a fresh Interpretation row matching the context's
    # analytics_version exactly (1 metric, latest as_of_date 2026-01-01) --
    # the compute-on-miss path should serve this without needing AI enabled.
    session.add(Interpretation(
        id=uuid.uuid4(), subject_type="ENTITY", subject_id=str(entity_id),
        scope="METRIC", metric_key="ROE", as_of=date(2026, 1, 1),
        analytics_version="1:2026-01-01",
        interpretation="ROE of 18% is strong for this sector.",
        trend="STABLE", direction="FAVORABLE", drivers=["net_margin"],
        confidence=0.8, citations=["analytics_results:x"], ai_enabled=True,
    ))
    await session.commit()

    resp = await client.get(f"/v5/interpret/entities/{entity_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert "ROE" in data["metrics"]
    assert data["metrics"]["ROE"]["interpretation"] == "ROE of 18% is strong for this sector."
    assert data["metrics"]["ROE"]["ai_enabled"] is True
    # No subject-scope row cached yet, and AI is disabled in this test env,
    # so no synthesis should have been produced.
    assert data["subject"] is None


@pytest.mark.asyncio
async def test_metric_interpretation_404_for_unknown_metric(client: AsyncClient, session: AsyncSession):
    entity_id = await _seed_entity_with_roe(session)
    resp = await client.get(f"/v5/interpret/entities/{entity_id}/metrics/NOT_A_REAL_METRIC")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_metric_interpretation_503_when_uncached_and_ai_disabled(
    client: AsyncClient, session: AsyncSession
):
    entity_id = await _seed_entity_with_roe(session)
    resp = await client.get(f"/v5/interpret/entities/{entity_id}/metrics/ROE")
    assert resp.status_code == 503


@pytest.mark.asyncio
async def test_metric_interpretation_serves_fresh_cached_row(client: AsyncClient, session: AsyncSession):
    entity_id = await _seed_entity_with_roe(session)
    session.add(Interpretation(
        id=uuid.uuid4(), subject_type="ENTITY", subject_id=str(entity_id),
        scope="METRIC", metric_key="ROE", as_of=date(2026, 1, 1),
        analytics_version="1:2026-01-01",
        interpretation="ROE of 18% reflects strong profitability.",
        trend="STABLE", direction="FAVORABLE", ai_enabled=True,
    ))
    await session.commit()

    resp = await client.get(f"/v5/interpret/entities/{entity_id}/metrics/roe")  # lowercase on purpose
    assert resp.status_code == 200
    data = resp.json()
    assert data["metric_key"] == "ROE"
    assert data["interpretation"] == "ROE of 18% reflects strong profitability."


@pytest.mark.asyncio
async def test_metric_interpretation_stale_cache_returns_503_not_stale_data(
    client: AsyncClient, session: AsyncSession
):
    entity_id = await _seed_entity_with_roe(session)
    # A cached row exists, but its analytics_version doesn't match the
    # current context (real one would be "1:2026-01-01") -- must be treated
    # as a miss, and since AI is disabled, there's nothing to serve.
    session.add(Interpretation(
        id=uuid.uuid4(), subject_type="ENTITY", subject_id=str(entity_id),
        scope="METRIC", metric_key="ROE", as_of=date(2026, 1, 1),
        analytics_version="STALE_VERSION",
        interpretation="Old interpretation from before a data update.",
        ai_enabled=True,
    ))
    await session.commit()

    resp = await client.get(f"/v5/interpret/entities/{entity_id}/metrics/ROE")
    assert resp.status_code == 503
