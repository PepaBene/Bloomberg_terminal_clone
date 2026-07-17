"""API tests for Portfolio Performance & Attribution endpoints (Pillar 4 Phase 2)."""

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.portfolio import Portfolio
from src.models.position import Position
from src.models.transaction import Transaction
from src.models.nav_snapshot import NAVSnapshot
from src.models.performance import PerformanceSnapshot
from src.models.attribution import AttributionResult, ReportRequest


# ── Helpers ──────────────────────────────────────────────────────────


async def _seed_portfolio(
    session: AsyncSession,
    portfolio_name: str = "Perf API Portfolio",
    **kwargs,
) -> Portfolio:
    defaults = {
        "id": uuid.uuid4(),
        "user_id": "default_user",
        "portfolio_name": portfolio_name,
        "portfolio_type": "REAL",
        "inception_date": date(2025, 1, 1),
        "initial_cash": Decimal("100000.00"),
        "current_cash": Decimal("100000.00"),
    }
    defaults.update(kwargs)
    p = Portfolio(**defaults)
    session.add(p)
    await session.flush()
    return p


async def _seed_position(
    session: AsyncSession,
    portfolio_id: uuid.UUID,
    ticker: str = "AAPL",
    **kwargs,
) -> Position:
    defaults = {
        "id": uuid.uuid4(),
        "portfolio_id": portfolio_id,
        "ticker": ticker,
        "status": "OPEN",
        "shares": Decimal("100.000000"),
        "cost_basis_per_share": Decimal("150.000000"),
        "cost_basis_total": Decimal("15000.00"),
        "first_acquisition_date": date(2025, 3, 1),
    }
    defaults.update(kwargs)
    pos = Position(**defaults)
    session.add(pos)
    await session.flush()
    return pos


async def _seed_transaction(
    session: AsyncSession,
    portfolio_id: uuid.UUID,
    **kwargs,
) -> Transaction:
    defaults = {
        "id": uuid.uuid4(),
        "portfolio_id": portfolio_id,
        "ticker": "AAPL",
        "transaction_type": "BUY",
        "transaction_date": date(2025, 3, 15),
        "shares": Decimal("100.000000"),
        "price_per_share": Decimal("150.000000"),
        "gross_amount": Decimal("15000.00"),
        "commission": Decimal("9.99"),
        "net_amount": Decimal("15009.99"),
        "cash_impact": Decimal("-15009.99"),
    }
    defaults.update(kwargs)
    txn = Transaction(**defaults)
    session.add(txn)
    await session.flush()
    return txn


async def _seed_nav_snapshot(
    session: AsyncSession,
    portfolio_id: uuid.UUID,
    snapshot_date: date = date(2025, 6, 1),
    **kwargs,
) -> NAVSnapshot:
    defaults = {
        "id": uuid.uuid4(),
        "portfolio_id": portfolio_id,
        "snapshot_date": snapshot_date,
        "nav": Decimal("105000.00"),
        "market_value": Decimal("80000.00"),
        "cash_balance": Decimal("25000.00"),
        "daily_return": Decimal("0.00150000"),
        "cumulative_return": Decimal("0.05000000"),
    }
    defaults.update(kwargs)
    snap = NAVSnapshot(**defaults)
    session.add(snap)
    await session.flush()
    return snap


