"""Tests for E4 FI Extension: Fixed Income Bond Screening."""

from datetime import date

import pytest

from src.engines.e4_fi_screening import (
    BondScreenFilter,
    apply_bond_filters,
    rank_bonds,
    rating_to_numeric,
)


# ---------------------------------------------------------------------------
# Sample bond data
# ---------------------------------------------------------------------------

def _sample_bonds() -> list[dict]:
    """Return a set of representative bond dicts for testing."""
    return [
        {
            "cusip": "ABC123456",
            "name": "Alpha Corp 5% 2030",
            "coupon_rate": 5.0,
            "maturity_date": date(2030, 6, 15),
            "spread_bps": 150,
            "yield_to_worst": 5.25,
            "yield_to_maturity": 5.50,
            "liquidity_score": 8,
            "rating_numeric": 6,  # A
            "seniority": "SENIOR_UNSECURED",
            "is_callable": True,
            "is_investment_grade": True,
            "outstanding_amount": 500_000_000,
        },
        {
            "cusip": "DEF789012",
            "name": "Beta Inc 7% 2028",
            "coupon_rate": 7.0,
            "maturity_date": date(2028, 3, 1),
            "spread_bps": 350,
            "yield_to_worst": 7.80,
            "yield_to_maturity": 8.00,
            "liquidity_score": 5,
            "rating_numeric": 13,  # BB-
            "seniority": "SENIOR_SECURED",
            "is_callable": False,
            "is_investment_grade": False,
            "outstanding_amount": 250_000_000,
        },
        {
            "cusip": "GHI345678",
            "name": "Gamma LLC 4% 2035",
            "coupon_rate": 4.0,
            "maturity_date": date(2035, 12, 1),
            "spread_bps": 90,
            "yield_to_worst": 4.10,
            "yield_to_maturity": 4.20,
            "liquidity_score": 9,
            "rating_numeric": 3,  # AA
            "seniority": "SENIOR_UNSECURED",
            "is_callable": False,
            "is_investment_grade": True,
            "outstanding_amount": 1_000_000_000,
        },
        {
            "cusip": "JKL901234",
            "name": "Delta Corp 8.5% 2027",
            "coupon_rate": 8.5,
            "maturity_date": date(2027, 9, 15),
            "spread_bps": 500,
            "yield_to_worst": 9.50,
            "yield_to_maturity": 9.75,
            "liquidity_score": 3,
            "rating_numeric": 16,  # B-
            "seniority": "SUBORDINATED",
            "is_callable": True,
            "is_investment_grade": False,
            "outstanding_amount": 100_000_000,
        },
    ]


# ---------------------------------------------------------------------------
# rating_to_numeric
# ---------------------------------------------------------------------------


def test_rating_to_numeric_known_ratings():
    """Well-known ratings map to correct numeric values."""
    assert rating_to_numeric("AAA") == 1
    assert rating_to_numeric("BBB-") == 10
    assert rating_to_numeric("D") == 22


def test_rating_to_numeric_case_insensitive():
    """Rating lookup is case-insensitive."""
    assert rating_to_numeric("bbb+") == 8
    assert rating_to_numeric("Aa-") == 4


def test_rating_to_numeric_none_and_unknown():
    """None or unknown rating returns None."""
    assert rating_to_numeric(None) is None
    assert rating_to_numeric("XYZ") is None


# ---------------------------------------------------------------------------
# Filter by spread
# ---------------------------------------------------------------------------


def test_filter_spread_gte():
    """Filter bonds with spread >= 200bps should return HY names only."""
    bonds = _sample_bonds()
    filters = [BondScreenFilter(field="spread_bps", op="GTE", value=200)]
    result = apply_bond_filters(bonds, filters)
    assert len(result) == 2
    cusips = {b["cusip"] for b in result}
    assert "DEF789012" in cusips
    assert "JKL901234" in cusips


