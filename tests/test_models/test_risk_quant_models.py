"""Tests for risk and quantitative analytics models."""

import uuid
from datetime import date, datetime, timezone

import pytest
import pytest_asyncio
from sqlalchemy import select

from src.models.risk import FactorExposure, StressTestResult, VaRResult
from src.models.quant import CorrelationResult, RegressionResult, TimeSeriesTestResult


@pytest.mark.asyncio
async def test_var_result_crud(session):
    """VaRResult can be created and queried."""
    sid = uuid.uuid4()
    var = VaRResult(
        security_id=sid,
        calculation_date=date(2026, 3, 20),
        method="HISTORICAL",
        confidence_level=0.95,
        holding_period_days=1,
        var_value=0.023,
        expected_shortfall=0.031,
        lookback_days=252,
        annualized_volatility=0.25,
        daily_mean_return=0.0004,
        daily_std_return=0.015,
        skewness=-0.3,
        kurtosis=4.1,
        data_quality="COMPLETE",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    session.add(var)
    await session.flush()

    result = await session.execute(
        select(VaRResult).where(VaRResult.security_id == sid)
    )
    row = result.scalar_one()
    assert float(row.var_value) == pytest.approx(0.023)
    assert float(row.confidence_level) == pytest.approx(0.95)
    assert row.method == "HISTORICAL"
    assert row.holding_period_days == 1


@pytest.mark.asyncio
async def test_stress_test_result_crud(session):
    """StressTestResult can be created with JSONB params."""
    sid = uuid.uuid4()
    stress = StressTestResult(
        security_id=sid,
        calculation_date=date(2026, 3, 20),
        scenario_type="HISTORICAL",
        scenario_name="GFC_2008",
        scenario_params={"start": "2008-09-01", "end": "2009-03-31"},
        pnl_percent=-0.45,
        max_drawdown=-0.55,
        worst_day=-0.09,
        best_day=0.11,
        data_quality="COMPLETE",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    session.add(stress)
    await session.flush()

    result = await session.execute(
        select(StressTestResult).where(StressTestResult.security_id == sid)
    )
    row = result.scalar_one()
    assert row.scenario_name == "GFC_2008"
    assert float(row.pnl_percent) == pytest.approx(-0.45)
    assert row.scenario_params["start"] == "2008-09-01"


@pytest.mark.asyncio
async def test_factor_exposure_crud(session):
    """FactorExposure can be created and queried."""
    sid = uuid.uuid4()
    fe = FactorExposure(
        security_id=sid,
        calculation_date=date(2026, 3, 20),
        factor_name="VALUE",
        z_score=1.5,
        raw_value=0.85,
        percentile_rank=88.0,
        data_quality="COMPLETE",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    session.add(fe)
    await session.flush()

    result = await session.execute(
        select(FactorExposure).where(FactorExposure.security_id == sid)
    )
    row = result.scalar_one()
    assert row.factor_name == "VALUE"
    assert float(row.z_score) == pytest.approx(1.5)


@pytest.mark.asyncio
async def test_regression_result_crud(session):
    """RegressionResult stores coefficients in JSONB."""
    sid = uuid.uuid4()
    reg = RegressionResult(
        security_id=sid,
        calculation_date=date(2026, 3, 20),
        method="OLS",
        dependent_var="daily_return",
        independent_vars=["market_return"],
        coefficients={"intercept": 0.001, "market_return": 1.15},
        std_errors={"intercept": 0.0005, "market_return": 0.08},
        r_squared=0.65,
        adj_r_squared=0.649,
        f_statistic=120.5,
        f_p_value=0.00001,
        n_observations=252,
        data_quality="COMPLETE",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    session.add(reg)
    await session.flush()

    result = await session.execute(
        select(RegressionResult).where(RegressionResult.security_id == sid)
    )
    row = result.scalar_one()
    assert row.coefficients["market_return"] == pytest.approx(1.15)
    assert float(row.r_squared) == pytest.approx(0.65)
    assert row.n_observations == 252


@pytest.mark.asyncio
async def test_correlation_result_crud(session):
    """CorrelationResult round-trips correctly."""
    corr = CorrelationResult(
        calculation_date=date(2026, 3, 20),
        method="PEARSON",
        series_x_id="sec_aaa",
        series_y_id="sec_bbb",
        series_x_label="Apple",
        series_y_label="Microsoft",
        coefficient=0.78,
        p_value=0.0001,
        n_observations=252,
        data_quality="COMPLETE",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    session.add(corr)
    await session.flush()

    result = await session.execute(
        select(CorrelationResult).where(CorrelationResult.series_x_id == "sec_aaa")
    )
    row = result.scalar_one()
    assert float(row.coefficient) == pytest.approx(0.78)
    assert row.method == "PEARSON"


@pytest.mark.asyncio
async def test_time_series_test_result_crud(session):
    """TimeSeriesTestResult stores test outputs and critical values."""
    sid = uuid.uuid4()
    ts = TimeSeriesTestResult(
        security_id=sid,
        calculation_date=date(2026, 3, 20),
        test_type="ADF",
        series_name="daily_return",
        test_statistic=-3.85,
        p_value=0.002,
        critical_values={"1%": -3.43, "5%": -2.86, "10%": -2.57},
        is_significant=True,
        lags_used=5,
        data_quality="COMPLETE",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    session.add(ts)
    await session.flush()

    result = await session.execute(
        select(TimeSeriesTestResult).where(TimeSeriesTestResult.security_id == sid)
    )
    row = result.scalar_one()
    assert row.test_type == "ADF"
    assert row.is_significant is True
    assert float(row.p_value) == pytest.approx(0.002)
    assert row.critical_values["5%"] == pytest.approx(-2.86)