async def _seed_performance_snapshot(
    session: AsyncSession,
    portfolio_id: uuid.UUID,
    period_type: str = "MONTHLY",
    period_end: date = date(2025, 6, 30),
    **kwargs,
) -> PerformanceSnapshot:
    defaults = {
        "id": uuid.uuid4(),
        "portfolio_id": portfolio_id,
        "period_type": period_type,
        # Default period_start to period_end (not a fixed date) so callers
        # that only override period_end can't accidentally end up with
        # period_start > period_end and trip ck_perf_period_order.
        "period_start": period_end,
        "period_end": period_end,
        "twr_return": Decimal("0.02150000"),
        "mwr_return": Decimal("0.02100000"),
        "benchmark_return": Decimal("0.01800000"),
        "active_return": Decimal("0.00350000"),
        "sharpe_ratio": Decimal("1.250000"),
        "sortino_ratio": Decimal("1.480000"),
        "information_ratio": Decimal("0.850000"),
        "tracking_error": Decimal("0.041200"),
        "max_drawdown": Decimal("-0.085000"),
        "calmar_ratio": Decimal("0.950000"),
        "beta": Decimal("0.920000"),
        "alpha": Decimal("0.003500"),
        "volatility": Decimal("0.152000"),
        "up_capture": Decimal("1.050000"),
        "down_capture": Decimal("0.880000"),
    }
    defaults.update(kwargs)
    snap = PerformanceSnapshot(**defaults)
    session.add(snap)
    await session.flush()
    return snap


async def _seed_attribution(
    session: AsyncSession,
    portfolio_id: uuid.UUID,
    attribution_type: str = "BRINSON",
    period_end: date = date(2025, 6, 30),
    **kwargs,
) -> AttributionResult:
    defaults = {
        "id": uuid.uuid4(),
        "portfolio_id": portfolio_id,
        "period_start": date(2025, 6, 1),
        "period_end": period_end,
        "attribution_type": attribution_type,
        "total_portfolio_return": Decimal("0.02500000"),
        "total_benchmark_return": Decimal("0.01800000"),
        "total_active_return": Decimal("0.00700000"),
        "total_allocation": Decimal("0.00300000"),
        "total_selection": Decimal("0.00350000"),
        "total_interaction": Decimal("0.00050000"),
        "residual": Decimal("0.00000000"),
        "sector_detail": [
            {
                "sector": "Technology",
                "portfolio_weight": 0.35,
                "benchmark_weight": 0.30,
                "portfolio_return": 0.04,
                "benchmark_return": 0.03,
                "allocation_effect": 0.002,
                "selection_effect": 0.003,
                "interaction_effect": 0.0005,
                "total_effect": 0.0055,
            },
            {
                "sector": "Healthcare",
                "portfolio_weight": 0.15,
                "benchmark_weight": 0.18,
                "portfolio_return": 0.02,
                "benchmark_return": 0.025,
                "allocation_effect": -0.0005,
                "selection_effect": -0.001,
                "interaction_effect": 0.0001,
                "total_effect": -0.0014,
            },
        ],
        "security_detail": [
            {"ticker": "AAPL", "weight": 0.10, "return": 0.05, "contribution": 0.005},
            {"ticker": "MSFT", "weight": 0.08, "return": 0.04, "contribution": 0.0032},
            {"ticker": "GOOG", "weight": 0.07, "return": 0.03, "contribution": 0.0021},
            {"ticker": "AMZN", "weight": 0.06, "return": -0.01, "contribution": -0.0006},
            {"ticker": "META", "weight": 0.05, "return": -0.02, "contribution": -0.001},
            {"ticker": "NFLX", "weight": 0.04, "return": -0.03, "contribution": -0.0012},
        ],
        "factor_detail": [
            {"factor": "Momentum", "portfolio_exposure": 0.15, "benchmark_exposure": 0.10, "factor_return": 0.03, "contribution": 0.0015},
            {"factor": "Value", "portfolio_exposure": -0.05, "benchmark_exposure": 0.05, "factor_return": 0.02, "contribution": -0.002},
        ],
    }
    defaults.update(kwargs)
    attr = AttributionResult(**defaults)
    session.add(attr)
    await session.flush()
    return attr


# ══════════════════════════════════════════════════════════════════════
# Performance — GET summary
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_get_performance_empty(client: AsyncClient, session: AsyncSession):
    """GET /v4/portfolios/{id}/performance returns null when no data."""
    p = await _seed_portfolio(session, portfolio_name="Perf Empty")
    resp = await client.get(f"/v4/portfolios/{p.id}/performance")
    assert resp.status_code == 200
    assert resp.json() is None


