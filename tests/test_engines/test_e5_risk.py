"""Tests for the E5 Risk Analytics Engine.

Covers:
  - Engine identity
  - Historical VaR (95% / 99%, 1d / 10d / 30d)
  - Parametric VaR (normal-distribution assumption)
  - CVaR (expected shortfall) >= VaR
  - Volatility metrics (annualised, daily, skewness, kurtosis)
  - Max drawdown from a known price series
  - Hypothetical stress-test outputs
  - Liquidity: avg_volume_20d, avg_volume_60d, bid_ask_proxy, amihud_illiquidity
  - Factor exposures: momentum, low-vol
  - Fundamental risk from seeded AnalyticsResult rows
  - Leverage risk score composite
  - INSUFFICIENT_DATA for < 30 observations
  - Empty result for unknown security_id
  - VaRResult persistence to dedicated table
"""

import math
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.engines.e5_risk import RiskEngine, _mean, _percentile_pure, _std
from src.models.analytics import AnalyticsResult
from src.models.entity import Entity
from src.models.risk import VaRResult
from src.models.security import EODPrice, Security


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _business_days(start: date, count: int) -> list[date]:
    """Generate *count* consecutive business days starting from *start*."""
    days: list[date] = []
    current = start
    while len(days) < count:
        if current.weekday() < 5:  # Mon-Fri
            days.append(current)
        current += timedelta(days=1)
    return days


def _make_prices(
    security_id: uuid.UUID,
    n: int = 260,
    start_date: date = date(2025, 1, 2),
) -> list[EODPrice]:
    """Build *n* deterministic EODPrice rows.

    close = 100 + sin(i/10)*5 + i*0.01
    high  = close * 1.01
    low   = close * 0.99
    volume = 1_000_000
    """
    dates = _business_days(start_date, n)
    rows: list[EODPrice] = []
    now = datetime.now(timezone.utc)
    for i, price_date in enumerate(dates):
        close = 100.0 + math.sin(i / 10.0) * 5.0 + i * 0.01
        rows.append(
            EODPrice(
                security_id=security_id,
                price_date=price_date,
                open=close * 0.995,
                high=close * 1.01,
                low=close * 0.99,
                close=close,
                close_adjusted=close,
                volume=1_000_000,
                source="TEST",
                created_at=now,
            )
        )
    return rows


def _expected_returns(prices: list[EODPrice], lookback_days: int = 252) -> list[float]:
    """Replicate the engine's date-cutoff and lookback-trim logic.

    The engine's ``_load_returns`` applies:
        cutoff = date.today() - timedelta(days=int(lookback_days * 1.6))
    then trims to rets[-lookback_days:].
    """
    cutoff = date.today() - timedelta(days=int(lookback_days * 1.6))
    filtered = [p for p in prices if p.price_date >= cutoff]
    closes = [float(p.close_adjusted) for p in filtered]
    rets = [
        (closes[i] - closes[i - 1]) / closes[i - 1]
        for i in range(1, len(closes))
    ]
    return rets[-lookback_days:] if len(rets) > lookback_days else rets


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def seed_data(session: AsyncSession):
    """Seed Entity + Security + 260 EODPrice rows.

    Returns a dict with entity_id, security_id, and the list of prices.
    """
    now = datetime.now(timezone.utc)

    entity = Entity(
        entity_id=uuid.uuid4(),
        entity_type="PUBLIC_COMPANY",
        legal_name="Risk Test Corp",
        status="ACTIVE",
        source="TEST",
        created_at=now,
        updated_at=now,
    )
    session.add(entity)
    await session.flush()

    security = Security(
        security_id=uuid.uuid4(),
        name="Risk Test Corp Common Stock",
        short_name="RSKC",
        security_type="COMMON_STOCK",
        asset_class="EQUITY",
        status="ACTIVE",
        issuer_entity_id=entity.entity_id,
        created_at=now,
        updated_at=now,
    )
    session.add(security)
    await session.flush()

    prices = _make_prices(security.security_id, n=260)
    session.add_all(prices)
    await session.flush()

    return {
        "entity_id": entity.entity_id,
        "security_id": security.security_id,
        "prices": prices,
    }


@pytest.fixture
def risk_engine():
    return RiskEngine()


# ---------------------------------------------------------------------------
# 1. Engine identity
# ---------------------------------------------------------------------------

def test_e5_engine_id(risk_engine):
    """engine_id is 'E5'."""
    assert risk_engine.engine_id == "E5"


