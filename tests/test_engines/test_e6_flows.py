"""Tests for E6 Institutional Flow Analytics Engine.

Comprehensive test suite covering position change detection, aggregate
metrics, tier-weighted conviction, smart money flow, short interest
integration, squeeze classification, persistence, and alert generation.
"""

import uuid
from datetime import date, datetime, timezone

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.engines.base import EngineOutput
from src.engines.e6_flows import InstitutionalFlowEngine
from src.models.entity import Entity
from src.models.flows import FlowAlert, InstitutionalFlowSignal
from src.models.ownership import InstitutionalHolding, InstitutionProfile, ShortInterest
from src.models.security import Security


# ---------------------------------------------------------------------------
# Fixed IDs for deterministic assertions
# ---------------------------------------------------------------------------
ENTITY_ID = uuid.uuid4()
SECURITY_ID = uuid.uuid4()
WHALE_INST_ID = uuid.uuid4()
MAJOR_INST_ID = uuid.uuid4()
SMALL_INST_ID = uuid.uuid4()

Q1_DATE = date(2025, 12, 31)
Q2_DATE = date(2026, 3, 31)

NOW = datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _metric(outputs: list[EngineOutput], name: str) -> EngineOutput | None:
    """Look up a single metric by name from a list of EngineOutput."""
    for o in outputs:
        if o.metric_name == name:
            return o
    return None


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def e6_engine():
    """Return a fresh E6 engine instance."""
    return InstitutionalFlowEngine()


@pytest_asyncio.fixture
async def seeded_security(session: AsyncSession) -> uuid.UUID:
    """Create entity + security with no holdings.  Returns security_id."""
    entity = Entity(
        entity_id=ENTITY_ID,
        legal_name="Test Corp",
        entity_type="PUBLIC_COMPANY",
        status="ACTIVE",
        source="TEST",
    )
    session.add(entity)
    await session.flush()

    security = Security(
        security_id=SECURITY_ID,
        name="Test Corp Common Stock",
        short_name="TEST",
        security_type="COMMON_STOCK",
        asset_class="EQUITY",
        status="ACTIVE",
        issuer_entity_id=ENTITY_ID,
    )
    session.add(security)
    await session.flush()
    return SECURITY_ID


@pytest_asyncio.fixture
async def institution_profiles(session: AsyncSession, seeded_security):
    """Create 3 institution profiles: WHALE, MAJOR, SMALL.

    Returns a dict mapping tier label -> institution_id.
    """
    profiles = [
        InstitutionProfile(
            institution_id=WHALE_INST_ID,
            institution_name="Whale Capital Management",
            institution_type="HEDGE_FUND",
            tier="WHALE",
            aum=500_000_000_000,
        ),
        InstitutionProfile(
            institution_id=MAJOR_INST_ID,
            institution_name="Major Asset Partners",
            institution_type="MUTUAL_FUND",
            tier="MAJOR",
            aum=50_000_000_000,
        ),
        InstitutionProfile(
            institution_id=SMALL_INST_ID,
            institution_name="Small Value Fund",
            institution_type="HEDGE_FUND",
            tier="SMALL",
            aum=500_000_000,
        ),
    ]
    for p in profiles:
        session.add(p)
    await session.flush()
    return {
        "whale": WHALE_INST_ID,
        "major": MAJOR_INST_ID,
        "small": SMALL_INST_ID,
    }


