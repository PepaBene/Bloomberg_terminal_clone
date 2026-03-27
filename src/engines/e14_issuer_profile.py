"""E14 Issuer FI Profile Engine — Maturity Wall, Debt Stack, Refinancing Risk, Weighted Cost.

All functions are pure computation — no database access.
"""

from __future__ import annotations

from datetime import date


# Seniority ordering for debt stack
SENIORITY_ORDER = [
    "SENIOR_SECURED",
    "SENIOR_UNSECURED",
    "SENIOR_SUBORDINATED",
    "SUBORDINATED",
    "JUNIOR_SUBORDINATED",
]


def compute_maturity_wall(
    bonds: list[dict],
    reference_date: date | None = None,
    years_forward: int = 5,
) -> list[dict]:
    """Compute maturity wall — debt maturing by year.

    bonds: list of {maturity_date: date, outstanding_amount: float, cusip: str}

    Returns list of {
        year: int,
        amount_maturing: float,
        pct_of_total: float,
        bond_count: int,
        cusips: list[str]
    } for each year in the forward window.
    """
    ref = reference_date or date.today()
    if not bonds:
        return []

    total_outstanding = sum(b.get("outstanding_amount", 0.0) for b in bonds)

    # Build year buckets for the forward window
    start_year = ref.year
    end_year = start_year + years_forward  # exclusive

    year_buckets: dict[int, dict] = {}
    for yr in range(start_year, end_year):
        year_buckets[yr] = {
            "year": yr,
            "amount_maturing": 0.0,
            "bond_count": 0,
            "cusips": [],
        }

    for bond in bonds:
        mat_date = bond.get("maturity_date")
        if mat_date is None:
            continue
        mat_year = mat_date.year
        if mat_year < start_year or mat_year >= end_year:
            continue
        # Only include bonds maturing on or after the reference date
        if mat_date < ref:
            continue

        amount = bond.get("outstanding_amount", 0.0)
        cusip = bond.get("cusip", "")

        year_buckets[mat_year]["amount_maturing"] += amount
        year_buckets[mat_year]["bond_count"] += 1
        year_buckets[mat_year]["cusips"].append(cusip)

    result = []
    for yr in range(start_year, end_year):
        bucket = year_buckets[yr]
        pct = (bucket["amount_maturing"] / total_outstanding * 100.0) if total_outstanding > 0 else 0.0
        result.append({
            "year": bucket["year"],
            "amount_maturing": round(bucket["amount_maturing"], 2),
            "pct_of_total": round(pct, 4),
            "bond_count": bucket["bond_count"],
            "cusips": bucket["cusips"],
        })

    return result


def build_debt_stack(bonds: list[dict]) -> list[dict]:
    """Build debt stack by seniority.

    bonds: list of {seniority: str, outstanding_amount: float, coupon_rate: float,
                    maturity_date: date, cusip: str}

    Returns list of {
        seniority: str,
        total_outstanding: float,
        pct_of_total: float,
        avg_coupon: float,
        avg_maturity_years: float (from today),
        bond_count: int,
    } sorted by seniority priority (SENIOR_SECURED first).
    """
    if not bonds:
        return []

    total_outstanding = sum(b.get("outstanding_amount", 0.0) for b in bonds)
    today = date.today()

    # Group by seniority
    groups: dict[str, dict] = {}
    for bond in bonds:
        sen = bond.get("seniority", "UNKNOWN")
        amount = bond.get("outstanding_amount", 0.0)
        coupon = bond.get("coupon_rate", 0.0)
        mat_date = bond.get("maturity_date")

        if sen not in groups:
            groups[sen] = {
                "seniority": sen,
                "total_outstanding": 0.0,
                "coupon_sum": 0.0,
                "maturity_years_sum": 0.0,
                "bond_count": 0,
            }

        groups[sen]["total_outstanding"] += amount
        groups[sen]["coupon_sum"] += coupon
        groups[sen]["bond_count"] += 1

        if mat_date is not None:
            years = (mat_date - today).days / 365.25
            groups[sen]["maturity_years_sum"] += max(years, 0.0)

    # Sort by seniority order
    def _sort_key(item: dict) -> int:
        sen = item["seniority"]
        if sen in SENIORITY_ORDER:
            return SENIORITY_ORDER.index(sen)
        return len(SENIORITY_ORDER)  # unknowns go last

    result = []
    for group in sorted(groups.values(), key=_sort_key):
        count = group["bond_count"]
        pct = (group["total_outstanding"] / total_outstanding * 100.0) if total_outstanding > 0 else 0.0
        avg_coupon = group["coupon_sum"] / count if count > 0 else 0.0
        avg_mat = group["maturity_years_sum"] / count if count > 0 else 0.0
        result.append({
            "seniority": group["seniority"],
            "total_outstanding": round(group["total_outstanding"], 2),
            "pct_of_total": round(pct, 4),
            "avg_coupon": round(avg_coupon, 6),
            "avg_maturity_years": round(avg_mat, 2),
            "bond_count": count,
        })

    return result


