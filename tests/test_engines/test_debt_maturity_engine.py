"""Tests for the debt maturity profile engine (pure compute + DB persist)."""

import uuid
from datetime import date

import pytest
from sqlalchemy import select

from src.engines.debt_maturity_engine import (
    MaturityProfileResult,
    compute_and_persist_profiles,
    compute_maturity_profile,
    persist_profile,
)
from src.models.capital_structure import CapitalStructure, DebtTranche
from src.models.debt_maturity import DebtMaturityProfile, MaturityBucket
from src.models.entity import Entity


AS_OF = date(2026, 1, 1)


def _tranche(principal, maturity, coupon=None, seniority="SENIOR_SECURED"):
    return {
        "principal_amount": principal,
        "maturity_date": maturity,
        "coupon_rate": coupon,
        "seniority_type": seniority,
        "instrument_type": "TERM_LOAN",
    }


# ── Pure computation ────────────────────────────────────────────────────


class TestComputeMaturityProfile:
    def test_basic_buckets_and_totals(self):
        tranches = [
            _tranche(100.0, date(2026, 6, 1), coupon=0.05),   # within 1yr
            _tranche(200.0, date(2027, 6, 1), coupon=0.06),   # within 2yr
            _tranche(300.0, date(2028, 6, 1), coupon=0.07),   # within 3yr
            _tranche(400.0, date(2035, 6, 1), coupon=0.08),   # long-dated
        ]
        r = compute_maturity_profile(tranches, AS_OF)

        assert r.total_debt == 1000.0
        assert r.debt_maturing_1yr == 100.0
        assert r.debt_maturing_2yr == 300.0   # 100 + 200
        assert r.debt_maturing_3yr == 600.0   # 100 + 200 + 300
        assert r.pct_debt_maturing_1yr == pytest.approx(0.10, abs=1e-6)
        assert r.pct_debt_maturing_3yr == pytest.approx(0.60, abs=1e-6)
        # 4 distinct maturity years → 4 buckets
        assert {b.year for b in r.buckets} == {2026, 2027, 2028, 2035}

    def test_weighted_avg_coupon(self):
        tranches = [
            _tranche(100.0, date(2027, 1, 1), coupon=0.04),
            _tranche(300.0, date(2028, 1, 1), coupon=0.08),
        ]
        r = compute_maturity_profile(tranches, AS_OF)
        # (100*0.04 + 300*0.08) / 400 = 0.07
        assert r.weighted_avg_coupon == pytest.approx(0.07, abs=1e-6)

    def test_weighted_avg_maturity_years(self):
        # Single tranche maturing ~2 years out.
        tranches = [_tranche(100.0, date(2028, 1, 1))]
        r = compute_maturity_profile(tranches, AS_OF)
        assert r.weighted_avg_maturity_years == pytest.approx(2.0, abs=0.05)

    def test_maturity_wall_alert(self):
        # 50% of debt due within 1yr → wall + near-term stress.
        tranches = [
            _tranche(500.0, date(2026, 3, 1)),
            _tranche(500.0, date(2030, 3, 1)),
        ]
        r = compute_maturity_profile(tranches, AS_OF)
        assert r.maturity_wall_alert is True
        assert r.near_term_stress is True

    def test_cash_coverage_stress(self):
        tranches = [_tranche(1000.0, date(2026, 6, 1))]
        # Cash below 1x of 1yr maturities → stress even if pct alone wouldn't.
        r = compute_maturity_profile(tranches, AS_OF, cash=500.0)
        assert r.cash_to_1yr_maturities == pytest.approx(0.5, abs=1e-6)
        assert r.near_term_stress is True

    def test_past_due_excluded_from_windows(self):
        tranches = [
            _tranche(100.0, date(2020, 1, 1)),   # already matured
            _tranche(200.0, date(2028, 6, 1)),   # ~2.4yr out
        ]
        r = compute_maturity_profile(tranches, AS_OF)
        # Total debt still counts principal, but past-due is out of windows.
        assert r.total_debt == 300.0
        assert r.debt_maturing_1yr == 0.0
        assert r.debt_maturing_3yr == 200.0

    def test_empty(self):
        r = compute_maturity_profile([], AS_OF)
        assert r.total_debt == 0.0
        assert r.pct_debt_maturing_1yr is None
        assert r.weighted_avg_maturity_years is None
        assert r.buckets == []

    def test_bucket_breakdown_by_seniority(self):
        tranches = [
            _tranche(100.0, date(2027, 1, 1), seniority="SENIOR_SECURED"),
            _tranche(50.0, date(2027, 6, 1), seniority="SUBORDINATED"),
        ]
        r = compute_maturity_profile(tranches, AS_OF)
        bucket_2027 = next(b for b in r.buckets if b.year == 2027)
        assert bucket_2027.total_amount == 150.0
        assert bucket_2027.breakdown["SENIOR_SECURED"] == 100.0
        assert bucket_2027.breakdown["SUBORDINATED"] == 50.0


# ── DB persistence (aiosqlite) ──────────────────────────────────────────


async def _seed_entity_with_tranches(session) -> uuid.UUID:
    entity = Entity(
        entity_id=uuid.uuid4(),
        entity_type="PUBLIC_COMPANY",
        legal_name="DebtCo Inc.",
        status="ACTIVE",
        source="TEST",
    )
    session.add(entity)
    await session.flush()

    cap = CapitalStructure(
        capital_structure_id=uuid.uuid4(),
        entity_id=entity.entity_id,
        as_of_date=AS_OF,
    )
    session.add(cap)
    await session.flush()

    for principal, maturity, coupon in [
        (100.0, date(2026, 6, 1), 0.05),
        (300.0, date(2028, 6, 1), 0.07),
    ]:
        session.add(
            DebtTranche(
                tranche_id=uuid.uuid4(),
                entity_id=entity.entity_id,
                capital_structure_id=cap.capital_structure_id,
                principal_amount=principal,
                maturity_date=maturity,
                coupon_rate=coupon,
                seniority_type="SENIOR_SECURED",
                instrument_type="TERM_LOAN",
            )
        )
    await session.flush()
    return entity.entity_id


@pytest.mark.asyncio
async def test_persist_profile_writes_rows(session):
    entity_id = await _seed_entity_with_tranches(session)
    result = compute_maturity_profile(
        [_tranche(100.0, date(2026, 6, 1)), _tranche(300.0, date(2028, 6, 1))],
        AS_OF,
    )
    status = await persist_profile(session, entity_id, result)
    assert status == "inserted"

    profiles = (
        await session.execute(
            select(DebtMaturityProfile).where(
                DebtMaturityProfile.entity_id == entity_id
            )
        )
    ).scalars().all()
    assert len(profiles) == 1
    buckets = (
        await session.execute(
            select(MaturityBucket).where(
                MaturityBucket.profile_id == profiles[0].profile_id
            )
        )
    ).scalars().all()
    assert len(buckets) == 2


@pytest.mark.asyncio
async def test_compute_and_persist_is_idempotent(session):
    entity_id = await _seed_entity_with_tranches(session)

    first = await compute_and_persist_profiles(session, as_of_date=AS_OF)
    assert first["entities"] == 1
    assert first["profiles"] == 1
    assert first["replaced"] == 0

    second = await compute_and_persist_profiles(session, as_of_date=AS_OF)
    assert second["replaced"] == 1

    # Only one profile should remain for the (entity, as_of) pair.
    profiles = (
        await session.execute(
            select(DebtMaturityProfile).where(
                DebtMaturityProfile.entity_id == entity_id
            )
        )
    ).scalars().all()
    assert len(profiles) == 1