@pytest_asyncio.fixture
async def two_quarter_holdings(session: AsyncSession, institution_profiles):
    """Seed holdings for 2 quarters.

    Q1 (2025-12-31):
      - Whale: 100K shares, $10M MV, pct_outstanding=0.05
      - Major: 50K shares, $15M MV, pct_outstanding=0.025

    Q2 (2026-03-31):
      - Whale: 120K shares, $12M MV, shares_change=+20K, pct_outstanding=0.06
        (increased -- 20% > 5% threshold)
      - Small: 30K shares, $3M MV, shares_change=+30K (brand new position)
      - Major: ABSENT (fully exited)

    Position analysis:
      new=1 (Small), closed=1 (Major), increased=1 (Whale),
      decreased=0, unchanged=0.  Total=3.
    """
    holdings = [
        # ---- Q1 ----
        InstitutionalHolding(
            institution_id=WHALE_INST_ID,
            security_id=SECURITY_ID,
            report_date=Q1_DATE,
            filing_date=date(2026, 1, 15),
            shares_held=100_000,
            market_value=10_000_000,
            percent_of_portfolio=0.02,
            percent_of_outstanding=0.05,
            shares_change=10_000,
            is_new_position=False,
            is_sold_out=False,
            source="SEC_13F",
            created_at=NOW,
        ),
        InstitutionalHolding(
            institution_id=MAJOR_INST_ID,
            security_id=SECURITY_ID,
            report_date=Q1_DATE,
            filing_date=date(2026, 1, 15),
            shares_held=50_000,
            market_value=15_000_000,
            percent_of_portfolio=0.03,
            percent_of_outstanding=0.025,
            shares_change=5_000,
            is_new_position=False,
            is_sold_out=False,
            source="SEC_13F",
            created_at=NOW,
        ),
        # ---- Q2 ----
        InstitutionalHolding(
            institution_id=WHALE_INST_ID,
            security_id=SECURITY_ID,
            report_date=Q2_DATE,
            filing_date=date(2026, 4, 15),
            shares_held=120_000,
            market_value=12_000_000,
            percent_of_portfolio=0.025,
            percent_of_outstanding=0.06,
            shares_change=20_000,
            is_new_position=False,
            is_sold_out=False,
            source="SEC_13F",
            created_at=NOW,
        ),
        InstitutionalHolding(
            institution_id=SMALL_INST_ID,
            security_id=SECURITY_ID,
            report_date=Q2_DATE,
            filing_date=date(2026, 4, 15),
            shares_held=30_000,
            market_value=3_000_000,
            percent_of_portfolio=0.06,
            percent_of_outstanding=0.015,
            shares_change=30_000,
            is_new_position=True,
            is_sold_out=False,
            source="SEC_13F",
            created_at=NOW,
        ),
    ]
    for h in holdings:
        session.add(h)
    await session.flush()


@pytest_asyncio.fixture
async def computed_outputs(
    session: AsyncSession, e6_engine, two_quarter_holdings
) -> list[EngineOutput]:
    """Run E6 compute and return the output list (2-quarter path)."""
    return await e6_engine.compute(session, SECURITY_ID)


# ===========================================================================
# 1. Engine identity
# ===========================================================================


def test_e6_engine_id(e6_engine):
    """engine.engine_id must be 'E6'."""
    assert e6_engine.engine_id == "E6"


# ===========================================================================
# 2. Basic compute contract
# ===========================================================================


@pytest.mark.asyncio
async def test_e6_compute_basic(computed_outputs):
    """compute() returns a non-empty list of EngineOutput."""
    assert isinstance(computed_outputs, list)
    assert len(computed_outputs) > 0
    for o in computed_outputs:
        assert isinstance(o, EngineOutput)


# ===========================================================================
# 3-6. Position change counts
# ===========================================================================


@pytest.mark.asyncio
async def test_e6_new_positions_count(computed_outputs):
    """Small is the only new position (in Q2, not in Q1) -> count=1."""
    m = _metric(computed_outputs, "inst_new_positions_count")
    assert m is not None
    assert m.value == 1.0


@pytest.mark.asyncio
async def test_e6_closed_positions_count(computed_outputs):
    """Major is the only closed position (in Q1, absent Q2) -> count=1."""
    m = _metric(computed_outputs, "inst_closed_positions_count")
    assert m is not None
    assert m.value == 1.0


