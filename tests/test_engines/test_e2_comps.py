"""Tests for E2 Comparable Company Analysis Engine."""

import uuid
from datetime import date

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.analytics import AnalyticsResult
from src.models.entity import Entity
from src.models.security import EODPrice, EquityDetails, Security


# ---------------------------------------------------------------------------
# Fixtures — 3 peer entities/securities in same GICS sector with metrics
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def comps_entities(session: AsyncSession) -> list[Entity]:
    """Create 3 entities in the same GICS sub-industry (IT sector 45)."""
    entities = []
    for i, name in enumerate(["Comps Alpha Corp", "Comps Beta Corp", "Comps Gamma Corp"]):
        entity = Entity(
            entity_id=uuid.uuid4(),
            legal_name=name,
            entity_type="PUBLIC_COMPANY",
            status="ACTIVE",
            incorporation_country="US",
            gics_sector="45",
            gics_sub_industry="45103010",
            source="TEST",
        )
        session.add(entity)
        entities.append(entity)
    await session.flush()
    return entities


@pytest_asyncio.fixture
async def comps_securities(
    session: AsyncSession,
    comps_entities: list[Entity],
) -> list[Security]:
    """Create 3 securities linked to the 3 entities, with EquityDetails and EODPrices."""
    securities = []
    prices = [120.0, 90.0, 150.0]
    shares_list = [50_000_000.0, 40_000_000.0, 60_000_000.0]

    for i, entity in enumerate(comps_entities):
        security = Security(
            security_id=uuid.uuid4(),
            name=f"{entity.legal_name} Common Stock",
            security_type="COMMON_STOCK",
            asset_class="EQUITY",
            status="ACTIVE",
            issuer_entity_id=entity.entity_id,
        )
        session.add(security)
        await session.flush()

        # Equity details
        session.add(EquityDetails(
            security_id=security.security_id,
            shares_outstanding=shares_list[i],
        ))

        # EOD price
        session.add(EODPrice(
            security_id=security.security_id,
            price_date=date(2025, 3, 14),
            open=prices[i] - 1,
            high=prices[i] + 2,
            low=prices[i] - 2,
            close=prices[i],
            close_adjusted=prices[i],
            volume=500_000,
        ))
        await session.flush()
        securities.append(security)

    return securities


@pytest_asyncio.fixture
async def comps_analytics(
    session: AsyncSession,
    comps_entities: list[Entity],
    comps_securities: list[Security],
) -> None:
    """Seed AnalyticsResult rows for pe_trailing and ev_ebitda across all 3 peers."""
    today = date(2025, 3, 14)

    # Valuation metrics per security
    metric_values = [
        # (pe_trailing, ev_ebitda, eps_diluted, ebitda_per_share, revenue_per_share, book_value_per_share)
        (15.0, 10.0, 8.0, 12.0, 24.0, 50.0),
        (12.0, 8.0, 7.5, 11.25, 22.5, 45.0),
        (18.0, 12.0, 8.33, 12.5, 25.0, 55.0),
    ]

    for i, sec in enumerate(comps_securities):
        vals = metric_values[i]
        metrics = [
            ("pe_trailing", "VALUATION", vals[0]),
            ("ev_ebitda", "VALUATION", vals[1]),
            ("eps_diluted", "PER_SHARE", vals[2]),
            ("ebitda_per_share", "PER_SHARE", vals[3]),
            ("revenue_per_share", "PER_SHARE", vals[4]),
            ("book_value_per_share", "PER_SHARE", vals[5]),
        ]
        for metric_name, category, value in metrics:
            session.add(AnalyticsResult(
                security_id=sec.security_id,
                entity_id=comps_entities[i].entity_id,
                engine_id="E1",
                metric_name=metric_name,
                metric_category=category,
                value=value,
                unit="RATIO" if category == "VALUATION" else "CURRENCY",
                period="TTM",
                as_of_date=today,
                data_quality="COMPLETE",
            ))
    await session.flush()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_comps_returns_results(
    session: AsyncSession,
    comps_securities: list[Security],
    comps_analytics: None,
):
    """Comps engine should return non-empty results."""
    from src.engines.e2_comps import CompsEngine

    engine = CompsEngine()
    # Run comps for the first security (its peers are the other two)
    results = await engine.compute(session, security_id=comps_securities[0].security_id)
    assert len(results) > 0


