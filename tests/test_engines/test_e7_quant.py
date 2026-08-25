"""Tests for E7 Quantitative & Statistical Engine.

Covers pure-Python helpers (_ols, _pearson_corr, _spearman_corr,
_autocorrelation), the default compute() pipeline (beta, correlation,
autocorrelation, ADF), and standalone methods (run_regression,
run_correlation, run_stationarity, run_cointegration,
run_rolling_regression) with DB persistence checks.
"""

import math
import uuid
from datetime import date, datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.engines.base import EngineOutput
from src.engines.e7_quant import (
    QuantEngine,
    _autocorrelation,
    _mean,
    _ols,
    _pearson_corr,
    _rank,
    _spearman_corr,
    _std,
)
from src.models.entity import Entity
from src.models.quant import CorrelationResult, RegressionResult, TimeSeriesTestResult
from src.models.security import EODPrice, Security


# ---------------------------------------------------------------------------
# Fixed IDs
# ---------------------------------------------------------------------------
ENTITY_ID = uuid.uuid4()
SECURITY_ID = uuid.uuid4()
BENCHMARK_ENTITY_ID = uuid.uuid4()
BENCHMARK_ID = uuid.uuid4()

NOW = datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _metric(outputs: list[EngineOutput], name: str) -> EngineOutput | None:
    for o in outputs:
        if o.metric_name == name:
            return o
    return None


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def e7_engine():
    return QuantEngine()


@pytest_asyncio.fixture
async def seeded_security(session: AsyncSession) -> uuid.UUID:
    """Create an entity + security with 100 EOD prices."""
    entity = Entity(
        entity_id=ENTITY_ID,
        legal_name="Quant Test Corp",
        entity_type="PUBLIC_COMPANY",
        status="ACTIVE",
        source="TEST",
    )
    session.add(entity)
    await session.flush()

    security = Security(
        security_id=SECURITY_ID,
        name="Quant Test Corp Common Stock",
        short_name="QTC",
        security_type="COMMON_STOCK",
        asset_class="EQUITY",
        status="ACTIVE",
        issuer_entity_id=ENTITY_ID,
    )
    session.add(security)
    await session.flush()

    # Generate 100 deterministic prices using sin pattern for slight oscillation
    base_date = date.today() - timedelta(days=150)
    for i in range(100):
        price = 100.0 + 0.05 * i + 2.0 * math.sin(i * 0.3)
        session.add(EODPrice(
            security_id=SECURITY_ID,
            price_date=base_date + timedelta(days=i),
            close=price,
            close_adjusted=price,
            source="TEST",
            created_at=NOW,
        ))
    await session.flush()
    return SECURITY_ID


@pytest_asyncio.fixture
async def seeded_benchmark(session: AsyncSession, seeded_security) -> uuid.UUID:
    """Create a benchmark security with 100 correlated EOD prices."""
    bench_entity = Entity(
        entity_id=BENCHMARK_ENTITY_ID,
        legal_name="Benchmark Index",
        entity_type="INDEX",
        status="ACTIVE",
        source="TEST",
    )
    session.add(bench_entity)
    await session.flush()

    bench = Security(
        security_id=BENCHMARK_ID,
        name="Benchmark Index",
        short_name="BENCH",
        security_type="INDEX",
        asset_class="EQUITY",
        status="ACTIVE",
        issuer_entity_id=BENCHMARK_ENTITY_ID,
    )
    session.add(bench)
    await session.flush()

    # Benchmark prices: correlated to security prices but with different scale
    base_date = date.today() - timedelta(days=150)
    for i in range(100):
        price = 200.0 + 0.1 * i + 3.0 * math.sin(i * 0.3)
        session.add(EODPrice(
            security_id=BENCHMARK_ID,
            price_date=base_date + timedelta(days=i),
            close=price,
            close_adjusted=price,
            source="TEST",
            created_at=NOW,
        ))
    await session.flush()
    return BENCHMARK_ID


# ===========================================================================
# 1. Engine identity
# ===========================================================================

def test_e7_engine_id(e7_engine):
    """engine_id must be 'E7'."""
    assert e7_engine.engine_id == "E7"


# ===========================================================================
# 2. OLS known data: y = 2x + 1
# ===========================================================================