@pytest.mark.asyncio
async def test_e6_increased_positions_count(computed_outputs):
    """Whale increased by 20K (20% of prior 100K, above 5% threshold) -> count=1."""
    m = _metric(computed_outputs, "inst_increased_positions_count")
    assert m is not None
    assert m.value == 1.0


@pytest.mark.asyncio
async def test_e6_net_shares_change(computed_outputs):
    """net_shares_change = sum of Q2 shares_change = +20K + +30K = 50K."""
    m = _metric(computed_outputs, "inst_net_shares_change")
    assert m is not None
    assert m.value == pytest.approx(50_000.0)


# ===========================================================================
# 7. Buy/sell ratio
# ===========================================================================


@pytest.mark.asyncio
async def test_e6_buy_sell_ratio(computed_outputs):
    """(new + increased) / max(closed + decreased, 1) = (1+1)/(1+0) = 2.0."""
    m = _metric(computed_outputs, "inst_buy_sell_ratio")
    assert m is not None
    assert m.value == pytest.approx(2.0)


# ===========================================================================
# 8. Breadth score
# ===========================================================================


@pytest.mark.asyncio
async def test_e6_breadth_score(computed_outputs):
    """breadth = clamp((new+increased - closed-decreased) / total).

    (1+1 - 1-0) / 3 = 1/3 ~ 0.333
    """
    m = _metric(computed_outputs, "inst_breadth_score")
    assert m is not None
    assert m.value == pytest.approx(1.0 / 3.0, abs=0.001)


# ===========================================================================
# 9. Conviction score (tier-weighted)
# ===========================================================================


@pytest.mark.asyncio
async def test_e6_conviction_score(computed_outputs):
    """Conviction = (weighted_positive / weighted_all) * 100.

    Positive (new + increased):
      Whale(increased) weight=4, Small(new) weight=1 => 5
    Negative (closed + decreased):
      Major(closed) weight=3 => 3
    Unchanged: none
    weighted_all = 4 + 1 + 3 = 8
    conviction = (5 / 8) * 100 = 62.5
    """
    m = _metric(computed_outputs, "inst_conviction_score")
    assert m is not None
    assert m.value == pytest.approx(62.5)


# ===========================================================================
# 10. Smart money flow
# ===========================================================================


@pytest.mark.asyncio
async def test_e6_smart_money_flow(computed_outputs):
    """Smart money (WHALE + MAJOR only).

    Whale is in Q2 with shares_change > 0 -> buyer  (1)
    Major is closed -> seller (1)
    total_whales = 2
    smart_money_flow = clamp((1 - 1) / 2) = 0.0
    """
    m = _metric(computed_outputs, "inst_smart_money_flow")
    assert m is not None
    assert m.value == pytest.approx(0.0)


# ===========================================================================
# 11. No holdings -> INSUFFICIENT_DATA
# ===========================================================================


@pytest.mark.asyncio
async def test_e6_no_holdings(session: AsyncSession, e6_engine, seeded_security):
    """Security with zero holdings returns single INSUFFICIENT_DATA output."""
    outputs = await e6_engine.compute(session, SECURITY_ID)
    assert len(outputs) == 1
    assert outputs[0].data_quality == "INSUFFICIENT_DATA"
    assert outputs[0].metric_name == "inst_data_quality"


# ===========================================================================
# 12. Single quarter -> PARTIAL
# ===========================================================================


@pytest.mark.asyncio
async def test_e6_single_quarter(session: AsyncSession, e6_engine, seeded_security):
    """Single report_date produces PARTIAL outputs."""
    inst_id = uuid.uuid4()
    session.add(InstitutionProfile(
        institution_id=inst_id,
        institution_name="Solo Fund",
        institution_type="HEDGE_FUND",
        tier="SMALL",
    ))
    await session.flush()

    session.add(InstitutionalHolding(
        institution_id=inst_id,
        security_id=SECURITY_ID,
        report_date=Q2_DATE,
        shares_held=10_000,
        market_value=1_000_000,
        shares_change=10_000,
        is_new_position=True,
        is_sold_out=False,
        source="SEC_13F",
        created_at=NOW,
    ))
    await session.flush()

    outputs = await e6_engine.compute(session, SECURITY_ID)
    assert len(outputs) > 0
    for o in outputs:
        assert o.data_quality == "PARTIAL"

    names = {o.metric_name for o in outputs}
    assert "inst_new_positions_count" in names
    assert "inst_net_shares_change" in names