@pytest.mark.asyncio
async def test_get_performance_with_data(client: AsyncClient, session: AsyncSession):
    """GET /v4/portfolios/{id}/performance returns snapshot."""
    p = await _seed_portfolio(session, portfolio_name="Perf Data")
    await _seed_performance_snapshot(session, p.id)
    resp = await client.get(f"/v4/portfolios/{p.id}/performance")
    assert resp.status_code == 200
    data = resp.json()
    assert data["period_type"] == "MONTHLY"
    assert data["twr_return"] is not None
    assert data["sharpe_ratio"] is not None


@pytest.mark.asyncio
async def test_get_performance_404(client: AsyncClient, session: AsyncSession):
    """GET /v4/portfolios/{id}/performance returns 404 for missing portfolio."""
    resp = await client.get(f"/v4/portfolios/{uuid.uuid4()}/performance")
    assert resp.status_code == 404


# ══════════════════════════════════════════════════════════════════════
# Returns — time series, calendar, rolling
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_get_returns_time_series(client: AsyncClient, session: AsyncSession):
    """GET /v4/portfolios/{id}/performance/returns returns entries."""
    p = await _seed_portfolio(session, portfolio_name="Returns TS")
    await _seed_nav_snapshot(session, p.id, snapshot_date=date(2025, 6, 1))
    await _seed_nav_snapshot(session, p.id, snapshot_date=date(2025, 6, 2))
    resp = await client.get(f"/v4/portfolios/{p.id}/performance/returns")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["entries"]) >= 2


@pytest.mark.asyncio
async def test_get_calendar_returns(client: AsyncClient, session: AsyncSession):
    """GET /v4/portfolios/{id}/performance/returns/calendar returns grid."""
    p = await _seed_portfolio(session, portfolio_name="Calendar Returns")
    await _seed_performance_snapshot(
        session, p.id, period_type="MONTHLY", period_end=date(2025, 1, 31)
    )
    await _seed_performance_snapshot(
        session, p.id, period_type="MONTHLY", period_end=date(2025, 2, 28)
    )
    resp = await client.get(f"/v4/portfolios/{p.id}/performance/returns/calendar")
    assert resp.status_code == 200
    data = resp.json()
    assert "years" in data


@pytest.mark.asyncio
async def test_get_rolling_returns(client: AsyncClient, session: AsyncSession):
    """GET /v4/portfolios/{id}/performance/returns/rolling returns entries."""
    p = await _seed_portfolio(session, portfolio_name="Rolling Returns")
    await _seed_performance_snapshot(
        session, p.id, period_type="DAILY", period_end=date(2025, 3, 1)
    )
    resp = await client.get(f"/v4/portfolios/{p.id}/performance/returns/rolling")
    assert resp.status_code == 200
    data = resp.json()
    assert "entries" in data


# ══════════════════════════════════════════════════════════════════════
# Benchmark comparison
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_get_benchmark_comparison(client: AsyncClient, session: AsyncSession):
    """GET /v4/portfolios/{id}/performance/benchmark returns comparison."""
    p = await _seed_portfolio(session, portfolio_name="Benchmark Compare")
    await _seed_performance_snapshot(session, p.id, period_end=date(2025, 4, 30))
    resp = await client.get(f"/v4/portfolios/{p.id}/performance/benchmark")
    assert resp.status_code == 200
    data = resp.json()
    assert "portfolio_return" in data
    assert "benchmark_return" in data
    assert "active_return" in data


@pytest.mark.asyncio
async def test_get_benchmark_comparison_empty(client: AsyncClient, session: AsyncSession):
    """GET /v4/portfolios/{id}/performance/benchmark returns zeros when no data."""
    p = await _seed_portfolio(session, portfolio_name="Benchmark Empty")
    resp = await client.get(f"/v4/portfolios/{p.id}/performance/benchmark")
    assert resp.status_code == 200
    data = resp.json()
    assert data["portfolio_return"] == 0.0