def compute_weighted_avg_cost_of_debt(bonds: list[dict]) -> float:
    """Weighted average coupon rate across all bonds.

    bonds: list of {coupon_rate: float, outstanding_amount: float}

    Weight by outstanding amount. Return weighted avg coupon rate.
    """
    total_outstanding = 0.0
    weighted_coupon_sum = 0.0

    for bond in bonds:
        amount = bond.get("outstanding_amount", 0.0)
        coupon = bond.get("coupon_rate", 0.0)
        weighted_coupon_sum += coupon * amount
        total_outstanding += amount

    if total_outstanding == 0:
        return 0.0

    return weighted_coupon_sum / total_outstanding


def compute_debt_maturity_profile(
    bonds: list[dict],
    reference_date: date | None = None,
) -> dict:
    """Compute maturity statistics.

    bonds: list of {maturity_date: date, outstanding_amount: float}

    Returns {
        avg_maturity_years: float,
        weighted_avg_maturity_years: float (weighted by outstanding),
        shortest_maturity_years: float,
        longest_maturity_years: float,
        total_outstanding: float,
        bond_count: int,
    }
    """
    ref = reference_date or date.today()

    if not bonds:
        return {
            "avg_maturity_years": 0.0,
            "weighted_avg_maturity_years": 0.0,
            "shortest_maturity_years": 0.0,
            "longest_maturity_years": 0.0,
            "total_outstanding": 0.0,
            "bond_count": 0,
        }

    total_outstanding = 0.0
    maturity_years_list: list[float] = []
    weighted_sum = 0.0

    for bond in bonds:
        mat_date = bond.get("maturity_date")
        amount = bond.get("outstanding_amount", 0.0)
        if mat_date is None:
            continue

        years = (mat_date - ref).days / 365.25
        years = max(years, 0.0)

        maturity_years_list.append(years)
        weighted_sum += years * amount
        total_outstanding += amount

    if not maturity_years_list:
        return {
            "avg_maturity_years": 0.0,
            "weighted_avg_maturity_years": 0.0,
            "shortest_maturity_years": 0.0,
            "longest_maturity_years": 0.0,
            "total_outstanding": total_outstanding,
            "bond_count": len(bonds),
        }

    avg_maturity = sum(maturity_years_list) / len(maturity_years_list)
    weighted_avg = weighted_sum / total_outstanding if total_outstanding > 0 else 0.0

    return {
        "avg_maturity_years": round(avg_maturity, 4),
        "weighted_avg_maturity_years": round(weighted_avg, 4),
        "shortest_maturity_years": round(min(maturity_years_list), 4),
        "longest_maturity_years": round(max(maturity_years_list), 4),
        "total_outstanding": round(total_outstanding, 2),
        "bond_count": len(maturity_years_list),
    }