# ===========================================================================
# 13. Persistence of InstitutionalFlowSignal
# ===========================================================================


@pytest.mark.asyncio
async def test_e6_persists_signal(session: AsyncSession, computed_outputs):
    """After compute, an InstitutionalFlowSignal row must exist in the DB."""
    result = await session.execute(
        select(InstitutionalFlowSignal).where(
            InstitutionalFlowSignal.security_id == SECURITY_ID,
            InstitutionalFlowSignal.report_date == Q2_DATE,
        )
    )
    signal = result.scalar_one_or_none()
    assert signal is not None
    assert signal.data_quality == "COMPLETE"
    assert signal.new_positions_count == 1
    assert signal.closed_positions_count == 1
    assert signal.increased_positions_count == 1


# ===========================================================================
# 14. Alert generation (FULL_EXIT for Major with prior MV > $10M)
# ===========================================================================


@pytest.mark.asyncio
async def test_e6_generates_alerts(session: AsyncSession, computed_outputs):
    """Major exited with prior MV=$15M (>$10M).  Expect a FULL_EXIT alert.

    Whale has pct_outstanding change = 0.06 - 0.05 = 0.01.
    The WHALE_MOVE threshold is strictly > 0.01, so Whale does NOT trigger.
    """
    result = await session.execute(
        select(FlowAlert).where(
            FlowAlert.security_id == SECURITY_ID,
            FlowAlert.report_date == Q2_DATE,
        )
    )
    alerts = result.scalars().all()

    # FULL_EXIT for Major
    exit_alerts = [a for a in alerts if a.alert_type == "FULL_EXIT"]
    assert len(exit_alerts) == 1
    assert exit_alerts[0].institution_id == MAJOR_INST_ID
    assert exit_alerts[0].severity == "HIGH"
    assert "Major Asset Partners" in exit_alerts[0].headline
    assert float(exit_alerts[0].value_involved) == pytest.approx(15_000_000.0)

    # No WHALE_MOVE alert (0.01 is not > 0.01)
    whale_alerts = [a for a in alerts if a.alert_type == "WHALE_MOVE"]
    assert len(whale_alerts) == 0


# ===========================================================================
# 15. Squeeze LOW with no short interest
# ===========================================================================


@pytest.mark.asyncio
async def test_e6_squeeze_low(computed_outputs):
    """No short interest data -> squeeze_potential = LOW."""
    m = _metric(computed_outputs, "inst_squeeze_potential")
    assert m is not None
    squeeze_inp = [
        inp for inp in (m.inputs or []) if inp.get("name") == "squeeze"
    ]
    assert len(squeeze_inp) == 1
    assert squeeze_inp[0]["period"] == "LOW"


# ===========================================================================
# 16. Squeeze HIGH with high short interest + ACCUMULATION trend
# ===========================================================================