def test_ols_known_data():
    """For y = 2*x + 1 (perfect linear), beta ~ 2, intercept ~ 1, R^2 ~ 1."""
    x = [float(i) for i in range(1, 101)]
    y = [2.0 * xi + 1.0 for xi in x]

    result = _ols(x, y)

    assert "error" not in result
    assert result["coefficients"]["x"] == pytest.approx(2.0, abs=1e-6)
    assert result["coefficients"]["intercept"] == pytest.approx(1.0, abs=1e-6)
    assert result["r_squared"] == pytest.approx(1.0, abs=1e-6)


# ===========================================================================
# 3. OLS R-squared range
# ===========================================================================

def test_ols_r_squared_range():
    """R-squared should be in [0, 1] for reasonable data."""
    # Noisy data: y has pattern but also noise via deterministic perturbation
    x = [float(i) for i in range(1, 51)]
    y = [3.0 * xi + 5.0 + 10.0 * math.sin(xi) for xi in x]

    result = _ols(x, y)

    assert "error" not in result
    assert 0.0 <= result["r_squared"] <= 1.0


# ===========================================================================
# 4. OLS std errors positive
# ===========================================================================

def test_ols_std_errors_positive():
    """Standard errors for intercept and x should be present and > 0."""
    x = [float(i) for i in range(1, 51)]
    y = [2.0 * xi + 1.0 + 5.0 * math.sin(xi * 0.7) for xi in x]

    result = _ols(x, y)

    assert "error" not in result
    assert result["std_errors"]["intercept"] > 0
    assert result["std_errors"]["x"] > 0


# ===========================================================================
# 5. OLS confidence intervals
# ===========================================================================

def test_ols_confidence_intervals():
    """95% CI for 'x' should bracket the true beta when there is residual
    noise (so se_beta > 0)."""
    x = [float(i) for i in range(1, 101)]
    # Add small deterministic noise so residuals are non-zero
    y = [2.0 * xi + 1.0 + 0.5 * math.sin(xi * 0.8) for xi in x]

    result = _ols(x, y)

    ci = result["confidence_intervals"]["x"]
    beta = result["coefficients"]["x"]
    assert len(ci) == 2
    assert ci[0] < beta < ci[1]
    # True beta is approximately 2.0; CI should contain it
    assert ci[0] < 2.0 < ci[1]


# ===========================================================================
# 6. OLS insufficient data
# ===========================================================================

def test_ols_insufficient_data():
    """Fewer than 3 data points should return an error dict."""
    result = _ols([1.0, 2.0], [3.0, 4.0])

    assert "error" in result
    assert result["error"] == "insufficient_data"
    assert result["n"] == 2


# ===========================================================================
# 7. Pearson perfect correlation
# ===========================================================================

def test_pearson_perfect_correlation():
    """Identical x and y should give r = 1.0."""
    vals = [float(i) for i in range(3, 53)]
    r, p = _pearson_corr(vals, vals)

    assert r == pytest.approx(1.0, abs=1e-6)


# ===========================================================================
# 8. Pearson negative correlation
# ===========================================================================

def test_pearson_negative_correlation():
    """x vs -x should give r ~ -1.0."""
    x = [float(i) for i in range(1, 51)]
    neg_x = [-xi for xi in x]

    r, p = _pearson_corr(x, neg_x)

    assert r == pytest.approx(-1.0, abs=1e-6)


# ===========================================================================
# 9. Spearman correlation with monotonic non-linear data
# ===========================================================================

def test_spearman_correlation():
    """Monotonic non-linear transform (x^3) should yield high Spearman."""
    x = [float(i) for i in range(1, 51)]
    y = [xi ** 3 for xi in x]

    r, p = _spearman_corr(x, y)

    # Spearman measures monotonic relationships; x^3 is strictly monotonic
    assert r == pytest.approx(1.0, abs=1e-6)


# ===========================================================================
# 10. Autocorrelation lag-1 on known autocorrelated series
# ===========================================================================

def test_autocorrelation_lag1():
    """A slowly varying series (cumulative sum of small steps) should have
    high positive lag-1 autocorrelation."""
    # Build a deterministic autocorrelated series: cumsum of small oscillation
    steps = [math.sin(0.1 * i) for i in range(200)]
    series = []
    running = 0.0
    for s in steps:
        running += s
        series.append(running)

    ac = _autocorrelation(series, lag=1)

    # Cumulative sum of a smooth series should be highly autocorrelated
    assert ac > 0.9


# ===========================================================================
# 11. Autocorrelation of white noise is low
# ===========================================================================

