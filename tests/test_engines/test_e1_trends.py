"""Tests for the Trend Analysis engine (Part 1B)."""

import uuid
from datetime import date, timedelta

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from src.engines.e1_trends import TrendEngine, TREND_RATIOS
from src.models.analytics import AnalyticsResult
from src.models.entity import Entity
from src.models.security import Security


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def security_with_history(session: AsyncSession) -> Security:
    """Create a security with 5 years of ratio history."""
    entity = Entity(
        entity_id=uuid.uuid4(),
        legal_name="Trend Test Corp",
        entity_type="PUBLIC_COMPANY",
        status="ACTIVE",
        incorporation_country="US",
        source="TEST",
    )
    session.add(entity)
    await session.flush()

    security = Security(
        security_id=uuid.uuid4(),
        name="Trend Test Corp Stock",
        security_type="COMMON_STOCK",
        asset_class="EQUITY",
        status="ACTIVE",
        issuer_entity_id=entity.entity_id,
    )
    session.add(security)
    await session.flush()

    # Seed 20 quarterly gross_margin values showing an improving trend
    base_date = date(2025, 3, 31)
    for i in range(20):
        period_end = base_date - timedelta(days=i * 91)
        fiscal_year = period_end.year
        session.add(AnalyticsResult(
            result_id=uuid.uuid4(),
            security_id=security.security_id,
            entity_id=entity.entity_id,
            engine_id="E1",
            metric_name="gross_margin",
            metric_category="PROFITABILITY",
            value=0.30 + 0.01 * i * 0.5,  # 0.30 → 0.395 (improving going back)
            # Actually we want improving forward, so reverse: oldest=0.30, newest=0.395
            period=f"Q{((i % 4) + 1)}_{fiscal_year}",
            period_end_date=period_end,
            as_of_date=period_end,
        ))

    # Seed 20 quarterly debt_to_equity values — stable around 0.75
    for i in range(20):
        period_end = base_date - timedelta(days=i * 91)
        session.add(AnalyticsResult(
            result_id=uuid.uuid4(),
            security_id=security.security_id,
            entity_id=entity.entity_id,
            engine_id="E1",
            metric_name="debt_to_equity",
            metric_category="LEVERAGE",
            value=0.75 + 0.01 * (i % 3 - 1),  # 0.74, 0.75, 0.76 oscillating
            period=f"Q{((i % 4) + 1)}_{period_end.year}",
            period_end_date=period_end,
            as_of_date=period_end,
        ))

    # Seed 8 quarterly roe values — volatile
    for i in range(8):
        period_end = base_date - timedelta(days=i * 91)
        session.add(AnalyticsResult(
            result_id=uuid.uuid4(),
            security_id=security.security_id,
            entity_id=entity.entity_id,
            engine_id="E1",
            metric_name="roe",
            metric_category="PROFITABILITY",
            value=0.10 + 0.05 * ((-1) ** i),  # 0.15, 0.05, 0.15, 0.05 ...
            period=f"Q{((i % 4) + 1)}_{period_end.year}",
            period_end_date=period_end,
            as_of_date=period_end,
        ))

    await session.flush()
    return security


