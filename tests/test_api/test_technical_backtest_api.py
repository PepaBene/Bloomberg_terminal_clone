"""API tests for technical backtest endpoints (Pillar 2 Supplement – Part 6)."""

import math

import pytest
from httpx import AsyncClient


def _sample_prices(n: int = 200) -> list[float]:
    """Generate sample price series."""
    import random
    random.seed(123)
    prices = [100.0]
    for _ in range(n - 1):
        change = random.gauss(0.001, 0.015)
        prices.append(prices[-1] * (1 + change))
    return [round(p, 2) for p in prices]


@pytest.mark.asyncio
async def test_submit_ma_crossover_backtest(client: AsyncClient):
    resp = await client.post("/v1/analytics/technical-backtest", json={
        "name": "MA Crossover Test",
        "indicator": "MA_CROSSOVER",
        "fast_period": 5,
        "slow_period": 20,
        "ma_type": "SMA",
        "prices": _sample_prices(200),
        "initial_capital": 100000,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "MA Crossover Test"
    assert data["indicator"] == "MA_CROSSOVER"
    assert "total_trades" in data
    assert "final_value" in data
    assert "sharpe_ratio" in data


@pytest.mark.asyncio
async def test_submit_rsi_backtest(client: AsyncClient):
    resp = await client.post("/v1/analytics/technical-backtest", json={
        "name": "RSI Test",
        "indicator": "RSI",
        "rsi_period": 14,
        "rsi_overbought": 70,
        "rsi_oversold": 30,
        "prices": _sample_prices(200),
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["indicator"] == "RSI"


@pytest.mark.asyncio
async def test_submit_bollinger_backtest(client: AsyncClient):
    resp = await client.post("/v1/analytics/technical-backtest", json={
        "name": "Bollinger Test",
        "indicator": "BOLLINGER",
        "bb_period": 20,
        "bb_std": 2.0,
        "prices": _sample_prices(200),
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["indicator"] == "BOLLINGER"


@pytest.mark.asyncio
async def test_submit_combined_backtest(client: AsyncClient):
    resp = await client.post("/v1/analytics/technical-backtest", json={
        "name": "Combined Test",
        "indicator": "COMBINED",
        "prices": _sample_prices(200),
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["indicator"] == "COMBINED"


@pytest.mark.asyncio
async def test_empty_prices(client: AsyncClient):
    resp = await client.post("/v1/analytics/technical-backtest", json={
        "name": "Empty Test",
        "indicator": "MA_CROSSOVER",
        "prices": [],
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_trades"] == 0
    assert data["final_value"] == 100000.0


@pytest.mark.asyncio
async def test_backtest_response_fields(client: AsyncClient):
    resp = await client.post("/v1/analytics/technical-backtest", json={
        "name": "Fields Test",
        "indicator": "MA_CROSSOVER",
        "prices": _sample_prices(200),
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "backtest_id" in data
    assert "signals_generated" in data
    assert "max_drawdown" in data
    assert "win_rate" in data
    assert "annualized_return" in data
    assert "annualized_volatility" in data