def test_autocorrelation_white_noise():
    """A deterministic pseudo-random series (LCG) should have low
    lag-1 autocorrelation."""
    # Linear congruential generator produces uncorrelated values
    series = []
    x = 12345
    a, c, m = 1103515245, 12345, 2 ** 31
    for _ in range(500):
        x = (a * x + c) % m
        series.append(float(x) / m)

    ac = _autocorrelation(series, lag=1)

    assert abs(ac) < 0.15


# ===========================================================================
# 12. Default compute with benchmark
# ===========================================================================

@pytest.mark.asyncio
async def test_default_compute_with_benchmark(
    session: AsyncSession, e7_engine, seeded_benchmark
):
    """compute() with security + benchmark should produce beta, correlation,
    autocorrelation, and ADF outputs."""
    outputs = await e7_engine.compute(
        session, SECURITY_ID, benchmark_id=BENCHMARK_ID
    )

    assert isinstance(outputs, list)
    assert len(outputs) > 0
    for o in outputs:
        assert isinstance(o, EngineOutput)
        assert o.engine_id == "E7"

    names = {o.metric_name for o in outputs}

    # Beta metrics
    assert "beta_market" in names
    assert "beta_blume_adjusted" in names
    assert "beta_r_squared" in names

    # Correlation metrics
    assert "correlation_market_pearson" in names
    assert "correlation_market_spearman" in names

    # Autocorrelation
    assert "autocorrelation_lag1" in names

    # Beta value should be positive for positively correlated securities
    beta_out = _metric(outputs, "beta_market")
    assert beta_out is not None
    assert beta_out.value is not None
    assert beta_out.value > 0


# ===========================================================================
# 12b. Beta/correlation must align by date, not position, across a
#      benchmark calendar gap
# ===========================================================================

@pytest.mark.asyncio
async def test_beta_aligns_by_date_across_benchmark_gap(session: AsyncSession, e7_engine):
    """Regression test for the position-based alignment bug.

    Security has 100 consecutive daily prices (dates D0..D99). Its per-date
    return at date Dk (k=1..99) is exactly k*0.001. The benchmark has the
    SAME per-date return relationship (bench_return(Dk) = 2 * sec_return(Dk)
    = k*0.002) but is missing a 10-day block in the middle (D45..D54), the
    kind of calendar gap a holiday mismatch or a listing gap produces.

    Regressing sec (y) on bench (x) at matching dates is a perfect line
    (sec = 0.5*bench for every date), so date-correct alignment must recover
    beta ~= 0.5 and r_squared ~= 1.0. The previous position-based code
    truncated both return series to equal length from the *end*, which -
    because of the gap - paired each date's security return against a
    benchmark return from a *different* date, destroying the perfect linear
    relationship (r_squared collapses well below 1.0).
    """
    gap_entity_id = uuid.uuid4()
    gap_security_id = uuid.uuid4()
    gap_bench_entity_id = uuid.uuid4()
    gap_bench_id = uuid.uuid4()

    session.add(Entity(
        entity_id=gap_entity_id, legal_name="Gap Test Corp",
        entity_type="PUBLIC_COMPANY", status="ACTIVE", source="TEST",
    ))
    session.add(Entity(
        entity_id=gap_bench_entity_id, legal_name="Gap Benchmark Index",
        entity_type="INDEX", status="ACTIVE", source="TEST",
    ))
    await session.flush()

    session.add(Security(
        security_id=gap_security_id, name="Gap Test Corp Common Stock",
        short_name="GAP", security_type="COMMON_STOCK", asset_class="EQUITY",
        status="ACTIVE", issuer_entity_id=gap_entity_id,
    ))
    session.add(Security(
        security_id=gap_bench_id, name="Gap Benchmark Index",
        short_name="GAPBM", security_type="INDEX", asset_class="EQUITY",
        status="ACTIVE", issuer_entity_id=gap_bench_entity_id,
    ))
    await session.flush()

    base_date = date.today() - timedelta(days=150)

    # Security: 100 consecutive daily prices, return(Dk) = k * 0.001.
    sec_price = 100.0
    for k in range(100):
        if k > 0:
            sec_price *= 1.0 + k * 0.001
        session.add(EODPrice(
            security_id=gap_security_id, price_date=base_date + timedelta(days=k),
            close=sec_price, close_adjusted=sec_price, source="TEST", created_at=NOW,
        ))

    # Benchmark: same dates MINUS a 10-day gap at k=45..54. No row is
    # inserted for a skipped k, so bench_price is simply left untouched
    # across the gap; the first row after the gap (k=55) is array-adjacent
    # to k=44's row and gets the *same* k*0.002 multiplier every other row
    # gets, so its observed (D44->D55) return still comes out to exactly
    # 55*0.002 = 2 * sec_return(D55) -- i.e. every row the benchmark
    # actually has still obeys the designed 2x relationship for its own
    # date, whether or not its immediate predecessor row was contiguous.
    bench_price = 200.0
    for k in range(100):
        if 45 <= k <= 54:
            continue
        if k != 0:
            bench_price *= 1.0 + k * 0.002
        session.add(EODPrice(
            security_id=gap_bench_id, price_date=base_date + timedelta(days=k),
            close=bench_price, close_adjusted=bench_price, source="TEST", created_at=NOW,
        ))
    await session.flush()

    outputs = await e7_engine.compute(
        session, gap_security_id, benchmark_id=gap_bench_id,
    )

    beta_out = _metric(outputs, "beta_market")
    r_sq_out = _metric(outputs, "beta_r_squared")
    assert beta_out is not None and beta_out.value is not None
    assert r_sq_out is not None and r_sq_out.value is not None

    # Date-correct alignment recovers the exact designed relationship.
    assert beta_out.value == pytest.approx(0.5, abs=1e-6)
    assert r_sq_out.value == pytest.approx(1.0, abs=1e-6)


