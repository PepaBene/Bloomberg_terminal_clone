"""Tests for the analytics engine base framework."""

from datetime import date
from uuid import uuid4

import pytest

from src.engines.base import EngineOutput, safe_divide, pct_change, cagr, make_input


# ---------------------------------------------------------------------------
# EngineOutput dataclass
# ---------------------------------------------------------------------------

def test_engine_output_defaults():
    """EngineOutput should populate defaults correctly."""
    eo = EngineOutput(
        security_id=uuid4(),
        entity_id=uuid4(),
        engine_id="E1",
        metric_name="gross_margin",
        metric_category="PROFITABILITY",
        value=0.45,
    )
    assert eo.unit == "RATIO"
    assert eo.period == "LATEST"
    assert eo.data_quality == "COMPLETE"
    assert eo.calculation_version == "1.0"
    assert eo.as_of_date == date.today()
    assert eo.inputs is None


def test_engine_output_with_inputs():
    """EngineOutput should carry lineage inputs."""
    inputs = [{"name": "revenue", "source": "pillar_1.fundamentals", "value": 1000}]
    eo = EngineOutput(
        security_id=uuid4(),
        entity_id=uuid4(),
        engine_id="E1",
        metric_name="net_margin",
        metric_category="PROFITABILITY",
        value=0.12,
        inputs=inputs,
    )
    assert eo.inputs == inputs
    assert len(eo.inputs) == 1


def test_engine_output_none_value():
    """EngineOutput value=None should pair with INSUFFICIENT_DATA quality."""
    eo = EngineOutput(
        security_id=uuid4(),
        entity_id=uuid4(),
        engine_id="E1",
        metric_name="pe_trailing",
        metric_category="VALUATION",
        value=None,
        data_quality="INSUFFICIENT_DATA",
    )
    assert eo.value is None
    assert eo.data_quality == "INSUFFICIENT_DATA"


# ---------------------------------------------------------------------------
# safe_divide
# ---------------------------------------------------------------------------

def test_safe_divide_normal():
    assert safe_divide(10.0, 2.0) == 5.0


def test_safe_divide_zero_denominator():
    assert safe_divide(10.0, 0.0) is None


def test_safe_divide_none_numerator():
    assert safe_divide(None, 5.0) is None


def test_safe_divide_none_denominator():
    assert safe_divide(5.0, None) is None


def test_safe_divide_negative_denominator_allowed():
    result = safe_divide(10.0, -2.0, allow_negative_denominator=True)
    assert result == -5.0


def test_safe_divide_negative_denominator_disallowed():
    result = safe_divide(10.0, -2.0, allow_negative_denominator=False)
    assert result is None


# ---------------------------------------------------------------------------
# pct_change
# ---------------------------------------------------------------------------

def test_pct_change_positive():
    assert pct_change(110.0, 100.0) == pytest.approx(0.1)


def test_pct_change_negative():
    assert pct_change(90.0, 100.0) == pytest.approx(-0.1)


def test_pct_change_from_negative():
    # (50 - (-100)) / |-100| = 1.5
    assert pct_change(50.0, -100.0) == pytest.approx(1.5)


def test_pct_change_zero_prior():
    assert pct_change(100.0, 0.0) is None


def test_pct_change_none():
    assert pct_change(None, 100.0) is None
    assert pct_change(100.0, None) is None


# ---------------------------------------------------------------------------
# cagr
# ---------------------------------------------------------------------------

def test_cagr_normal():
    # 100 → 200 in 3 years = 2^(1/3) - 1 ≈ 0.2599
    result = cagr(200.0, 100.0, 3)
    assert result == pytest.approx(0.2599, abs=0.001)


def test_cagr_zero_start():
    assert cagr(200.0, 0.0, 3) is None


def test_cagr_negative_start():
    assert cagr(200.0, -50.0, 3) is None


def test_cagr_zero_years():
    assert cagr(200.0, 100.0, 0) is None


def test_cagr_none():
    assert cagr(None, 100.0, 3) is None


# ---------------------------------------------------------------------------
# make_input
# ---------------------------------------------------------------------------

def test_make_input():
    inp = make_input("revenue", "pillar_1.fundamentals.income_statement", 42000000.0, "TTM")
    assert inp["name"] == "revenue"
    assert inp["source"] == "pillar_1.fundamentals.income_statement"
    assert inp["value"] == 42000000.0
    assert inp["period"] == "TTM"