def test_filter_spread_between():
    """BETWEEN filter for spread 100-400 should match Alpha and Beta."""
    bonds = _sample_bonds()
    filters = [BondScreenFilter(field="spread_bps", op="BETWEEN", value=100, value2=400)]
    result = apply_bond_filters(bonds, filters)
    assert len(result) == 2
    cusips = {b["cusip"] for b in result}
    assert "ABC123456" in cusips
    assert "DEF789012" in cusips


# ---------------------------------------------------------------------------
# Filter by rating
# ---------------------------------------------------------------------------


def test_filter_rating_investment_grade():
    """Filter for IG bonds (rating_numeric <= 10)."""
    bonds = _sample_bonds()
    filters = [BondScreenFilter(field="rating_numeric", op="LTE", value=10)]
    result = apply_bond_filters(bonds, filters)
    assert len(result) == 2
    assert all(b["is_investment_grade"] for b in result)


# ---------------------------------------------------------------------------
# Filter by maturity date
# ---------------------------------------------------------------------------


def test_filter_maturity_after_2030():
    """Bonds maturing after 2030 should only include Gamma 2035."""
    bonds = _sample_bonds()
    filters = [BondScreenFilter(field="maturity_date", op="GT", value="2030-06-15")]
    result = apply_bond_filters(bonds, filters)
    assert len(result) == 1
    assert result[0]["cusip"] == "GHI345678"


# ---------------------------------------------------------------------------
# Filter by seniority (EQ, case-insensitive string)
# ---------------------------------------------------------------------------


def test_filter_seniority_eq():
    """EQ filter on seniority for SENIOR_UNSECURED."""
    bonds = _sample_bonds()
    filters = [BondScreenFilter(field="seniority", op="EQ", value="SENIOR_UNSECURED")]
    result = apply_bond_filters(bonds, filters)
    assert len(result) == 2
    cusips = {b["cusip"] for b in result}
    assert "ABC123456" in cusips
    assert "GHI345678" in cusips


# ---------------------------------------------------------------------------
# Multiple filters (AND logic)
# ---------------------------------------------------------------------------


def test_multiple_filters_and_logic():
    """Multiple filters use AND logic: IG + spread >= 100 -> only Alpha."""
    bonds = _sample_bonds()
    filters = [
        BondScreenFilter(field="is_investment_grade", op="EQ", value=True),
        BondScreenFilter(field="spread_bps", op="GTE", value=100),
    ]
    result = apply_bond_filters(bonds, filters)
    assert len(result) == 1
    assert result[0]["cusip"] == "ABC123456"


# ---------------------------------------------------------------------------
# Ranking and limiting
# ---------------------------------------------------------------------------


def test_rank_by_spread_descending():
    """Ranking by spread descending puts highest-spread bond first."""
    bonds = _sample_bonds()
    ranked = rank_bonds(bonds, sort_field="spread_bps", ascending=False, limit=10)
    assert ranked[0]["cusip"] == "JKL901234"  # 500bps
    assert ranked[-1]["cusip"] == "GHI345678"  # 90bps


def test_rank_limit():
    """Limit caps the number of returned bonds."""
    bonds = _sample_bonds()
    ranked = rank_bonds(bonds, sort_field="spread_bps", ascending=False, limit=2)
    assert len(ranked) == 2


def test_rank_ascending():
    """Ascending sort puts lowest-spread bond first."""
    bonds = _sample_bonds()
    ranked = rank_bonds(bonds, sort_field="spread_bps", ascending=True, limit=10)
    assert ranked[0]["cusip"] == "GHI345678"  # 90bps


def test_rank_handles_none_values():
    """Bonds with None for the sort field are placed at the end."""
    bonds = _sample_bonds()
    bonds[0]["spread_bps"] = None  # Alpha -> None
    ranked = rank_bonds(bonds, sort_field="spread_bps", ascending=False, limit=10)
    # Alpha should be last
    assert ranked[-1]["cusip"] == "ABC123456"
