"""Tests for E14 Issuer FI Profile Engine."""

from datetime import date

import pytest

from src.engines.e14_issuer_profile import (
    SENIORITY_ORDER,
    build_debt_stack,
    compute_debt_maturity_profile,
    compute_maturity_wall,
    compute_weighted_avg_cost_of_debt,
)


# ── Maturity Wall Tests ──────────────────────────────────────────────


def test_maturity_wall_5_bonds_across_3_years():
    """5 bonds maturing across 3 different years within the forward window."""
    ref = date(2025, 1, 1)
    bonds = [
        {"maturity_date": date(2025, 6, 15), "outstanding_amount": 500.0, "cusip": "A001"},
        {"maturity_date": date(2025, 12, 1), "outstanding_amount": 300.0, "cusip": "A002"},
        {"maturity_date": date(2026, 3, 15), "outstanding_amount": 200.0, "cusip": "A003"},
        {"maturity_date": date(2027, 6, 15), "outstanding_amount": 400.0, "cusip": "A004"},
        {"maturity_date": date(2027, 9, 1), "outstanding_amount": 600.0, "cusip": "A005"},
    ]
    wall = compute_maturity_wall(bonds, reference_date=ref, years_forward=5)
    assert len(wall) == 5  # 2025, 2026, 2027, 2028, 2029

    # 2025: 500 + 300 = 800
    y2025 = next(item for item in wall if item["year"] == 2025)
    assert y2025["amount_maturing"] == 800.0
    assert y2025["bond_count"] == 2
    assert set(y2025["cusips"]) == {"A001", "A002"}

    # 2026: 200
    y2026 = next(item for item in wall if item["year"] == 2026)
    assert y2026["amount_maturing"] == 200.0
    assert y2026["bond_count"] == 1

    # 2027: 400 + 600 = 1000
    y2027 = next(item for item in wall if item["year"] == 2027)
    assert y2027["amount_maturing"] == 1000.0
    assert y2027["bond_count"] == 2

    # 2028, 2029: 0
    y2028 = next(item for item in wall if item["year"] == 2028)
    assert y2028["amount_maturing"] == 0.0
    assert y2028["bond_count"] == 0


def test_maturity_wall_empty_list():
    """Empty bond list returns empty maturity wall."""
    wall = compute_maturity_wall([], reference_date=date(2025, 1, 1))
    assert wall == []


def test_maturity_wall_all_same_year():
    """All bonds maturing in same year."""
    ref = date(2025, 1, 1)
    bonds = [
        {"maturity_date": date(2026, 3, 15), "outstanding_amount": 100.0, "cusip": "B001"},
        {"maturity_date": date(2026, 6, 15), "outstanding_amount": 200.0, "cusip": "B002"},
        {"maturity_date": date(2026, 9, 15), "outstanding_amount": 300.0, "cusip": "B003"},
    ]
    wall = compute_maturity_wall(bonds, reference_date=ref, years_forward=3)
    y2025 = next(item for item in wall if item["year"] == 2025)
    y2026 = next(item for item in wall if item["year"] == 2026)
    y2027 = next(item for item in wall if item["year"] == 2027)
    assert y2025["amount_maturing"] == 0.0
    assert y2026["amount_maturing"] == 600.0
    assert y2026["bond_count"] == 3
    assert y2027["amount_maturing"] == 0.0


def test_maturity_wall_pct_of_total():
    """Percentages should sum to total of included bonds."""
    ref = date(2025, 1, 1)
    bonds = [
        {"maturity_date": date(2025, 6, 15), "outstanding_amount": 500.0, "cusip": "C001"},
        {"maturity_date": date(2026, 6, 15), "outstanding_amount": 500.0, "cusip": "C002"},
    ]
    wall = compute_maturity_wall(bonds, reference_date=ref, years_forward=5)
    y2025 = next(item for item in wall if item["year"] == 2025)
    y2026 = next(item for item in wall if item["year"] == 2026)
    assert y2025["pct_of_total"] == pytest.approx(50.0, abs=0.1)
    assert y2026["pct_of_total"] == pytest.approx(50.0, abs=0.1)


def test_maturity_wall_bonds_outside_window_excluded():
    """Bonds maturing outside the forward window are excluded from buckets."""
    ref = date(2025, 1, 1)
    bonds = [
        {"maturity_date": date(2025, 6, 15), "outstanding_amount": 100.0, "cusip": "D001"},
        {"maturity_date": date(2035, 6, 15), "outstanding_amount": 900.0, "cusip": "D002"},
    ]
    wall = compute_maturity_wall(bonds, reference_date=ref, years_forward=3)
    total_in_wall = sum(item["amount_maturing"] for item in wall)
    assert total_in_wall == 100.0  # only the 2025 bond


# ── Debt Stack Tests ─────────────────────────────────────────────────