# ===========================================================================
# 13. Default compute with insufficient data
# ===========================================================================

@pytest.mark.asyncio
async def test_default_compute_insufficient_data(
    session: AsyncSession, e7_engine
):
    """Security with fewer than 30 prices should return INSUFFICIENT_DATA."""
    eid = uuid.uuid4()
    sid = uuid.uuid4()

    entity = Entity(
        entity_id=eid,
        legal_name="Sparse Corp",
        entity_type="PUBLIC_COMPANY",
        status="ACTIVE",
        source="TEST",
    )
    session.add(entity)
    await session.flush()

    security = Security(
        security_id=sid,
        name="Sparse Corp Stock",
        short_name="SPA",
        security_type="COMMON_STOCK",
        asset_class="EQUITY",
        status="ACTIVE",
        issuer_entity_id=eid,
    )
    session.add(security)
    await session.flush()

    # Only 10 prices -> fewer than 30 returns
    base_date = date.today() - timedelta(days=20)
    for i in range(10):
        session.add(EODPrice(
            security_id=sid,
            price_date=base_date + timedelta(days=i),
            close=50.0 + i,
            close_adjusted=50.0 + i,
            source="TEST",
            created_at=NOW,
        ))
    await session.flush()

    outputs = await e7_engine.compute(session, sid)

    assert len(outputs) == 1
    assert outputs[0].data_quality == "INSUFFICIENT_DATA"
    assert outputs[0].metric_name == "quant_data_status"


# ===========================================================================
# 14. run_regression persists to DB
# ===========================================================================

@pytest.mark.asyncio
async def test_run_regression_persists(
    session: AsyncSession, e7_engine, seeded_security
):
    """run_regression should return a regression_id and persist a
    RegressionResult row in the database."""
    x = [float(i) for i in range(1, 51)]
    y = [2.0 * xi + 3.0 + math.sin(xi) for xi in x]

    result = await e7_engine.run_regression(
        session, SECURITY_ID, x, y,
        method="OLS",
        dependent_var="return",
        independent_var="market",
    )

    assert "error" not in result
    assert "regression_id" in result
    assert result["method"] == "OLS"
    assert result["r_squared"] > 0.9
    assert "market" in result["coefficients"]

    # Verify persistence
    row = await session.execute(
        select(RegressionResult).where(
            RegressionResult.regression_id == result["regression_id"]
        )
    )
    reg = row.scalar_one_or_none()
    assert reg is not None
    assert reg.method == "OLS"
    assert reg.dependent_var == "return"
    assert float(reg.r_squared) == pytest.approx(result["r_squared"], abs=1e-4)
    assert reg.n_observations == 50
    assert reg.data_quality == "COMPLETE"


# ===========================================================================
# 15. run_correlation persists to DB
# ===========================================================================

