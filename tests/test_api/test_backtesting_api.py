"""API tests for backtesting endpoints (Pillar 2 Supplement – Part 3)."""

import uuid
from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.backtesting import BacktestResult, BacktestRun


# ── Helpers ──────────────────────────────────────────────────────────

async def _seed_backtest_run(session: AsyncSession, backtest_id: uuid.UUID) -> BacktestRun:
    run = BacktestRun(
        backtest_id=backtest_id,
        name="Test Value Strategy",
        description="A test strategy",
        status="COMPLETED",
        strategy_definition={"filters": {"pe_ratio": {"max": 20}}, "ranking": {"metric": "pe_ratio"}},
        start_date=date(2020, 1, 1),
        end_date=date(2023, 12, 31),
        benchmark="SP500",
        weighting_method="EQUAL",
        rebalance_frequency="QUARTERLY",
        max_positions=30,
        transaction_cost_bps=10.0,
    )
    session.add(run)
    await session.commit()
    return run


async def _seed_backtest_result(
    session: AsyncSession, backtest_id: uuid.UUID
) -> BacktestResult:
    result = BacktestResult(
        result_id=uuid.uuid4(),
        backtest_id=backtest_id,
        total_return=0.45,
        annualized_return=0.098,
        benchmark_return=0.35,
        excess_return=0.10,
        sharpe_ratio=1.25,
        sortino_ratio=1.80,
        max_drawdown=0.15,
        max_drawdown_duration_days=45,
        annualized_volatility=0.12,
        beta=0.95,
        tracking_error=0.05,
        information_ratio=2.0,
        win_rate=0.55,
        avg_win=0.012,
        avg_loss=-0.008,
        turnover_annual=1.2,
        total_trades=120,
        monthly_returns={"2020-01": 0.02, "2020-02": -0.01, "2020-03": 0.03},
        period_holdings={"2020-01-01": [{"security_id": "abc", "weight": 0.5}]},
        sector_attribution={"Technology": 0.03, "Healthcare": 0.01},
    )
    session.add(result)
    await session.commit()
    return result


# ── Tests ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_submit_backtest(client: AsyncClient):
    """POST /v1/analytics/backtest creates a new backtest run."""
    resp = await client.post(
        "/v1/analytics/backtest",
        json={
            "name": "My Value Strategy",
            "strategy_definition": {"filters": {"pe_ratio": {"max": 15}}},
            "start_date": "2020-01-01",
            "end_date": "2023-12-31",
            "benchmark": "SP500",
            "weighting_method": "EQUAL",
            "rebalance_frequency": "QUARTERLY",
            "max_positions": 25,
            "transaction_cost_bps": 15.0,
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "My Value Strategy"
    assert data["status"] == "COMPLETED"
    assert data["max_positions"] == 25


@pytest.mark.asyncio
async def test_get_backtest_results(client: AsyncClient, session: AsyncSession):
    """GET /v1/analytics/backtest/{id}/results returns performance metrics."""
    bid = uuid.uuid4()
    await _seed_backtest_run(session, bid)
    await _seed_backtest_result(session, bid)

    resp = await client.get(f"/v1/analytics/backtest/{bid}/results")
    assert resp.status_code == 200
    data = resp.json()
    assert data["backtest_id"] == str(bid)
    assert data["total_return"] == pytest.approx(0.45, abs=0.001)
    assert data["sharpe_ratio"] == pytest.approx(1.25, abs=0.01)
    assert data["max_drawdown"] == pytest.approx(0.15, abs=0.001)


@pytest.mark.asyncio
async def test_get_backtest_results_404(client: AsyncClient):
    """GET /v1/analytics/backtest/{id}/results returns 404 for unknown ID."""
    resp = await client.get(f"/v1/analytics/backtest/{uuid.uuid4()}/results")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_backtest_holdings(client: AsyncClient, session: AsyncSession):
    """GET /v1/analytics/backtest/{id}/holdings returns holdings."""
    bid = uuid.uuid4()
    await _seed_backtest_run(session, bid)
    await _seed_backtest_result(session, bid)

    resp = await client.get(f"/v1/analytics/backtest/{bid}/holdings")
    assert resp.status_code == 200
    data = resp.json()
    assert data["backtest_id"] == str(bid)
    assert data["period_holdings"] is not None


@pytest.mark.asyncio
async def test_compare_backtests(client: AsyncClient, session: AsyncSession):
    """POST /v1/analytics/backtest/compare compares multiple backtests."""
    bid1 = uuid.uuid4()
    bid2 = uuid.uuid4()
    await _seed_backtest_run(session, bid1)
    await _seed_backtest_result(session, bid1)
    await _seed_backtest_run(session, bid2)
    await _seed_backtest_result(session, bid2)

    resp = await client.post(
        "/v1/analytics/backtest/compare",
        json={"backtest_ids": [str(bid1), str(bid2)]},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["backtests"]) == 2


@pytest.mark.asyncio
async def test_compare_backtests_partial(client: AsyncClient, session: AsyncSession):
    """POST /v1/analytics/backtest/compare with one missing backtest."""
    bid1 = uuid.uuid4()
    await _seed_backtest_run(session, bid1)
    await _seed_backtest_result(session, bid1)

    resp = await client.post(
        "/v1/analytics/backtest/compare",
        json={"backtest_ids": [str(bid1), str(uuid.uuid4())]},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["backtests"]) == 1  # only one found