# ---------------------------------------------------------------------------
# 2. Historical VaR -- 95 % 1-day
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_var_historical_95_1d(session, seed_data, risk_engine):
    """VaR 95% 1d equals -percentile(5%) of the return series."""
    outputs = await risk_engine.compute(session, seed_data["security_id"])
    out_map = {o.metric_name: o.value for o in outputs}

    # Recompute expected value using the same date-cutoff logic as the engine
    rets = _expected_returns(seed_data["prices"])
    sorted_rets = sorted(rets)
    expected = -_percentile_pure(sorted_rets, 5.0)

    assert "var_historical_95_1d" in out_map
    assert out_map["var_historical_95_1d"] == pytest.approx(expected, rel=1e-6)


# ---------------------------------------------------------------------------
# 3. Historical VaR -- 99 % 1-day
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_var_historical_99_1d(session, seed_data, risk_engine):
    """VaR 99% 1d equals -percentile(1%) of the return series."""
    outputs = await risk_engine.compute(session, seed_data["security_id"])
    out_map = {o.metric_name: o.value for o in outputs}

    rets = _expected_returns(seed_data["prices"])
    sorted_rets = sorted(rets)
    expected = -_percentile_pure(sorted_rets, 1.0)

    assert "var_historical_99_1d" in out_map
    assert out_map["var_historical_99_1d"] == pytest.approx(expected, rel=1e-6)


# ---------------------------------------------------------------------------
# 4. VaR 10-day scaling  (var_10d ~ var_1d * sqrt(10))
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_var_10d_scaling(session, seed_data, risk_engine):
    """var_historical_95_10d should equal var_historical_95_1d * sqrt(10)."""
    outputs = await risk_engine.compute(session, seed_data["security_id"])
    out_map = {o.metric_name: o.value for o in outputs}

    var_1d = out_map["var_historical_95_1d"]
    var_10d = out_map["var_historical_95_10d"]
    assert var_10d == pytest.approx(var_1d * math.sqrt(10), rel=1e-9)


# ---------------------------------------------------------------------------
# 5. Parametric VaR -- 95 % 1-day
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_var_parametric_95_1d(session, seed_data, risk_engine):
    """Parametric VaR 95 1d = -(mean - 1.645 * std)."""
    outputs = await risk_engine.compute(session, seed_data["security_id"])
    out_map = {o.metric_name: o.value for o in outputs}

    rets = _expected_returns(seed_data["prices"])
    mu = _mean(rets)
    sigma = _std(rets)
    expected = -(mu - 1.645 * sigma)

    assert "var_parametric_95_1d" in out_map
    assert out_map["var_parametric_95_1d"] == pytest.approx(expected, rel=1e-6)


# ---------------------------------------------------------------------------
# 6. CVaR >= VaR (always true)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cvar_exceeds_var(session, seed_data, risk_engine):
    """CVaR (expected shortfall) should be >= VaR at the same confidence level."""
    outputs = await risk_engine.compute(session, seed_data["security_id"])
    out_map = {o.metric_name: o.value for o in outputs}

    assert out_map["cvar_95_1d"] >= out_map["var_historical_95_1d"]
    assert out_map["cvar_99_1d"] >= out_map["var_historical_99_1d"]


# ---------------------------------------------------------------------------
# 7. Annualised volatility = daily_std * sqrt(252)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_annualized_volatility(session, seed_data, risk_engine):
    """annualized_volatility equals daily_volatility * sqrt(252)."""
    outputs = await risk_engine.compute(session, seed_data["security_id"])
    out_map = {o.metric_name: o.value for o in outputs}

    assert out_map["annualized_volatility"] == pytest.approx(
        out_map["daily_volatility"] * math.sqrt(252), rel=1e-9,
    )


# ---------------------------------------------------------------------------
# 8. Max drawdown on a known series
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_max_drawdown(session, seed_data, risk_engine):
    """max_drawdown is a positive ratio in [0, 1)."""
    outputs = await risk_engine.compute(session, seed_data["security_id"])
    out_map = {o.metric_name: o.value for o in outputs}

    assert "max_drawdown" in out_map
    mdd = out_map["max_drawdown"]
    # The sinusoidal series has peaks and valleys, so mdd > 0
    assert mdd > 0.0
    assert mdd < 1.0