@pytest.mark.asyncio
async def test_run_correlation_persists(session: AsyncSession, e7_engine):
    """run_correlation should return a correlation_id and persist a
    CorrelationResult row in the database."""
    x = [float(i) for i in range(1, 51)]
    y = [3.0 * xi + 1.0 for xi in x]

    result = await e7_engine.run_correlation(
        session, x, y,
        method="PEARSON",
        series_x_id="sec_A",
        series_y_id="sec_B",
    )

    assert "correlation_id" in result
    assert result["method"] == "PEARSON"
    assert result["coefficient"] == pytest.approx(1.0, abs=1e-4)
    assert result["n_observations"] == 50

    # Verify persistence
    row = await session.execute(
        select(CorrelationResult).where(
            CorrelationResult.correlation_id == result["correlation_id"]
        )
    )
    corr = row.scalar_one_or_none()
    assert corr is not None
    assert corr.series_x_id == "sec_A"
    assert corr.series_y_id == "sec_B"
    assert float(corr.coefficient) == pytest.approx(1.0, abs=1e-4)
    assert corr.data_quality == "COMPLETE"


# ===========================================================================
# 16. run_stationarity ADF on stationary series
# ===========================================================================

@pytest.mark.asyncio
async def test_run_stationarity_adf(session: AsyncSession, e7_engine):
    """A stationary series should be flagged as stationary by the ADF test
    (or the pure-Python fallback which checks var_diff / var_level < 0.1)."""
    # Large-amplitude, very slow oscillation: high level variance but tiny
    # first-difference variance, satisfying the fallback heuristic.
    series = [100.0 * math.sin(i * 0.01) for i in range(200)]

    result = await e7_engine.run_stationarity(
        session, series,
        test_type="ADF",
        series_name="test_stationary",
    )

    assert result is not None
    assert "test_id" in result
    assert "test_statistic" in result
    assert "p_value" in result
    assert result["is_significant"] is True

    # Verify persistence
    row = await session.execute(
        select(TimeSeriesTestResult).where(
            TimeSeriesTestResult.test_id == result["test_id"]
        )
    )
    ts = row.scalar_one_or_none()
    assert ts is not None
    assert ts.test_type == "ADF"
    assert ts.series_name == "test_stationary"
    assert ts.is_significant is True


# ===========================================================================
# 17. run_cointegration on two cointegrated series
# ===========================================================================

@pytest.mark.asyncio
async def test_run_cointegration(session: AsyncSession, e7_engine):
    """Two cointegrated series (y ~ 2*x) should be detected as cointegrated.
    The fallback runs OLS on (x,y), then tests residuals via _run_adf which
    checks var_diff / var_level < 0.1."""
    n = 200
    # Common non-stationary trend (steady drift)
    trend = []
    val = 100.0
    for i in range(n):
        val += 0.5
        trend.append(val)

    # series_x follows the trend exactly
    series_x = list(trend)
    # series_y = 2*trend + constant + slowly drifting residual
    # The slow sinusoidal residual ensures var_diff / var_level < 0.1
    series_y = [2.0 * t + 50.0 + 5.0 * math.sin(i * 0.02) for i, t in enumerate(trend)]

    result = await e7_engine.run_cointegration(
        session, series_x, series_y,
        series_x_id="asset_A",
        series_y_id="asset_B",
    )

    assert result is not None
    assert "test_id" in result
    assert "test_statistic" in result
    assert "p_value" in result
    assert "hedge_ratio" in result
    assert result["is_cointegrated"] is True
    # Hedge ratio should be close to 2.0 (the true coefficient)
    assert result["hedge_ratio"] == pytest.approx(2.0, abs=0.5)

    # Verify persistence
    row = await session.execute(
        select(TimeSeriesTestResult).where(
            TimeSeriesTestResult.test_id == result["test_id"]
        )
    )
    ts = row.scalar_one_or_none()
    assert ts is not None
    assert ts.test_type == "COINTEGRATION"
    assert ts.is_significant is True


# ===========================================================================
# 18. Rolling regression window
# ===========================================================================

@pytest.mark.asyncio
async def test_rolling_regression_window(e7_engine):
    """Rolling regression with window=10 on 30 points should produce 21
    result entries (indices 9..29)."""
    x = [float(i) for i in range(30)]
    y = [2.0 * xi + 1.0 for xi in x]

    points = await e7_engine.run_rolling_regression(x, y, window=10)

    assert len(points) == 21
    # Each point should have the expected keys
    for pt in points:
        assert "index" in pt
        assert "beta" in pt
        assert "alpha" in pt
        assert "r_squared" in pt

    # For perfect linear data, every window should recover beta ~ 2.0
    for pt in points:
        assert pt["beta"] == pytest.approx(2.0, abs=1e-6)
        assert pt["alpha"] == pytest.approx(1.0, abs=1e-6)
        assert pt["r_squared"] == pytest.approx(1.0, abs=1e-6)

    # Check that indices are sequential from window-1 to n-1
    assert points[0]["index"] == 9
    assert points[-1]["index"] == 29