def test_debt_stack_multiple_seniorities():
    """Multiple seniority levels should be sorted correctly."""
    bonds = [
        {"seniority": "SUBORDINATED", "outstanding_amount": 200.0, "coupon_rate": 0.06, "maturity_date": date(2030, 1, 1), "cusip": "E001"},
        {"seniority": "SENIOR_SECURED", "outstanding_amount": 500.0, "coupon_rate": 0.04, "maturity_date": date(2028, 1, 1), "cusip": "E002"},
        {"seniority": "SENIOR_UNSECURED", "outstanding_amount": 300.0, "coupon_rate": 0.05, "maturity_date": date(2029, 1, 1), "cusip": "E003"},
    ]
    stack = build_debt_stack(bonds)
    assert len(stack) == 3
    # Ordered: SENIOR_SECURED, SENIOR_UNSECURED, SUBORDINATED
    assert stack[0]["seniority"] == "SENIOR_SECURED"
    assert stack[1]["seniority"] == "SENIOR_UNSECURED"
    assert stack[2]["seniority"] == "SUBORDINATED"
    assert stack[0]["total_outstanding"] == 500.0
    assert stack[2]["total_outstanding"] == 200.0


def test_debt_stack_single_seniority():
    """Single seniority returns one group."""
    bonds = [
        {"seniority": "SENIOR_UNSECURED", "outstanding_amount": 100.0, "coupon_rate": 0.05, "maturity_date": date(2030, 1, 1), "cusip": "F001"},
        {"seniority": "SENIOR_UNSECURED", "outstanding_amount": 200.0, "coupon_rate": 0.06, "maturity_date": date(2031, 1, 1), "cusip": "F002"},
    ]
    stack = build_debt_stack(bonds)
    assert len(stack) == 1
    assert stack[0]["seniority"] == "SENIOR_UNSECURED"
    assert stack[0]["total_outstanding"] == 300.0
    assert stack[0]["bond_count"] == 2
    assert stack[0]["avg_coupon"] == pytest.approx(0.055, abs=0.001)


def test_debt_stack_empty():
    """Empty bond list returns empty debt stack."""
    stack = build_debt_stack([])
    assert stack == []


def test_debt_stack_pct_of_total():
    """Percentages should sum to 100%."""
    bonds = [
        {"seniority": "SENIOR_SECURED", "outstanding_amount": 600.0, "coupon_rate": 0.04, "maturity_date": date(2030, 1, 1), "cusip": "G001"},
        {"seniority": "SUBORDINATED", "outstanding_amount": 400.0, "coupon_rate": 0.07, "maturity_date": date(2032, 1, 1), "cusip": "G002"},
    ]
    stack = build_debt_stack(bonds)
    total_pct = sum(item["pct_of_total"] for item in stack)
    assert total_pct == pytest.approx(100.0, abs=0.1)


# ── Weighted Average Cost of Debt Tests ──────────────────────────────


def test_weighted_avg_cost_various_coupons():
    """Weighted average of different coupon rates."""
    bonds = [
        {"coupon_rate": 0.04, "outstanding_amount": 500.0},
        {"coupon_rate": 0.06, "outstanding_amount": 500.0},
    ]
    result = compute_weighted_avg_cost_of_debt(bonds)
    # (0.04*500 + 0.06*500) / 1000 = 0.05
    assert result == pytest.approx(0.05, abs=1e-6)


def test_weighted_avg_cost_single_bond():
    """Single bond returns its own coupon rate."""
    bonds = [{"coupon_rate": 0.045, "outstanding_amount": 1000.0}]
    result = compute_weighted_avg_cost_of_debt(bonds)
    assert result == pytest.approx(0.045, abs=1e-6)


def test_weighted_avg_cost_empty():
    """Empty list returns 0."""
    assert compute_weighted_avg_cost_of_debt([]) == 0.0


def test_weighted_avg_cost_weighted_by_amount():
    """Larger issue should dominate the weighted average."""
    bonds = [
        {"coupon_rate": 0.03, "outstanding_amount": 900.0},
        {"coupon_rate": 0.09, "outstanding_amount": 100.0},
    ]
    result = compute_weighted_avg_cost_of_debt(bonds)
    # (0.03*900 + 0.09*100) / 1000 = (27 + 9) / 1000 = 0.036
    assert result == pytest.approx(0.036, abs=1e-6)


# ── Debt Maturity Profile Tests ──────────────────────────────────────


def test_maturity_profile_statistics():
    """Verify all maturity profile statistics."""
    ref = date(2025, 1, 1)
    bonds = [
        {"maturity_date": date(2027, 1, 1), "outstanding_amount": 500.0},   # ~2 years
        {"maturity_date": date(2030, 1, 1), "outstanding_amount": 300.0},   # ~5 years
        {"maturity_date": date(2035, 1, 1), "outstanding_amount": 200.0},   # ~10 years
    ]
    profile = compute_debt_maturity_profile(bonds, reference_date=ref)

    assert profile["bond_count"] == 3
    assert profile["total_outstanding"] == 1000.0
    assert profile["shortest_maturity_years"] == pytest.approx(2.0, abs=0.1)
    assert profile["longest_maturity_years"] == pytest.approx(10.0, abs=0.1)
    # avg = (2 + 5 + 10) / 3 = 5.67
    assert profile["avg_maturity_years"] == pytest.approx(5.67, abs=0.2)
    # weighted avg = (2*500 + 5*300 + 10*200) / 1000 = (1000+1500+2000)/1000 = 4.5
    assert profile["weighted_avg_maturity_years"] == pytest.approx(4.5, abs=0.2)


def test_maturity_profile_empty():
    """Empty bond list returns zeroed profile."""
    profile = compute_debt_maturity_profile([])
    assert profile["bond_count"] == 0
    assert profile["total_outstanding"] == 0.0
    assert profile["avg_maturity_years"] == 0.0