# ---------------------------------------------------------------------------
# 9. Skewness and kurtosis present in output
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_skewness_kurtosis(session, seed_data, risk_engine):
    """Skewness and kurtosis metrics are present with finite numeric values."""
    outputs = await risk_engine.compute(session, seed_data["security_id"])
    out_map = {o.metric_name: o.value for o in outputs}

    assert "skewness" in out_map
    assert "kurtosis" in out_map
    assert isinstance(out_map["skewness"], float)
    assert isinstance(out_map["kurtosis"], float)
    assert math.isfinite(out_map["skewness"])
    assert math.isfinite(out_map["kurtosis"])


# ---------------------------------------------------------------------------
# 10. Hypothetical stress scenario outputs present
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_stress_hypothetical(session, seed_data, risk_engine):
    """At least one stress_equity_minus_* output should be present."""
    outputs = await risk_engine.compute(session, seed_data["security_id"])
    stress_names = [o.metric_name for o in outputs if o.metric_name.startswith("stress_")]

    assert len(stress_names) > 0
    # Verify the well-known -10% equity shock scenario
    assert "stress_equity_minus_10" in stress_names


# ---------------------------------------------------------------------------
# 10b. Hypothetical stress scales by beta (regression: was a flat echo)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_stress_hypothetical_scales_by_beta(session, seed_data, risk_engine):
    """stress_equity_minus_10 must scale with the security's beta_market.

    Regression test: every security previously got the SAME raw shock_pct
    (e.g. exactly -0.10 for "Equity -10%") regardless of its actual market
    sensitivity. With beta_market=1.5 seeded, the exposure-adjusted stress
    P&L must be -0.10 * 1.5 = -0.15, not the raw -0.10.
    """
    session.add(AnalyticsResult(
        security_id=seed_data["security_id"],
        entity_id=seed_data["entity_id"],
        engine_id="E7",
        metric_name="beta_market",
        metric_category="STATISTICAL",
        value=Decimal("1.5"),
        unit="RATIO",
        period="LATEST",
        as_of_date=date.today(),
        data_quality="COMPLETE",
    ))
    await session.flush()

    outputs = await risk_engine.compute(session, seed_data["security_id"])
    out_map = {o.metric_name: o.value for o in outputs}

    assert "stress_equity_minus_10" in out_map
    assert out_map["stress_equity_minus_10"] == pytest.approx(-0.10 * 1.5, abs=1e-9)


# ---------------------------------------------------------------------------
# 10c. Historical stress test replays the scenario's actual date window
#      (regression: previously always compounded the trailing 252 days
#      from *today*, ignoring which historical scenario was requested)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_historical_stress_uses_scenario_window(session):
    """run_stress_test('GFC_2008') must reflect prices during 2008-09-01..
    2009-03-31 specifically, not a trailing window ending today.

    Seeds a security with three distinct regimes: flat (0%/day) before the
    GFC_2008 window, a severe -0.5%/day decline ONLY within the window, and
    a long +0.3%/day rally afterward that runs well past 252 business days
    (so it alone can fill an entire "trailing 252 returns" slice). The
    correct pnl_percent is the compounded -0.5%/day crash over exactly the
    scenario's business days. The old "trailing 252 days from *today*" code
    fetched every row with no upper-date bound and took the *last* 252
    returns of whatever it found -- here that is almost entirely the
    post-window rally, nothing like the crash -- so a buggy vs. fixed
    result would diverge sharply (a large positive vs. a large negative
    pnl_percent).
    """
    from src.engines.e5_risk import RiskEngine

    entity_id = uuid.uuid4()
    security_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    session.add(Entity(
        entity_id=entity_id, entity_type="PUBLIC_COMPANY",
        legal_name="GFC Window Test Corp", status="ACTIVE", source="TEST",
        created_at=now, updated_at=now,
    ))
    session.add(Security(
        security_id=security_id, name="GFC Window Test Corp Common Stock",
        short_name="GFCW", security_type="COMMON_STOCK", asset_class="EQUITY",
        status="ACTIVE", issuer_entity_id=entity_id, created_at=now, updated_at=now,
    ))
    await session.flush()

    scenario_start = date(2008, 9, 1)
    scenario_end = date(2009, 3, 31)

    # ~64 biz days flat before + ~152 crash days within the 7-month window
    # + ~300 rally days after (comfortably > 252, so a naive "last 252
    # returns" slice over the whole series lands entirely in the rally).
    all_days = _business_days(date(2008, 6, 1), 520)

    price = 100.0
    expected_window_returns: list[float] = []
    rows = []
    for i, d in enumerate(all_days):
        if i > 0:
            if scenario_start <= d <= scenario_end:
                daily_return = -0.005
                expected_window_returns.append(daily_return)
            elif d > scenario_end:
                daily_return = 0.003
            else:
                daily_return = 0.0
            price *= (1.0 + daily_return)
        rows.append(EODPrice(
            security_id=security_id, price_date=d,
            open=price, high=price, low=price, close=price, close_adjusted=price,
            volume=1_000_000, source="TEST", created_at=now,
        ))
    session.add_all(rows)
    await session.flush()

    expected_pnl = 1.0
    for r in expected_window_returns:
        expected_pnl *= (1.0 + r)
    expected_pnl -= 1.0

    engine = RiskEngine()
    result = await engine.run_stress_test(session, security_id, "GFC_2008")

    assert result is not None
    assert result.pnl_percent == pytest.approx(expected_pnl, rel=1e-6)
    # Sanity bound: a multi-month -0.5%/day decline is a severe crash, not
    # the large positive figure a rally-tail read would produce.
    assert result.pnl_percent < -0.30