# ══════════════════════════════════════════════════════════════════════
# Risk metrics
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_get_risk_metrics(client: AsyncClient, session: AsyncSession):
    """GET /v4/portfolios/{id}/performance/risk-metrics returns all metrics."""
    p = await _seed_portfolio(session, portfolio_name="Risk Metrics")
    await _seed_performance_snapshot(session, p.id, period_end=date(2025, 5, 31))
    resp = await client.get(f"/v4/portfolios/{p.id}/performance/risk-metrics")
    assert resp.status_code == 200
    data = resp.json()
    assert data["sharpe_ratio"] is not None
    assert data["sortino_ratio"] is not None
    assert data["beta"] is not None
    assert data["alpha"] is not None
    assert data["volatility"] is not None
    assert data["max_drawdown"] is not None
    assert data["up_capture"] is not None
    assert data["down_capture"] is not None


# ══════════════════════════════════════════════════════════════════════
# Drawdown
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_get_drawdown(client: AsyncClient, session: AsyncSession):
    """GET /v4/portfolios/{id}/performance/drawdown returns analysis."""
    p = await _seed_portfolio(session, portfolio_name="Drawdown Analysis")
    await _seed_performance_snapshot(session, p.id, period_end=date(2025, 7, 31))
    resp = await client.get(f"/v4/portfolios/{p.id}/performance/drawdown")
    assert resp.status_code == 200
    data = resp.json()
    assert "max_drawdown" in data
    assert data["max_drawdown"] is not None


# ══════════════════════════════════════════════════════════════════════
# Attribution
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_get_attribution_empty(client: AsyncClient, session: AsyncSession):
    """GET /v4/portfolios/{id}/attribution returns empty when no data."""
    p = await _seed_portfolio(session, portfolio_name="Attr Empty")
    resp = await client.get(f"/v4/portfolios/{p.id}/attribution")
    assert resp.status_code == 200
    data = resp.json()
    assert data["factor_detail"] == []
    assert data["top_contributors"] == []


@pytest.mark.asyncio
async def test_get_attribution_with_data(client: AsyncClient, session: AsyncSession):
    """GET /v4/portfolios/{id}/attribution returns full result."""
    p = await _seed_portfolio(session, portfolio_name="Attr Data")
    await _seed_attribution(session, p.id)
    resp = await client.get(f"/v4/portfolios/{p.id}/attribution")
    assert resp.status_code == 200
    data = resp.json()
    assert data["brinson"] is not None
    assert data["brinson"]["total_portfolio_return"] is not None
    assert len(data["factor_detail"]) >= 1
    assert len(data["top_contributors"]) >= 1


@pytest.mark.asyncio
async def test_get_sector_attribution(client: AsyncClient, session: AsyncSession):
    """GET /v4/portfolios/{id}/attribution/sectors returns sectors."""
    p = await _seed_portfolio(session, portfolio_name="Attr Sectors")
    await _seed_attribution(session, p.id, period_end=date(2025, 8, 31))
    resp = await client.get(f"/v4/portfolios/{p.id}/attribution/sectors")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert data[0]["sector"] == "Technology"


@pytest.mark.asyncio
async def test_get_security_attribution(client: AsyncClient, session: AsyncSession):
    """GET /v4/portfolios/{id}/attribution/securities returns securities."""
    p = await _seed_portfolio(session, portfolio_name="Attr Securities")
    await _seed_attribution(session, p.id, period_end=date(2025, 9, 30))
    resp = await client.get(f"/v4/portfolios/{p.id}/attribution/securities")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1


@pytest.mark.asyncio
async def test_get_factor_attribution(client: AsyncClient, session: AsyncSession):
    """GET /v4/portfolios/{id}/attribution/factors returns factors."""
    p = await _seed_portfolio(session, portfolio_name="Attr Factors")
    await _seed_attribution(session, p.id, period_end=date(2025, 10, 31))
    resp = await client.get(f"/v4/portfolios/{p.id}/attribution/factors")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert data[0]["factor"] == "Momentum"