@pytest.mark.asyncio
async def test_comps_peer_count(
    session: AsyncSession,
    comps_securities: list[Security],
    comps_analytics: None,
):
    """Peer count should be >= 2 (the other two securities)."""
    from src.engines.e2_comps import CompsEngine

    engine = CompsEngine()
    results = await engine.compute(session, security_id=comps_securities[0].security_id)

    by_name = {r.metric_name: r.value for r in results}
    assert "comps_peer_count" in by_name
    assert by_name["comps_peer_count"] >= 2


@pytest.mark.asyncio
async def test_comps_implied_prices(
    session: AsyncSession,
    comps_securities: list[Security],
    comps_analytics: None,
):
    """At least one comps_*_implied metric should exist."""
    from src.engines.e2_comps import CompsEngine

    engine = CompsEngine()
    results = await engine.compute(session, security_id=comps_securities[0].security_id)

    implied_metrics = [r for r in results if "_implied" in r.metric_name]
    assert len(implied_metrics) >= 1


@pytest.mark.asyncio
async def test_comps_engine_id(
    session: AsyncSession,
    comps_securities: list[Security],
    comps_analytics: None,
):
    """All comps outputs should have engine_id='E2'."""
    from src.engines.e2_comps import CompsEngine

    engine = CompsEngine()
    results = await engine.compute(session, security_id=comps_securities[0].security_id)

    assert len(results) > 0
    for r in results:
        assert r.engine_id == "E2"


@pytest.mark.asyncio
async def test_comps_no_peers_empty(session: AsyncSession):
    """Security with a unique GICS code should produce empty or INSUFFICIENT_PEERS."""
    from src.engines.e2_comps import CompsEngine

    # Lone entity in a unique GICS sub-industry
    entity = Entity(
        entity_id=uuid.uuid4(),
        legal_name="Lone Wolf Corp",
        entity_type="PUBLIC_COMPANY",
        status="ACTIVE",
        incorporation_country="US",
        gics_sector="10",
        gics_sub_industry="10101010",
        source="TEST",
    )
    session.add(entity)
    await session.flush()

    security = Security(
        security_id=uuid.uuid4(),
        name="Lone Wolf Common Stock",
        security_type="COMMON_STOCK",
        asset_class="EQUITY",
        status="ACTIVE",
        issuer_entity_id=entity.entity_id,
    )
    session.add(security)
    await session.flush()

    engine = CompsEngine()
    results = await engine.compute(session, security_id=security.security_id)

    # Either empty or all flagged as INSUFFICIENT_PEERS
    if results:
        quality_flags = {r.data_quality for r in results}
        assert "INSUFFICIENT_PEERS" in quality_flags


@pytest.mark.asyncio
async def test_comps_composite_implied_price(
    session: AsyncSession,
    comps_securities: list[Security],
    comps_analytics: None,
):
    """comps_composite_implied_price should exist in the output."""
    from src.engines.e2_comps import CompsEngine

    engine = CompsEngine()
    results = await engine.compute(session, security_id=comps_securities[0].security_id)

    by_name = {r.metric_name: r for r in results}
    assert "comps_composite_implied_price" in by_name


@pytest.mark.asyncio
async def test_comps_percentile(
    session: AsyncSession,
    comps_securities: list[Security],
    comps_analytics: None,
):
    """comps_*_percentile values should be between 0 and 100."""
    from src.engines.e2_comps import CompsEngine

    engine = CompsEngine()
    results = await engine.compute(session, security_id=comps_securities[0].security_id)

    percentile_outputs = [r for r in results if "_percentile" in r.metric_name]
    assert len(percentile_outputs) >= 1
    for p in percentile_outputs:
        if p.value is not None:
            assert 0 <= p.value <= 100, f"{p.metric_name} = {p.value} out of range"


@pytest.mark.asyncio
async def test_comps_upside_downside(
    session: AsyncSession,
    comps_securities: list[Security],
    comps_analytics: None,
):
    """comps_upside_downside should exist in the output."""
    from src.engines.e2_comps import CompsEngine

    engine = CompsEngine()
    results = await engine.compute(session, security_id=comps_securities[0].security_id)

    by_name = {r.metric_name: r for r in results}
    assert "comps_upside_downside" in by_name