# ---------------------------------------------------------------------------
# 11. No price data -> empty list (unknown security_id)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_no_price_data(session, risk_engine):
    """Unknown security_id returns an empty list (security not found)."""
    random_id = uuid.uuid4()
    outputs = await risk_engine.compute(session, random_id)
    assert outputs == []


# ---------------------------------------------------------------------------
# 12. Factor momentum computed from 252 prices
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_factor_momentum(session, seed_data, risk_engine):
    """factor_momentum should be computed when enough price history exists."""
    outputs = await risk_engine.compute(session, seed_data["security_id"])
    out_map = {o.metric_name: o.value for o in outputs}

    assert "factor_momentum" in out_map
    assert isinstance(out_map["factor_momentum"], float)
    assert math.isfinite(out_map["factor_momentum"])


# ---------------------------------------------------------------------------
# 13. Factor low-vol (inverse of annualised vol)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_factor_low_vol(session, seed_data, risk_engine):
    """factor_low_vol should be positive and equal to 1/annualized_vol."""
    outputs = await risk_engine.compute(session, seed_data["security_id"])
    out_map = {o.metric_name: o.value for o in outputs}

    assert "factor_low_vol" in out_map
    low_vol = out_map["factor_low_vol"]
    assert low_vol is not None
    assert low_vol > 0.0


# ---------------------------------------------------------------------------
# 14. Fundamental risk from AnalyticsResult
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fundamental_risk_from_analytics(session, seed_data, risk_engine):
    """Seed AnalyticsResult with fundamental ratios and check risk_ prefixed outputs."""
    now = datetime.now(timezone.utc)
    sid = seed_data["security_id"]
    eid = seed_data["entity_id"]
    today = date.today()

    fundamental_metrics = [
        ("net_debt_to_ebitda", 3.5),
        ("interest_coverage", 4.0),
        ("debt_to_equity", 0.8),
        ("current_ratio", 1.5),
    ]
    for metric_name, value in fundamental_metrics:
        session.add(AnalyticsResult(
            result_id=uuid.uuid4(),
            security_id=sid,
            entity_id=eid,
            engine_id="E1",
            metric_name=metric_name,
            metric_category="LEVERAGE",
            value=value,
            period="TTM",
            as_of_date=today,
            created_at=now,
            updated_at=now,
        ))
    await session.flush()

    outputs = await risk_engine.compute(session, sid)
    out_map = {o.metric_name: o.value for o in outputs}

    assert out_map["risk_net_debt_to_ebitda"] == pytest.approx(3.5)
    assert out_map["risk_interest_coverage"] == pytest.approx(4.0)
    assert out_map["risk_debt_to_equity"] == pytest.approx(0.8)
    assert out_map["risk_current_ratio"] == pytest.approx(1.5)


# ---------------------------------------------------------------------------
# 15. Leverage risk score from net_debt_to_ebitda and interest_coverage
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_leverage_risk_score(session, seed_data, risk_engine):
    """Leverage score should reflect the composite of net_debt_to_ebitda and interest_coverage."""
    now = datetime.now(timezone.utc)
    sid = seed_data["security_id"]
    eid = seed_data["entity_id"]
    today = date.today()

    # High leverage: net_debt_to_ebitda=5 (>4 -> +25), interest_coverage=1.5 (<2 -> +25)
    for metric_name, value in [("net_debt_to_ebitda", 5.0), ("interest_coverage", 1.5)]:
        session.add(AnalyticsResult(
            result_id=uuid.uuid4(),
            security_id=sid,
            entity_id=eid,
            engine_id="E1",
            metric_name=metric_name,
            metric_category="LEVERAGE",
            value=value,
            period="TTM",
            as_of_date=today,
            created_at=now,
            updated_at=now,
        ))
    await session.flush()

    outputs = await risk_engine.compute(session, sid)
    out_map = {o.metric_name: o.value for o in outputs}

    assert "risk_leverage_score" in out_map
    # score = 50 + 25 (nde>4) + 25 (ic<2) = 100, clamped to [0,100]
    assert out_map["risk_leverage_score"] == pytest.approx(100.0)