@pytest.mark.asyncio
async def test_e6_squeeze_high(session: AsyncSession, e6_engine, seeded_security):
    """HIGH squeeze: short_percent_float > 20% AND trend = ACCUMULATION.

    Create 5 quarterly dates with consistently positive shares_change
    to produce an ACCUMULATION trend (3+ positive quarter pairs),
    plus short interest at 25% of float.
    """
    inst_id = uuid.uuid4()
    session.add(InstitutionProfile(
        institution_id=inst_id,
        institution_name="Squeeze Fund",
        institution_type="HEDGE_FUND",
        tier="WHALE",
    ))
    await session.flush()

    # 5 quarterly dates for multi-quarter trend computation
    quarter_dates = [
        date(2025, 3, 31),
        date(2025, 6, 30),
        date(2025, 9, 30),
        date(2025, 12, 31),
        date(2026, 3, 31),
    ]
    for i, qd in enumerate(quarter_dates):
        session.add(InstitutionalHolding(
            institution_id=inst_id,
            security_id=SECURITY_ID,
            report_date=qd,
            shares_held=10_000 * (i + 1),
            market_value=1_000_000 * (i + 1),
            shares_change=10_000,  # positive each quarter
            percent_of_outstanding=0.01 * (i + 1),
            is_new_position=(i == 0),
            is_sold_out=False,
            source="SEC_13F",
            created_at=NOW,
        ))

    # Short interest > 20% of float
    session.add(ShortInterest(
        security_id=SECURITY_ID,
        settlement_date=date(2026, 3, 15),
        shares_short=2_500_000,
        short_percent_float=0.25,
        short_percent_outstanding=0.20,
        days_to_cover=4.5,
        source="FINRA",
    ))
    await session.flush()

    outputs = await e6_engine.compute(session, SECURITY_ID)
    m = _metric(outputs, "inst_squeeze_potential")
    assert m is not None
    squeeze_inp = [
        inp for inp in (m.inputs or []) if inp.get("name") == "squeeze"
    ]
    assert len(squeeze_inp) == 1
    assert squeeze_inp[0]["period"] == "HIGH"


# ===========================================================================
# 17. Metric count
# ===========================================================================


@pytest.mark.asyncio
async def test_e6_metric_count(computed_outputs):
    """Full 2-quarter compute should produce exactly 16 metrics."""
    assert len(computed_outputs) == 16


# ===========================================================================
# 18. Output structure
# ===========================================================================


@pytest.mark.asyncio
async def test_e6_output_structure(computed_outputs):
    """Every output carries engine_id='E6' and category='INSTITUTIONAL_FLOW'."""
    for o in computed_outputs:
        assert o.engine_id == "E6"
        assert o.metric_category == "INSTITUTIONAL_FLOW"


# ===========================================================================
# 19. Security not found
# ===========================================================================


@pytest.mark.asyncio
async def test_e6_security_not_found(session: AsyncSession, e6_engine):
    """compute() with a nonexistent security_id returns an empty list."""
    fake_id = uuid.uuid4()
    outputs = await e6_engine.compute(session, fake_id)
    assert outputs == []


# ===========================================================================
# 20. _classify_squeeze static method (direct unit tests)
# ===========================================================================


class TestClassifySqueeze:
    """Direct unit tests for _classify_squeeze static method."""

    def test_high(self):
        """short > 20% and ACCUMULATION -> HIGH."""
        assert InstitutionalFlowEngine._classify_squeeze(0.25, "ACCUMULATION", 0.5) == "HIGH"

    def test_moderate(self):
        """short > 10% and breadth > 0 -> MODERATE."""
        assert InstitutionalFlowEngine._classify_squeeze(0.15, "NEUTRAL", 0.3) == "MODERATE"

    def test_low_no_short(self):
        """None short interest -> LOW."""
        assert InstitutionalFlowEngine._classify_squeeze(None, "ACCUMULATION", 0.5) == "LOW"

    def test_low_below_thresholds(self):
        """short <= 10% -> LOW regardless of breadth."""
        assert InstitutionalFlowEngine._classify_squeeze(0.05, "NEUTRAL", 0.5) == "LOW"

    def test_high_beats_moderate(self):
        """When both HIGH and MODERATE conditions met, HIGH wins (checked first)."""
        assert InstitutionalFlowEngine._classify_squeeze(0.25, "ACCUMULATION", 0.8) == "HIGH"

    def test_moderate_negative_breadth(self):
        """short > 10% but breadth <= 0 -> LOW."""
        assert InstitutionalFlowEngine._classify_squeeze(0.15, "NEUTRAL", -0.1) == "LOW"
