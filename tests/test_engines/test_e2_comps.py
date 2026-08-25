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
    # TTM totals (in dollars, NOT per-share) that _MULTIPLE_DENOM_MAP actually
    # reads for the EV-based multiples -- ttm_ebitda / ttm_total_revenue.
    # These were previously absent from this fixture (it only seeded the
    # stale "ebitda_per_share"/"eps_diluted" names from before [Bug 30 fix]
    # renamed the map to E1's real TTM output), so the EV implied-price
    # branch's arithmetic was never actually exercised by these tests --
    # exactly how the ×shares inflation bug went uncaught.
    ttm_totals = [
        # (ttm_diluted_eps, ttm_ebitda, ttm_total_revenue, bvps, dps)
        (8.0, 500_000_000.0, 1_200_000_000.0, 50.0, 2.0),
        (7.5, 350_000_000.0, 900_000_000.0, 45.0, 1.8),
        (8.33, 750_000_000.0, 1_500_000_000.0, 55.0, 2.2),
    ]
    net_debts = [200_000_000.0, 150_000_000.0, 300_000_000.0]

    for i, sec in enumerate(comps_securities):
        vals = metric_values[i]
        ttm = ttm_totals[i]
        metrics = [
            ("pe_trailing", "VALUATION", vals[0]),
            ("ev_ebitda", "VALUATION", vals[1]),
            ("eps_diluted", "PER_SHARE", vals[2]),
            ("ebitda_per_share", "PER_SHARE", vals[3]),
            ("revenue_per_share", "PER_SHARE", vals[4]),
            ("book_value_per_share", "PER_SHARE", vals[5]),
            ("ttm_diluted_eps", "PER_SHARE", ttm[0]),
            ("ttm_ebitda", "FUNDAMENTAL", ttm[1]),
            ("ttm_total_revenue", "FUNDAMENTAL", ttm[2]),
            ("bvps", "PER_SHARE", ttm[3]),
            ("dps", "PER_SHARE", ttm[4]),
            ("net_debt", "FUNDAMENTAL", net_debts[i]),
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
async def test_comps_ev_ebitda_implied_price_not_inflated_by_shares(
    session: AsyncSession,
    comps_securities: list[Security],
    comps_analytics: None,
):
    """EV-based implied price must not double-count shares outstanding.

    Regression test for the ×shares bug: ``_compute_implied_price`` was
    multiplying an already-total TTM EBITDA by ``shares`` a second time,
    inflating the EV-multiple implied price to billions of dollars per
    share instead of a sane per-share figure. Subject (comps_securities[0])
    has peer ev_ebitda values [8.0, 12.0] -> peer_median=10.0, ttm_ebitda=
    500_000_000, net_debt=200_000_000, shares=50_000_000:
        implied_ev = 10.0 * 500_000_000 = 5_000_000_000
        implied_equity = 5_000_000_000 - 200_000_000 = 4_800_000_000
        implied_price = 4_800_000_000 / 50_000_000 = 96.0
    The buggy version multiplied implied_ev by shares again, producing an
    implied_price in the billions.
    """
    from src.engines.e2_comps import CompsEngine

    engine = CompsEngine()
    results = await engine.compute(session, security_id=comps_securities[0].security_id)

    by_name = {r.metric_name: r.value for r in results}
    assert "comps_ev_ebitda_implied" in by_name
    implied = by_name["comps_ev_ebitda_implied"]
    assert implied is not None
    assert implied == pytest.approx(96.0, rel=1e-6)
    # Sanity bound: implied price should be in the same order of magnitude
    # as peer trading prices ($90-$150 in this fixture), not billions.
    assert 0 < implied < 1_000


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