# ══════════════════════════════════════════════════════════════════════
# Contributors
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_get_best_contributors(client: AsyncClient, session: AsyncSession):
    """GET /v4/portfolios/{id}/contributors/best returns top 5."""
    p = await _seed_portfolio(session, portfolio_name="Best Contributors")
    await _seed_attribution(session, p.id, period_end=date(2025, 11, 30))
    resp = await client.get(f"/v4/portfolios/{p.id}/contributors/best")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) <= 5
    # First entry should have highest contribution
    if len(data) >= 2:
        assert data[0]["contribution"] >= data[1]["contribution"]


@pytest.mark.asyncio
async def test_get_worst_contributors(client: AsyncClient, session: AsyncSession):
    """GET /v4/portfolios/{id}/contributors/worst returns bottom 5."""
    p = await _seed_portfolio(session, portfolio_name="Worst Contributors")
    await _seed_attribution(session, p.id, period_end=date(2025, 12, 31))
    resp = await client.get(f"/v4/portfolios/{p.id}/contributors/worst")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) <= 5
    # First entry should have lowest contribution
    if len(data) >= 2:
        assert data[0]["contribution"] <= data[1]["contribution"]


# ══════════════════════════════════════════════════════════════════════
# Reports
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_generate_summary_report(client: AsyncClient, session: AsyncSession):
    """POST /v4/portfolios/{id}/reports/summary creates report."""
    p = await _seed_portfolio(session, portfolio_name="Report Summary")
    resp = await client.post(f"/v4/portfolios/{p.id}/reports/summary")
    assert resp.status_code == 201
    data = resp.json()
    assert data["report_type"] == "SUMMARY"
    assert data["status"] == "COMPLETED"
    assert data["data"] is not None


