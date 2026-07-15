"""Tests for Pillar 4 Phase 2: AttributionResult and ReportRequest models."""

import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from src.models.attribution import AttributionResult, ReportRequest
from src.models.portfolio import Portfolio


# ── Helpers ──────────────────────────────────────────────────────────


async def _seed_portfolio(
    session,
    user_id: str = "test-user",
    portfolio_name: str = "Attr Test Portfolio",
    **kwargs,
) -> Portfolio:
    defaults = {
        "id": uuid.uuid4(),
        "user_id": user_id,
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


async def _seed_attribution(
    session,
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
            }
        ],
        "security_detail": [
            {
                "ticker": "AAPL",
                "weight": 0.10,
                "return": 0.05,
                "contribution": 0.005,
            },
            {
                "ticker": "MSFT",
                "weight": 0.08,
                "return": -0.02,
                "contribution": -0.0016,
            },
        ],
        "factor_detail": [
            {
                "factor": "Momentum",
                "portfolio_exposure": 0.15,
                "benchmark_exposure": 0.10,
                "factor_return": 0.03,
                "contribution": 0.0015,
            }
        ],
    }
    defaults.update(kwargs)
    attr = AttributionResult(**defaults)
    session.add(attr)
    await session.flush()
    return attr


async def _seed_report_request(
    session,
    portfolio_id: uuid.UUID,
    **kwargs,
) -> ReportRequest:
    defaults = {
        "id": uuid.uuid4(),
        "portfolio_id": portfolio_id,
        "report_type": "SUMMARY",
        "format": "json",
        "period_start": date(2025, 1, 1),
        "period_end": date(2025, 6, 30),
        "parameters": {"include_charts": True, "sections": ["performance", "attribution"]},
        "status": "COMPLETED",
        "result_data": {
            "report_type": "SUMMARY",
            "portfolio_name": "Test",
            "nav": 105000.0,
        },
    }
    defaults.update(kwargs)
    rr = ReportRequest(**defaults)
    session.add(rr)
    await session.flush()
    return rr


# ── AttributionResult CRUD ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_attribution_result(session):
    """Create an AttributionResult with all fields."""
    p = await _seed_portfolio(session, portfolio_name="Attr Create")
    attr = await _seed_attribution(session, p.id)
    result = await session.execute(
        select(AttributionResult).where(AttributionResult.id == attr.id)
    )
    fetched = result.scalar_one()
    assert fetched.portfolio_id == p.id
    assert fetched.attribution_type == "BRINSON"
    assert fetched.total_portfolio_return == Decimal("0.02500000")
    assert fetched.total_active_return == Decimal("0.00700000")


@pytest.mark.asyncio
async def test_attribution_unique_constraint(session):
    """Duplicate (portfolio_id, period_start, period_end) raises IntegrityError.

    P4-M-015: the constraint key is the *period*, not attribution_type --
    a BRINSON and a FACTOR attribution for the exact same period are still
    "the result for this period" and should collide, not coexist.
    """
    p = await _seed_portfolio(session, portfolio_name="Attr Unique")
    await _seed_attribution(
        session, p.id,
        attribution_type="BRINSON",
        period_start=date(2025, 7, 1),
        period_end=date(2025, 7, 31),
    )
    session.add(AttributionResult(
        id=uuid.uuid4(),
        portfolio_id=p.id,
        period_start=date(2025, 7, 1),
        period_end=date(2025, 7, 31),
        attribution_type="FACTOR",
    ))
    with pytest.raises(IntegrityError):
        await session.flush()
    await session.rollback()


@pytest.mark.asyncio
async def test_attribution_same_type_different_period_start_allowed(session):
    """Same portfolio_id + attribution_type + period_end but a different
    period_start is NOT a duplicate under the new (portfolio_id,
    period_start, period_end) key -- distinct periods that happen to share
    an end date are legitimately different rows."""
    p = await _seed_portfolio(session, portfolio_name="Attr Period Start Diff")
    await _seed_attribution(
        session, p.id,
        attribution_type="BRINSON",
        period_start=date(2025, 6, 1),
        period_end=date(2025, 8, 31),
    )
    other = AttributionResult(
        id=uuid.uuid4(),
        portfolio_id=p.id,
        period_start=date(2025, 7, 1),
        period_end=date(2025, 8, 31),
        attribution_type="BRINSON",
    )
    session.add(other)
    await session.flush()  # should not raise

    result = await session.execute(
        select(AttributionResult).where(AttributionResult.id == other.id)
    )
    fetched = result.scalar_one()
    assert fetched.period_start == date(2025, 7, 1)


@pytest.mark.asyncio
async def test_attribution_sector_detail_jsonb_roundtrip(session):
    """JSONB sector_detail round-trip."""
    p = await _seed_portfolio(session, portfolio_name="Attr Sector RT")
    sectors = [
        {"sector": "Tech", "allocation_effect": 0.003, "selection_effect": 0.005},
        {"sector": "Health", "allocation_effect": -0.001, "selection_effect": 0.002},
    ]
    attr = await _seed_attribution(
        session, p.id, sector_detail=sectors, period_end=date(2025, 8, 31)
    )
    result = await session.execute(
        select(AttributionResult).where(AttributionResult.id == attr.id)
    )
    fetched = result.scalar_one()
    assert isinstance(fetched.sector_detail, list)
    assert len(fetched.sector_detail) == 2
    assert fetched.sector_detail[0]["sector"] == "Tech"
    assert fetched.sector_detail[1]["sector"] == "Health"