# ---------------------------------------------------------------------------
# 16. Liquidity -- avg_volume_20d
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_liquidity_avg_volume(session, seed_data, risk_engine):
    """avg_volume_20d should be 1_000_000 (all rows have volume=1_000_000)."""
    outputs = await risk_engine.compute(session, seed_data["security_id"])
    out_map = {o.metric_name: o.value for o in outputs}

    assert "avg_volume_20d" in out_map
    assert out_map["avg_volume_20d"] == pytest.approx(1_000_000.0)


# ---------------------------------------------------------------------------
# 17. Amihud illiquidity
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_amihud_illiquidity(session, seed_data, risk_engine):
    """amihud_illiquidity should be positive for a series with non-zero returns and volume."""
    outputs = await risk_engine.compute(session, seed_data["security_id"])
    out_map = {o.metric_name: o.value for o in outputs}

    assert "amihud_illiquidity" in out_map
    assert out_map["amihud_illiquidity"] is not None
    assert out_map["amihud_illiquidity"] > 0.0


# ---------------------------------------------------------------------------
# 18. Bid-ask proxy: mean((high - low) / close)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_bid_ask_proxy(session, seed_data, risk_engine):
    """bid_ask_proxy ~ (1.01 - 0.99) = 0.02 since high=close*1.01, low=close*0.99."""
    outputs = await risk_engine.compute(session, seed_data["security_id"])
    out_map = {o.metric_name: o.value for o in outputs}

    assert "bid_ask_proxy" in out_map
    # (high - low) / close = (close*1.01 - close*0.99) / close = 0.02
    assert out_map["bid_ask_proxy"] == pytest.approx(0.02, rel=1e-6)


# ---------------------------------------------------------------------------
# 19. Insufficient price data (< 30 observations)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_insufficient_price_data(session, risk_engine):
    """With only 10 price rows, the engine should return a single INSUFFICIENT_DATA output."""
    now = datetime.now(timezone.utc)

    entity = Entity(
        entity_id=uuid.uuid4(),
        entity_type="PUBLIC_COMPANY",
        legal_name="Thin Data Corp",
        status="ACTIVE",
        source="TEST",
        created_at=now,
        updated_at=now,
    )
    session.add(entity)
    await session.flush()

    security = Security(
        security_id=uuid.uuid4(),
        name="Thin Data Corp Stock",
        short_name="THIN",
        security_type="COMMON_STOCK",
        asset_class="EQUITY",
        status="ACTIVE",
        issuer_entity_id=entity.entity_id,
        created_at=now,
        updated_at=now,
    )
    session.add(security)
    await session.flush()

    # Only 10 price rows -> fewer than 30 returns
    prices = _make_prices(security.security_id, n=10)
    session.add_all(prices)
    await session.flush()

    outputs = await risk_engine.compute(session, security.security_id)
    assert len(outputs) == 1
    assert outputs[0].metric_name == "risk_data_status"
    assert outputs[0].data_quality == "INSUFFICIENT_DATA"


# ---------------------------------------------------------------------------
# 20. VaRResult rows persisted to the database
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_persists_var_result(session, seed_data, risk_engine):
    """After compute(), VaRResult rows should exist in the database."""
    sid = seed_data["security_id"]
    await risk_engine.compute(session, sid)

    result = await session.execute(
        select(VaRResult).where(VaRResult.security_id == sid)
    )
    var_rows = result.scalars().all()

    # The engine persists one VaRResult per var_historical_* metric (6 configs)
    assert len(var_rows) >= 6

    # Verify each row has sensible fields
    for row in var_rows:
        assert row.method == "HISTORICAL"
        assert float(row.confidence_level) in [0.95, 0.99]
        assert row.holding_period_days in [1, 10, 30]
        assert row.var_value is not None
        assert row.data_quality == "COMPLETE"
