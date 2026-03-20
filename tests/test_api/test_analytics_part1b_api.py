"""Tests for the Part 1B Analytics API endpoints (trends, KPIs, peers)."""

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
async def seeded_part1b(session: AsyncSession):
    """Seed data for Part 1B API tests: trends, KPIs, peer data."""
    entity = Entity(
        entity_id=uuid.uuid4(),
        legal_name="Part1B API Corp",
        entity_type="PUBLIC_COMPANY",
        status="ACTIVE",
        incorporation_country="US",
        source="TEST",
        gics_sector="45",
        gics_industry_group="4510",
        gics_industry="451020",
        gics_sub_industry=None,  # skip FK in test
    )
    session.add(entity)
    await session.flush()

    security = Security(
        security_id=uuid.uuid4(),
        name="Part1B API Corp Stock",
        security_type="COMMON_STOCK",
        asset_class="EQUITY",
        status="ACTIVE",
        issuer_entity_id=entity.entity_id,
    )
    session.add(security)
    await session.flush()

    today = date.today()

    # Seed trend results
    trend_data = [
        ("gross_margin_trend_1y", "TREND", 0.05),
        ("gross_margin_trend_3y", "TREND", 0.12),
        ("gross_margin_momentum", "TREND", 0.03),
        ("gross_margin_consistency", "TREND", 1.0),  # code for HIGHLY_CONSISTENT
        ("gross_margin_zscore_5y", "TREND", 0.8),
        ("gross_margin_current_value", "TREND", 0.45),
    ]
    for name, cat, val in trend_data:
        inputs_list = []
        if "trend_1y" in name:
            inputs_list = [{"name": "label", "value": "IMPROVING"}]
        elif "consistency" in name:
            inputs_list = [{"name": "label", "value": "HIGHLY_CONSISTENT"}]
        session.add(AnalyticsResult(
            result_id=uuid.uuid4(),
            security_id=security.security_id,
            entity_id=entity.entity_id,
            engine_id="E1",
            metric_name=name,
            metric_category=cat,
            value=val,
            period="TTM",
            as_of_date=today,
            inputs=inputs_list if inputs_list else None,
        ))

    # Seed industry KPI results
    kpi_data = [
        ("rd_intensity", "INDUSTRY_KPI", 0.16),
        ("rule_of_40", "INDUSTRY_KPI", 0.30),
    ]
    for name, cat, val in kpi_data:
        session.add(AnalyticsResult(
            result_id=uuid.uuid4(),
            security_id=security.security_id,
            entity_id=entity.entity_id,
            engine_id="E1",
            metric_name=name,
            metric_category=cat,
            value=val,
            period="TTM",
            as_of_date=today,
            inputs=[
                {"name": "kpi_set_applied", "value": "SOFTWARE"},
                {"name": "gics_sector", "value": "Information Technology"},
                {"name": "gics_industry", "value": "Software"},
            ],
        ))

    await session.flush()
    return {"entity": entity, "security": security}


# ---------------------------------------------------------------------------
# Tests — Trends
# ---------------------------------------------------------------------------

class TestTrendsAPI:
    """API tests for /v2/analytics/trends/."""

    @pytest.mark.asyncio
    async def test_get_trends_200(self, client: AsyncClient, seeded_part1b):
        """GET /v2/analytics/trends/{id} should return trend data."""
        sid = seeded_part1b["security"]["security_id"] if isinstance(seeded_part1b["security"], dict) else seeded_part1b["security"].security_id
        resp = await client.get(f"/v2/analytics/trends/{sid}")
        assert resp.status_code == 200
        data = resp.json()
        assert "trends" in data
        assert data["security_id"] == str(sid)

    @pytest.mark.asyncio
    async def test_get_trends_with_filter(self, client: AsyncClient, seeded_part1b):
        """GET /v2/analytics/trends/{id}?ratio=gross_margin should filter."""
        sid = seeded_part1b["security"].security_id
        resp = await client.get(f"/v2/analytics/trends/{sid}?ratio=gross_margin")
        assert resp.status_code == 200
        data = resp.json()
        for t in data.get("trends", []):
            assert t["ratio_name"] == "gross_margin"

    @pytest.mark.asyncio
    async def test_get_trends_404(self, client: AsyncClient):
        """Non-existent security should return 404."""
        resp = await client.get(f"/v2/analytics/trends/{uuid.uuid4()}")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Tests — Industry KPIs
# ---------------------------------------------------------------------------

class TestIndustryKPIsAPI:
    """API tests for /v2/analytics/kpis/."""

    @pytest.mark.asyncio
    async def test_get_kpis_200(self, client: AsyncClient, seeded_part1b):
        """GET /v2/analytics/kpis/{id} should return KPIs."""
        sid = seeded_part1b["security"].security_id
        resp = await client.get(f"/v2/analytics/kpis/{sid}")
        assert resp.status_code == 200
        data = resp.json()
        assert "kpis" in data
        assert "rd_intensity" in data["kpis"]

    @pytest.mark.asyncio
    async def test_get_kpis_set_name(self, client: AsyncClient, seeded_part1b):
        """KPI response should include which set was applied."""
        sid = seeded_part1b["security"].security_id
        resp = await client.get(f"/v2/analytics/kpis/{sid}")
        data = resp.json()
        assert data.get("kpi_set_applied") == "SOFTWARE"

    @pytest.mark.asyncio
    async def test_get_kpis_history(self, client: AsyncClient, seeded_part1b):
        """GET /v2/analytics/kpis/{id}/history should work."""
        sid = seeded_part1b["security"].security_id
        resp = await client.get(f"/v2/analytics/kpis/{sid}/history?kpi=rd_intensity")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_get_kpis_404(self, client: AsyncClient):
        """Non-existent security should return 404."""
        resp = await client.get(f"/v2/analytics/kpis/{uuid.uuid4()}")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Tests — Peer Comparison
# ---------------------------------------------------------------------------

class TestPeerComparisonAPI:
    """API tests for peer comparison endpoints."""

    @pytest.mark.asyncio
    async def test_get_peer_group_200(self, client: AsyncClient, seeded_part1b):
        """GET /v2/analytics/peers/{id} should return peer group."""
        sid = seeded_part1b["security"].security_id
        resp = await client.get(f"/v2/analytics/peers/{sid}")
        assert resp.status_code == 200
        data = resp.json()
        assert "peers" in data
        assert data["subject_security_id"] == str(sid)

    @pytest.mark.asyncio
    async def test_get_vs_peers_200(self, client: AsyncClient, seeded_part1b):
        """GET /v2/analytics/ratios/{id}/vs-peers should return 200 with comparison structure."""
        sid = seeded_part1b["security"].security_id
        resp = await client.get(f"/v2/analytics/ratios/{sid}/vs-peers")
        assert resp.status_code == 200
        data = resp.json()
        # Peer comparison returns PeerComparisonResponse which has comparisons key
        assert "comparisons" in data or "subject_security_id" in data

    @pytest.mark.asyncio
    async def test_get_percentile_200(self, client: AsyncClient, seeded_part1b):
        """GET /v2/analytics/ratios/{id}/percentile should return ranks."""
        sid = seeded_part1b["security"].security_id
        resp = await client.get(f"/v2/analytics/ratios/{sid}/percentile")
        assert resp.status_code == 200
        data = resp.json()
        assert "percentiles" in data

    @pytest.mark.asyncio
    async def test_peer_group_404(self, client: AsyncClient):
        """Non-existent security should 404."""
        resp = await client.get(f"/v2/analytics/peers/{uuid.uuid4()}")
        assert resp.status_code == 404