@pytest.mark.asyncio
async def test_attribution_security_detail_jsonb_roundtrip(session):
    """JSONB security_detail round-trip."""
    p = await _seed_portfolio(session, portfolio_name="Attr Security RT")
    securities = [
        {"ticker": "GOOG", "weight": 0.12, "return": 0.06, "contribution": 0.0072},
    ]
    attr = await _seed_attribution(
        session, p.id, security_detail=securities, period_end=date(2025, 9, 30)
    )
    result = await session.execute(
        select(AttributionResult).where(AttributionResult.id == attr.id)
    )
    fetched = result.scalar_one()
    assert isinstance(fetched.security_detail, list)
    assert fetched.security_detail[0]["ticker"] == "GOOG"
    assert fetched.security_detail[0]["contribution"] == 0.0072


@pytest.mark.asyncio
async def test_attribution_factor_detail_jsonb_roundtrip(session):
    """JSONB factor_detail round-trip."""
    p = await _seed_portfolio(session, portfolio_name="Attr Factor RT")
    factors = [
        {"factor": "Value", "portfolio_exposure": 0.20, "factor_return": 0.015, "contribution": 0.003},
        {"factor": "Size", "portfolio_exposure": -0.10, "factor_return": 0.02, "contribution": -0.002},
    ]
    attr = await _seed_attribution(
        session, p.id, factor_detail=factors, period_end=date(2025, 10, 31)
    )
    result = await session.execute(
        select(AttributionResult).where(AttributionResult.id == attr.id)
    )
    fetched = result.scalar_one()
    assert isinstance(fetched.factor_detail, list)
    assert len(fetched.factor_detail) == 2
    assert fetched.factor_detail[0]["factor"] == "Value"
    assert fetched.factor_detail[1]["factor"] == "Size"


@pytest.mark.asyncio
async def test_attribution_update(session):
    """Update existing attribution result."""
    p = await _seed_portfolio(session, portfolio_name="Attr Update")
    attr = await _seed_attribution(session, p.id, period_end=date(2025, 11, 30))
    attr.total_active_return = Decimal("0.01000000")
    attr.residual = Decimal("0.00100000")
    await session.flush()

    result = await session.execute(
        select(AttributionResult).where(AttributionResult.id == attr.id)
    )
    fetched = result.scalar_one()
    assert fetched.total_active_return == Decimal("0.01000000")
    assert fetched.residual == Decimal("0.00100000")


@pytest.mark.asyncio
async def test_attribution_type_factor(session):
    """Create a FACTOR type attribution."""
    p = await _seed_portfolio(session, portfolio_name="Attr Factor Type")
    attr = await _seed_attribution(
        session, p.id, attribution_type="FACTOR", period_end=date(2025, 12, 31)
    )
    result = await session.execute(
        select(AttributionResult).where(AttributionResult.id == attr.id)
    )
    fetched = result.scalar_one()
    assert fetched.attribution_type == "FACTOR"


# ── ReportRequest CRUD ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_report_request(session):
    """Create a ReportRequest with all fields."""
    p = await _seed_portfolio(session, portfolio_name="Report Create")
    rr = await _seed_report_request(session, p.id)
    result = await session.execute(
        select(ReportRequest).where(ReportRequest.id == rr.id)
    )
    fetched = result.scalar_one()
    assert fetched.portfolio_id == p.id
    assert fetched.report_type == "SUMMARY"
    assert fetched.format == "json"
    assert fetched.status == "COMPLETED"


@pytest.mark.asyncio
async def test_report_request_jsonb_parameters_roundtrip(session):
    """JSONB parameters round-trip."""
    p = await _seed_portfolio(session, portfolio_name="Report Params RT")
    params = {"include_benchmark": True, "custom_period": "Q2_2025"}
    rr = await _seed_report_request(session, p.id, parameters=params)
    result = await session.execute(
        select(ReportRequest).where(ReportRequest.id == rr.id)
    )
    fetched = result.scalar_one()
    assert fetched.parameters == params
    assert fetched.parameters["include_benchmark"] is True


@pytest.mark.asyncio
async def test_report_request_jsonb_result_data_roundtrip(session):
    """JSONB result_data round-trip."""
    p = await _seed_portfolio(session, portfolio_name="Report Result RT")
    result_data = {
        "sections": ["summary", "performance", "attribution"],
        "nav": 112345.67,
        "returns": {"mtd": 0.015, "ytd": 0.08},
    }
    rr = await _seed_report_request(session, p.id, result_data=result_data)
    result = await session.execute(
        select(ReportRequest).where(ReportRequest.id == rr.id)
    )
    fetched = result.scalar_one()
    assert fetched.result_data == result_data
    assert fetched.result_data["nav"] == 112345.67
    assert fetched.result_data["returns"]["ytd"] == 0.08