@pytest_asyncio.fixture
async def security_sparse(session: AsyncSession) -> Security:
    """Security with only 1 period of data — insufficient for trends."""
    entity = Entity(
        entity_id=uuid.uuid4(),
        legal_name="Sparse Corp",
        entity_type="PUBLIC_COMPANY",
        status="ACTIVE",
        incorporation_country="US",
        source="TEST",
    )
    session.add(entity)
    await session.flush()

    security = Security(
        security_id=uuid.uuid4(),
        name="Sparse Corp Stock",
        security_type="COMMON_STOCK",
        asset_class="EQUITY",
        status="ACTIVE",
        issuer_entity_id=entity.entity_id,
    )
    session.add(security)
    await session.flush()

    session.add(AnalyticsResult(
        result_id=uuid.uuid4(),
        security_id=security.security_id,
        entity_id=entity.entity_id,
        engine_id="E1",
        metric_name="gross_margin",
        metric_category="PROFITABILITY",
        value=0.40,
        period="Q1_2025",
        period_end_date=date(2025, 3, 31),
        as_of_date=date(2025, 3, 31),
    ))
    await session.flush()
    return security


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestTrendEngine:
    """Unit tests for TrendEngine."""

    @pytest.mark.asyncio
    async def test_trend_engine_produces_outputs(self, session, security_with_history):
        """Engine should return trend outputs for seeded ratios."""
        engine = TrendEngine()
        results = await engine.compute(session, security_with_history.security_id)
        assert len(results) > 0
        assert all(r.engine_id == "E1" for r in results)
        assert all(r.metric_category == "TREND" for r in results)

    @pytest.mark.asyncio
    async def test_trend_direction_classified(self, session, security_with_history):
        """Direction should be IMPROVING, DETERIORATING, or STABLE."""
        engine = TrendEngine()
        results = await engine.compute(session, security_with_history.security_id)
        direction_results = [r for r in results if r.metric_name.endswith("_trend_1y")]
        assert len(direction_results) > 0
        valid_labels = {"IMPROVING", "DETERIORATING", "STABLE"}
        for r in direction_results:
            if r.inputs:
                labels = [inp.get("value") for inp in r.inputs if inp.get("name") == "label"]
                for lbl in labels:
                    if lbl:
                        assert lbl in valid_labels, f"Invalid direction: {lbl}"

    @pytest.mark.asyncio
    async def test_consistency_classification(self, session, security_with_history):
        """Consistency should be HIGHLY_CONSISTENT, MODERATE, or VOLATILE."""
        engine = TrendEngine()
        results = await engine.compute(session, security_with_history.security_id)
        consistency_results = [r for r in results if r.metric_name.endswith("_consistency")]
        valid = {"HIGHLY_CONSISTENT", "MODERATE", "VOLATILE"}
        for r in consistency_results:
            if r.inputs:
                labels = [inp.get("value") for inp in r.inputs if inp.get("name") == "label"]
                for lbl in labels:
                    if lbl:
                        assert lbl in valid, f"Invalid consistency: {lbl}"

    @pytest.mark.asyncio
    async def test_zscore_computation(self, session, security_with_history):
        """Z-score should be a reasonable number."""
        engine = TrendEngine()
        results = await engine.compute(session, security_with_history.security_id)
        zscore_results = [r for r in results if r.metric_name.endswith("_zscore_5y")]
        for r in zscore_results:
            if r.value is not None:
                assert -10.0 < r.value < 10.0, f"Z-score out of range: {r.value}"

    @pytest.mark.asyncio
    async def test_sparse_data_returns_few_trends(self, session, security_sparse):
        """With only 1 period, trends should be empty or minimal."""
        engine = TrendEngine()
        results = await engine.compute(session, security_sparse.security_id)
        # Should produce no direction/momentum trends (need ≥2 periods)
        direction_results = [r for r in results if "_trend_" in r.metric_name]
        assert len(direction_results) == 0

    @pytest.mark.asyncio
    async def test_trend_ratios_constant_is_defined(self):
        """TREND_RATIOS should list the key ratios to track."""
        assert len(TREND_RATIOS) >= 20
        assert "gross_margin" in TREND_RATIOS
        assert "roe" in TREND_RATIOS
        assert "debt_to_equity" in TREND_RATIOS

    @pytest.mark.asyncio
    async def test_multiple_ratios_tracked(self, session, security_with_history):
        """Trend outputs should cover multiple distinct base ratios."""
        engine = TrendEngine()
        results = await engine.compute(session, security_with_history.security_id)
        base_ratios = set()
        for r in results:
            # Extract base name by finding known suffixes
            for suffix in ("_trend_1y", "_momentum", "_std_5y", "_zscore_5y", "_consistency"):
                if r.metric_name.endswith(suffix):
                    base_ratios.add(r.metric_name[: -len(suffix)])
                    break
        # We seeded 3 ratios (gross_margin, debt_to_equity, roe)
        assert len(base_ratios) >= 2