@pytest.mark.asyncio
async def test_generate_performance_report(client: AsyncClient, session: AsyncSession):
    """POST /v4/portfolios/{id}/reports/performance creates report."""
    p = await _seed_portfolio(session, portfolio_name="Report Performance")
    resp = await client.post(
        f"/v4/portfolios/{p.id}/reports/performance",
        json={"report_type": "PERFORMANCE", "format": "json"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["report_type"] == "PERFORMANCE"


@pytest.mark.asyncio
async def test_generate_attribution_report(client: AsyncClient, session: AsyncSession):
    """POST /v4/portfolios/{id}/reports/attribution creates report."""
    p = await _seed_portfolio(session, portfolio_name="Report Attribution")
    resp = await client.post(f"/v4/portfolios/{p.id}/reports/attribution")
    assert resp.status_code == 201
    data = resp.json()
    assert data["report_type"] == "ATTRIBUTION"


@pytest.mark.asyncio
async def test_generate_holdings_report(client: AsyncClient, session: AsyncSession):
    """POST /v4/portfolios/{id}/reports/holdings creates report."""
    p = await _seed_portfolio(session, portfolio_name="Report Holdings")
    resp = await client.post(f"/v4/portfolios/{p.id}/reports/holdings")
    assert resp.status_code == 201
    data = resp.json()
    assert data["report_type"] == "HOLDINGS"


@pytest.mark.asyncio
async def test_report_with_period(client: AsyncClient, session: AsyncSession):
    """POST /v4/portfolios/{id}/reports/summary with period params."""
    p = await _seed_portfolio(session, portfolio_name="Report Period")
    resp = await client.post(
        f"/v4/portfolios/{p.id}/reports/summary",
        json={
            "report_type": "SUMMARY",
            "format": "pdf",
            "period_start": "2025-01-01",
            "period_end": "2025-06-30",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["format"] == "pdf"


# ══════════════════════════════════════════════════════════════════════
# Exports
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_export_holdings_csv(client: AsyncClient, session: AsyncSession):
    """GET /v4/portfolios/{id}/export/holdings returns CSV."""
    p = await _seed_portfolio(session, portfolio_name="Export Holdings")
    await _seed_position(session, p.id, ticker="AAPL")
    await _seed_position(session, p.id, ticker="MSFT")
    resp = await client.get(f"/v4/portfolios/{p.id}/export/holdings")
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    content = resp.text
    assert "ticker" in content
    assert "AAPL" in content
    assert "MSFT" in content


@pytest.mark.asyncio
async def test_export_transactions_csv(client: AsyncClient, session: AsyncSession):
    """GET /v4/portfolios/{id}/export/transactions returns CSV."""
    p = await _seed_portfolio(session, portfolio_name="Export Txns")
    await _seed_transaction(session, p.id)
    resp = await client.get(f"/v4/portfolios/{p.id}/export/transactions")
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    content = resp.text
    assert "date" in content
    assert "AAPL" in content


@pytest.mark.asyncio
async def test_export_nav_csv(client: AsyncClient, session: AsyncSession):
    """GET /v4/portfolios/{id}/export/nav returns CSV."""
    p = await _seed_portfolio(session, portfolio_name="Export NAV")
    await _seed_nav_snapshot(session, p.id)
    resp = await client.get(f"/v4/portfolios/{p.id}/export/nav")
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    content = resp.text
    assert "nav" in content


@pytest.mark.asyncio
async def test_export_returns_csv(client: AsyncClient, session: AsyncSession):
    """GET /v4/portfolios/{id}/export/returns returns CSV."""
    p = await _seed_portfolio(session, portfolio_name="Export Returns")
    await _seed_performance_snapshot(session, p.id, period_end=date(2026, 1, 31))
    resp = await client.get(f"/v4/portfolios/{p.id}/export/returns")
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    content = resp.text
    assert "twr_return" in content


# ══════════════════════════════════════════════════════════════════════
# Compare
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_compare_portfolios(client: AsyncClient, session: AsyncSession):
    """GET /v4/portfolios/performance/compare with 2 IDs."""
    p1 = await _seed_portfolio(session, portfolio_name="Compare A")
    p2 = await _seed_portfolio(session, portfolio_name="Compare B")
    await _seed_performance_snapshot(session, p1.id, period_end=date(2026, 2, 28))
    await _seed_performance_snapshot(session, p2.id, period_end=date(2026, 3, 31))
    resp = await client.get(
        f"/v4/portfolios/performance/compare?ids={p1.id},{p2.id}"
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["portfolios"]) == 2
    names = [e["portfolio_name"] for e in data["portfolios"]]
    assert "Compare A" in names
    assert "Compare B" in names


@pytest.mark.asyncio
async def test_compare_portfolios_partial(client: AsyncClient, session: AsyncSession):
    """GET /v4/portfolios/performance/compare with one missing ID skips it."""
    p1 = await _seed_portfolio(session, portfolio_name="Compare Partial")
    fake_id = uuid.uuid4()
    resp = await client.get(
        f"/v4/portfolios/performance/compare?ids={p1.id},{fake_id}"
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["portfolios"]) == 1


# ══════════════════════════════════════════════════════════════════════
# 404 for missing portfolio on various endpoints
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_performance_returns_404(client: AsyncClient, session: AsyncSession):
    """GET /v4/portfolios/{id}/performance/returns returns 404."""
    resp = await client.get(f"/v4/portfolios/{uuid.uuid4()}/performance/returns")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_attribution_404(client: AsyncClient, session: AsyncSession):
    """GET /v4/portfolios/{id}/attribution returns 404."""
    resp = await client.get(f"/v4/portfolios/{uuid.uuid4()}/attribution")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_risk_metrics_404(client: AsyncClient, session: AsyncSession):
    """GET /v4/portfolios/{id}/performance/risk-metrics returns 404."""
    resp = await client.get(f"/v4/portfolios/{uuid.uuid4()}/performance/risk-metrics")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_export_holdings_404(client: AsyncClient, session: AsyncSession):
    """GET /v4/portfolios/{id}/export/holdings returns 404."""
    resp = await client.get(f"/v4/portfolios/{uuid.uuid4()}/export/holdings")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_report_summary_404(client: AsyncClient, session: AsyncSession):
    """POST /v4/portfolios/{id}/reports/summary returns 404."""
    resp = await client.post(f"/v4/portfolios/{uuid.uuid4()}/reports/summary")
    assert resp.status_code == 404
