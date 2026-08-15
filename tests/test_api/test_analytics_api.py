"""Tests for the Pillar 2 Analytics API endpoints."""

import uuid
from datetime import date, datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.analytics import (
    AnalyticsResult,
    CalculationLineage,
    MultipleTimeSeries,
    WACCResult,
)
from src.models.entity import Entity
from src.models.security import EODPrice, Security


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def seeded_analytics(session: AsyncSession):
    """Seed a security with pre-computed analytics results."""
    entity = Entity(
        entity_id=uuid.uuid4(),
        legal_name="Analytics API Test Corp",
        entity_type="PUBLIC_COMPANY",
        status="ACTIVE",
        incorporation_country="US",
        source="TEST",
    )
    session.add(entity)
    await session.flush()

    security = Security(
        security_id=uuid.uuid4(),
        name="Analytics API Test Corp Common Stock",
        security_type="COMMON_STOCK",
        asset_class="EQUITY",
        status="ACTIVE",
        issuer_entity_id=entity.entity_id,
    )
    session.add(security)
    await session.flush()

    today = date.today()

    # Seed some E1 ratio results
    ratios = [
        ("gross_margin", "PROFITABILITY", 0.45),
        ("operating_margin", "PROFITABILITY", 0.22),
        ("net_margin", "PROFITABILITY", 0.15),
        ("roe", "PROFITABILITY", 0.18),
        ("debt_to_equity", "LEVERAGE", 0.75),
        ("current_ratio", "LEVERAGE", 1.5),
        ("asset_turnover", "EFFICIENCY", 0.8),
        ("revenue_yoy", "GROWTH", 0.12),
        ("eps_basic", "PER_SHARE", 3.50),
    ]
    for name, category, value in ratios:
        session.add(AnalyticsResult(
            result_id=uuid.uuid4(),
            security_id=security.security_id,
            entity_id=entity.entity_id,
            engine_id="E1",
            metric_name=name,
            metric_category=category,
            value=value,
            period="TTM",
            as_of_date=today,
        ))

    # TTM metrics
    for name, val in [("total_revenue", 400_000_000), ("net_income", 60_000_000)]:
        session.add(AnalyticsResult(
            result_id=uuid.uuid4(),
            security_id=security.security_id,
            entity_id=entity.entity_id,
            engine_id="E1",
            metric_name=name,
            metric_category="INCOME_STATEMENT",
            value=val,
            period="TTM",
            as_of_date=today,
        ))

    # E2 multiples
    for name, val in [("PE_TRAILING", 18.5), ("EV_EBITDA", 12.3), ("DIVIDEND_YIELD", 0.02)]:
        session.add(AnalyticsResult(
            result_id=uuid.uuid4(),
            security_id=security.security_id,
            entity_id=entity.entity_id,
            engine_id="E2",
            metric_name=name,
            metric_category="VALUATION",
            value=val,
            period="TTM",
            as_of_date=today,
        ))

    # DuPont decomposition — written by the E1 engine as generic AnalyticsResult
    # rows in the DUPONT category (the dedicated dupont_decompositions table is
    # never populated by the batch pipeline).
    for name, val in [
        ("dupont_roe_3f", 0.18),
        ("dupont_net_profit_margin", 0.15),
        ("dupont_asset_turnover", 0.80),
        ("dupont_equity_multiplier", 1.50),
    ]:
        session.add(AnalyticsResult(
            result_id=uuid.uuid4(),
            security_id=security.security_id,
            entity_id=entity.entity_id,
            engine_id="E1",
            metric_name=name,
            metric_category="DUPONT",
            value=val,
            period="TTM",
            period_end_date=today,
            as_of_date=today,
        ))

    # WACC result
    session.add(WACCResult(
        wacc_id=uuid.uuid4(),
        entity_id=entity.entity_id,
        security_id=security.security_id,
        calculation_date=today,
        risk_free_rate=0.0425,
        equity_risk_premium=0.055,
        beta=1.15,
        cost_of_equity=0.106,
        cost_of_debt_pretax=0.05,
        effective_tax_rate=0.21,
        cost_of_debt_aftertax=0.0395,
        debt_weight=0.30,
        equity_weight=0.70,
        wacc=0.086,
        market_cap=3_500_000_000.0,
        total_debt=1_500_000_000.0,
    ))

    # Lineage entry
    session.add(CalculationLineage(
        lineage_id=uuid.uuid4(),
        security_id=security.security_id,
        entity_id=entity.entity_id,
        engine_id="E1",
        engine_version="1.0.0",
        output_metric="gross_margin",
        output_value=0.45,
        period="TTM",
        calculation_formula="gross_profit / total_revenue",
        inputs=[
            {"name": "gross_profit", "source": "pillar_1.fundamentals", "value": 180000000},
            {"name": "total_revenue", "source": "pillar_1.fundamentals", "value": 400000000},
        ],
    ))

    await session.flush()
    return security


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_all_ratios(client, seeded_analytics):
    """GET /v2/analytics/ratios/{id} returns grouped ratios."""
    resp = await client.get(f"/v2/analytics/ratios/{seeded_analytics.security_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["security_id"] == str(seeded_analytics.security_id)
    assert "profitability" in data
    assert "gross_margin" in data["profitability"]
    assert data["profitability"]["gross_margin"] == pytest.approx(0.45)


@pytest.mark.asyncio
async def test_get_ratios_by_category(client, seeded_analytics):
    """GET /v2/analytics/ratios/{id}/profitability returns category ratios."""
    resp = await client.get(f"/v2/analytics/ratios/{seeded_analytics.security_id}/profitability")
    assert resp.status_code == 200
    data = resp.json()
    assert "gross_margin" in data
    assert data["gross_margin"] == pytest.approx(0.45)


@pytest.mark.asyncio
async def test_get_ratios_404(client):
    """GET /v2/analytics/ratios/{bad_id} returns 404."""
    resp = await client.get(f"/v2/analytics/ratios/{uuid.uuid4()}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_ttm(client, seeded_analytics):
    """GET /v2/analytics/ttm/{id} returns TTM metrics."""
    resp = await client.get(f"/v2/analytics/ttm/{seeded_analytics.security_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert "metrics" in data
    assert "total_revenue" in data["metrics"]


@pytest.mark.asyncio
async def test_get_ttm_matches_real_dated_period_label(session: AsyncSession, client):
    """Regression test: TTMEngine's real period label is
    f"TTM_{period_end_date.isoformat()}" (e.g. "TTM_2025-03-31"), not the
    bare "TTM" this endpoint previously matched exactly -- so it 404'd
    even when TTM data had actually been computed and persisted.
    """
    entity = Entity(
        entity_id=uuid.uuid4(), legal_name="TTM Label Test Corp",
        entity_type="PUBLIC_COMPANY", status="ACTIVE", source="TEST",
    )
    session.add(entity)
    await session.flush()
    security = Security(
        security_id=uuid.uuid4(), name="TTM Label Test Corp Stock",
        security_type="COMMON_STOCK", asset_class="EQUITY", status="ACTIVE",
        issuer_entity_id=entity.entity_id,
    )
    session.add(security)
    await session.flush()

    session.add(AnalyticsResult(
        result_id=uuid.uuid4(), security_id=security.security_id,
        entity_id=entity.entity_id, engine_id="E1", metric_name="ttm_total_revenue",
        metric_category="INCOME_STATEMENT", value=500_000_000.0, unit="CURRENCY",
        period="TTM_2025-03-31", period_end_date=date(2025, 3, 31),
        as_of_date=date.today(), data_quality="COMPLETE",
    ))
    await session.flush()

    resp = await client.get(f"/v2/analytics/ttm/{security.security_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["metrics"]["ttm_total_revenue"] == pytest.approx(500_000_000.0)


@pytest.mark.asyncio
async def test_get_dupont(client, seeded_analytics):
    """GET /v2/analytics/dupont/{id} returns DuPont decomposition."""
    resp = await client.get(f"/v2/analytics/dupont/{seeded_analytics.security_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert data[0]["model_type"] == "THREE_FACTOR"
    assert data[0]["roe"] == pytest.approx(0.18)


@pytest.mark.asyncio
async def test_get_multiples(client, seeded_analytics):
    """GET /v2/analytics/multiples/{id} returns valuation multiples."""
    resp = await client.get(f"/v2/analytics/multiples/{seeded_analytics.security_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert "multiples" in data
    assert "PE_TRAILING" in data["multiples"]
    assert data["multiples"]["PE_TRAILING"] == pytest.approx(18.5)


@pytest.mark.asyncio
async def test_multiple_history_matches_real_lowercase_type(session: AsyncSession, client):
    """Regression test: e2_multiples.py persists
    MultipleTimeSeries.multiple_type in lowercase (e.g. "pe_trailing",
    matching AnalyticsResult.metric_name), but this endpoint compared
    against `multiple.upper()` -- never matching, so
    /multiples/{id}/history was always empty.
    """
    entity = Entity(
        entity_id=uuid.uuid4(), legal_name="Multiples History Test Corp",
        entity_type="PUBLIC_COMPANY", status="ACTIVE", source="TEST",
    )
    session.add(entity)
    await session.flush()
    security = Security(
        security_id=uuid.uuid4(), name="Multiples History Test Corp Stock",
        security_type="COMMON_STOCK", asset_class="EQUITY", status="ACTIVE",
        issuer_entity_id=entity.entity_id,
    )
    session.add(security)
    await session.flush()

    session.add(MultipleTimeSeries(
        security_id=security.security_id,
        multiple_type="pe_trailing",
        calculation_date=date.today(),
        value=17.2,
    ))
    await session.flush()

    resp = await client.get(
        f"/v2/analytics/multiples/{security.security_id}/history",
        params={"multiple": "PE_TRAILING"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["data_points"]) == 1
    assert data["data_points"][0]["value"] == pytest.approx(17.2)


@pytest.mark.asyncio
async def test_get_wacc(client, seeded_analytics):
    """GET /v2/analytics/wacc/{id} returns WACC with components."""
    resp = await client.get(f"/v2/analytics/wacc/{seeded_analytics.security_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["wacc"] == pytest.approx(0.086)
    assert data["beta"] == pytest.approx(1.15)
    assert data["cost_of_equity"] == pytest.approx(0.106)


@pytest.mark.asyncio
async def test_get_wacc_components(client, seeded_analytics):
    """GET /v2/analytics/wacc/{id}/components returns detailed breakdown."""
    resp = await client.get(f"/v2/analytics/wacc/{seeded_analytics.security_id}/components")
    assert resp.status_code == 200
    data = resp.json()
    assert "risk_free_rate" in data
    assert "equity_risk_premium" in data
    assert "debt_weight" in data


@pytest.mark.asyncio
async def test_get_wacc_404(client):
    """GET /v2/analytics/wacc/{bad_id} returns 404."""
    resp = await client.get(f"/v2/analytics/wacc/{uuid.uuid4()}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_lineage(client, seeded_analytics):
    """GET /v2/analytics/audit/{id}/{metric} returns lineage."""
    resp = await client.get(
        f"/v2/analytics/audit/{seeded_analytics.security_id}/gross_margin"
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["output_metric"] == "gross_margin"
    assert data["output_value"] == pytest.approx(0.45)
    assert len(data["inputs"]) == 2
    assert data["calculation_formula"] == "gross_profit / total_revenue"


@pytest.mark.asyncio
async def test_get_lineage_404(client, seeded_analytics):
    """GET /v2/analytics/audit/{id}/nonexistent returns 404."""
    resp = await client.get(
        f"/v2/analytics/audit/{seeded_analytics.security_id}/nonexistent_metric"
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_bulk_ratios(client, seeded_analytics):
    """POST /v2/analytics/ratios/bulk returns ratios for multiple securities."""
    resp = await client.post(
        "/v2/analytics/ratios/bulk",
        json={
            "security_ids": [str(seeded_analytics.security_id)],
            "categories": ["PROFITABILITY"],
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert str(seeded_analytics.security_id) in data


@pytest.mark.asyncio
async def test_dupont_history(client, seeded_analytics):
    """GET /v2/analytics/dupont/{id}/history returns decomposition history."""
    resp = await client.get(
        f"/v2/analytics/dupont/{seeded_analytics.security_id}/history"
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "decompositions" in data


# ---------------------------------------------------------------------------
# /v2/analytics/correlation -- factor performance (regression for the
# previously-hardcoded-zeros bug)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_correlation_insufficient_securities_returns_zeros(client, session: AsyncSession):
    """Below _MIN_SECURITIES_FOR_FACTOR_PERFORMANCE, factors report zeros
    (honest default when there isn't enough data to rank a spread)."""
    entity = Entity(
        entity_id=uuid.uuid4(), legal_name="Sparse Factor Corp",
        entity_type="PUBLIC_COMPANY", status="ACTIVE", source="TEST",
    )
    session.add(entity)
    await session.flush()
    security = Security(
        security_id=uuid.uuid4(), name="Sparse Factor Corp Common Stock",
        security_type="COMMON_STOCK", asset_class="EQUITY", status="ACTIVE",
        issuer_entity_id=entity.entity_id,
    )
    session.add(security)
    await session.flush()
    session.add(AnalyticsResult(
        security_id=security.security_id, entity_id=entity.entity_id,
        engine_id="E1", metric_name="roe", metric_category="PROFITABILITY",
        value=0.20, unit="PERCENT", period="TTM", as_of_date=date.today(),
        data_quality="COMPLETE",
    ))
    await session.flush()

    resp = await client.get("/v2/analytics/correlation")
    assert resp.status_code == 200
    data = resp.json()
    quality = next(f for f in data["factorPerformance"] if f["factor"] == "Quality")
    assert quality == {
        "factor": "Quality", "mtd": 0.0, "qtd": 0.0, "ytd": 0.0,
        "oneYear": 0.0, "sharpe": 0.0, "ic": 0.0,
    }


@pytest.mark.asyncio
async def test_correlation_factor_performance_reflects_real_spread(client, session: AsyncSession):
    """Regression test: factor_performance must be computed from real price
    data, not hardcoded to zero.

    Seeds 9 securities with a "quality" score (roe) split into a clear
    bottom tercile (3 low-roe), middle tercile (3, padding only), and top
    tercile (3 high-roe). The bottom-tercile securities decline at a
    constant -0.10%/day; the top-tercile securities gain at a constant
    +0.10%/day, every business day for ~14 months. The long-top/short-
    bottom spread must therefore show a large POSITIVE oneYear return --
    not 0.0. (IC needs >= 5 securities in the top+bottom groups, hence
    tercile size 3 rather than 2.)
    """
    entities = []
    securities = []
    for i in range(9):
        eid = uuid.uuid4()
        sid = uuid.uuid4()
        entities.append(eid)
        securities.append(sid)
        session.add(Entity(
            entity_id=eid, legal_name=f"Factor Perf Corp {i}",
            entity_type="PUBLIC_COMPANY", status="ACTIVE", source="TEST",
        ))
        session.add(Security(
            security_id=sid, name=f"Factor Perf Corp {i} Common Stock",
            security_type="COMMON_STOCK", asset_class="EQUITY", status="ACTIVE",
            issuer_entity_id=eid,
        ))
    await session.flush()

    # roe: 3 bottom, 3 middle, 3 top
    roe_values = [0.01, 0.02, 0.03, 0.14, 0.16, 0.18, 0.30, 0.33, 0.35]
    today = date.today()
    for sid, eid, roe in zip(securities, entities, roe_values):
        session.add(AnalyticsResult(
            security_id=sid, entity_id=eid, engine_id="E1", metric_name="roe",
            metric_category="PROFITABILITY", value=roe, unit="PERCENT",
            period="TTM", as_of_date=today, data_quality="COMPLETE",
        ))
    await session.flush()

    # Daily returns: bottom three securities decline, top three rally.
    # Middle three get no price history (excluded from the spread query).
    bottom_ids = set(securities[0:3])
    top_ids = set(securities[6:9])
    daily_return = {sid: -0.001 for sid in bottom_ids}
    daily_return.update({sid: 0.001 for sid in top_ids})

    start = today - timedelta(days=400)
    rows = []
    for sid, ret in daily_return.items():
        d = start
        price = 100.0
        while d <= today:
            if d.weekday() < 5:
                price *= (1.0 + ret)
                rows.append(EODPrice(
                    security_id=sid, price_date=d,
                    open=price, high=price, low=price, close=price,
                    close_adjusted=price, volume=1_000_000, source="TEST",
                ))
            d += timedelta(days=1)
    session.add_all(rows)
    await session.flush()

    resp = await client.get("/v2/analytics/correlation")
    assert resp.status_code == 200
    data = resp.json()
    quality = next(f for f in data["factorPerformance"] if f["factor"] == "Quality")

    # A ~14-month +0.1%/day vs -0.1%/day spread compounds to a large gain --
    # nowhere near the previously-hardcoded 0.0.
    assert quality["oneYear"] > 0.3
    assert quality["ytd"] != 0.0
    assert quality["sharpe"] > 0.0
    # IC: quality score (roe) should positively rank-correlate with realized
    # return, since the highest-roe securities are exactly the ones that rallied.
    assert quality["ic"] > 0.5
