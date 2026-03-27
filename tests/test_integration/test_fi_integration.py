"""Cross-domain FI integration tests (D11 FI Supplement P9)."""

import uuid
from datetime import date

import pytest
from sqlalchemy import select

from src.models.entity import Entity
from src.models.security import Security, FixedIncomeDetails
from src.models.corporate_bond import CorporateBond, BondEODPrice, BondTrade
from src.models.credit_rating import CreditRatingEvent, CurrentCreditRating
from src.models.treasury import TreasurySecurity
from src.engines.bond_analytics import compute_ytm, compute_g_spread
from src.engines.credit_rating_analytics import (
    rating_to_numeric,
    is_fallen_angel,
    is_rising_star,
    compute_notches,
)
from src.engines.issuer_linkage import detect_financing_subsidiary, build_issuer_bond_hierarchy


# ── Helpers ──────────────────────────────────────────────────────────


async def _seed_entity(session, legal_name="Integration Test Corp", **overrides):
    defaults = {
        "entity_id": uuid.uuid4(),
        "entity_type": "CORPORATION",
        "legal_name": legal_name,
        "status": "ACTIVE",
        "source": "TEST",
        "confidence_score": 0.99,
    }
    defaults.update(overrides)
    entity = Entity(**defaults)
    session.add(entity)
    await session.flush()
    return entity


async def _seed_bond(session, entity_id, cusip, name="Test Bond 5% 2035", **overrides):
    defaults = {
        "bond_id": uuid.uuid4(),
        "cusip": cusip,
        "issuer_entity_id": entity_id,
        "name": name,
        "coupon_rate": 5.0,
        "coupon_type": "FIXED",
        "coupon_frequency": 2,
        "maturity_date": date(2035, 6, 15),
        "seniority": "SENIOR_UNSECURED",
        "currency": "USD",
        "status": "OUTSTANDING",
    }
    defaults.update(overrides)
    bond = CorporateBond(**defaults)
    session.add(bond)
    await session.flush()
    return bond


# ── Integration Tests ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_entity_to_bond_chain(session):
    """Create Entity -> CorporateBond -> BondEODPrice -> verify full chain."""
    entity = await _seed_entity(session, legal_name="Chain Corp P9")
    bond = await _seed_bond(session, entity.entity_id, cusip="INT100AA1")

    eod = BondEODPrice(
        id=uuid.uuid4(),
        bond_id=bond.bond_id,
        price_date=date(2025, 10, 1),
        last_trade_price=98.5,
        vwap=98.45,
        trade_count=10,
        total_volume=5_000_000.00,
        yield_to_maturity=0.0520,
        g_spread_bps=150,
        has_sufficient_trades=True,
        price_source="TRACE",
    )
    session.add(eod)
    await session.flush()

    # Verify the chain: entity -> bond -> eod price
    bond_result = await session.execute(
        select(CorporateBond).where(CorporateBond.issuer_entity_id == entity.entity_id)
    )
    fetched_bond = bond_result.scalars().unique().one()
    assert fetched_bond.cusip == "INT100AA1"

    price_result = await session.execute(
        select(BondEODPrice).where(BondEODPrice.bond_id == fetched_bond.bond_id)
    )
    fetched_price = price_result.scalar_one()
    assert float(fetched_price.last_trade_price) == pytest.approx(98.5, abs=0.01)
    assert fetched_price.g_spread_bps == 150


@pytest.mark.asyncio
async def test_security_fi_details_link(session):
    """Create Security -> FixedIncomeDetails with D11 extension fields."""
    sec_id = uuid.uuid4()
    security = Security(
        security_id=sec_id,
        security_type="CORPORATE_BOND",
        name="FI Details Integration Bond",
        short_name="FIINT",
        status="ACTIVE",
        asset_class="FIXED_INCOME",
    )
    session.add(security)
    await session.flush()

    fi_details = FixedIncomeDetails(
        security_id=sec_id,
        face_value=1000.0,
        coupon_rate=0.045,
        coupon_type="FIXED",
        coupon_frequency="SEMI_ANNUAL",
        day_count_convention="30/360",
        seniority="SENIOR_UNSECURED",
        use_of_proceeds="GENERAL",
        liquidity_tier="TIER_1",
        benchmark_treasury_cusip="912828ZZ0",
        oas_bps=120.50,
    )
    session.add(fi_details)
    await session.flush()

    result = await session.execute(
        select(Security).where(Security.security_id == sec_id)
    )
    fetched = result.scalars().unique().one()
    assert fetched.fixed_income_details is not None
    assert fetched.fixed_income_details.use_of_proceeds == "GENERAL"
    assert fetched.fixed_income_details.liquidity_tier == "TIER_1"
    assert fetched.fixed_income_details.benchmark_treasury_cusip == "912828ZZ0"
    assert float(fetched.fixed_income_details.oas_bps) == pytest.approx(120.50, abs=0.01)


@pytest.mark.asyncio
async def test_rating_event_fallen_angel(session):
    """Create entity + rating event with is_fallen_angel=True."""
    entity = await _seed_entity(session, legal_name="Fallen Angel Integ Corp P9")

    event = CreditRatingEvent(
        event_id=uuid.uuid4(),
        entity_id=entity.entity_id,
        agency="SP",
        new_rating="BB+",
        old_rating="BBB-",
        direction="DOWNGRADE",
        event_date=date(2026, 3, 1),
        new_rating_numeric=11,
        old_rating_numeric=10,
        notches_changed=-1,
        is_fallen_angel=True,
        is_rising_star=False,
    )
    session.add(event)
    await session.flush()

    result = await session.execute(
        select(CreditRatingEvent).where(CreditRatingEvent.event_id == event.event_id)
    )
    fetched = result.scalar_one()
    assert fetched.is_fallen_angel is True
    assert fetched.is_rising_star is False
    assert fetched.entity_id == entity.entity_id


@pytest.mark.asyncio
async def test_rating_event_rising_star(session):
    """Create entity + rating event with is_rising_star=True."""
    entity = await _seed_entity(session, legal_name="Rising Star Integ Corp P9")

    event = CreditRatingEvent(
        event_id=uuid.uuid4(),
        entity_id=entity.entity_id,
        agency="SP",
        new_rating="BBB-",
        old_rating="BB+",
        direction="UPGRADE",
        event_date=date(2026, 2, 20),
        new_rating_numeric=10,
        old_rating_numeric=11,
        notches_changed=1,
        is_fallen_angel=False,
        is_rising_star=True,
    )
    session.add(event)
    await session.flush()

    result = await session.execute(
        select(CreditRatingEvent).where(CreditRatingEvent.event_id == event.event_id)
    )
    fetched = result.scalar_one()
    assert fetched.is_rising_star is True
    assert fetched.is_fallen_angel is False


@pytest.mark.asyncio
async def test_rating_numeric_roundtrip(session):
    """rating_to_numeric('SP', 'BBB-') -> 10, verify notch computation."""
    numeric_bbb_minus = rating_to_numeric("SP", "BBB-")
    assert numeric_bbb_minus == 10

    numeric_bb_plus = rating_to_numeric("SP", "BB+")
    assert numeric_bb_plus == 11

    notches = compute_notches(numeric_bbb_minus, numeric_bb_plus)
    assert notches == -1  # downgrade by 1 notch

    assert is_fallen_angel(numeric_bbb_minus, numeric_bb_plus) is True
    assert is_rising_star(numeric_bb_plus, numeric_bbb_minus) is True


@pytest.mark.asyncio
async def test_bond_ytm_g_spread_flow(session):
    """Create bond with coupon=5%, compute YTM at price=98, compute G-spread vs treasury."""
    coupon_rate = 0.05
    price = 98.0
    face_value = 100.0
    years_to_maturity = 10.0
    frequency = 2
    treasury_yield = 0.04

    ytm = compute_ytm(price, coupon_rate, face_value, years_to_maturity, frequency)
    assert ytm > coupon_rate  # price below par means YTM > coupon

    g_spread = compute_g_spread(ytm, treasury_yield)
    assert g_spread > 0  # bond yield should exceed treasury yield
    assert isinstance(g_spread, int)  # G-spread returned in integer bps


@pytest.mark.asyncio
async def test_financing_subsidiary_detection(session):
    """detect_financing_subsidiary on various names."""
    assert detect_financing_subsidiary("Goldman Sachs Capital LLC") is True
    assert detect_financing_subsidiary("AT&T Funding Corp") is True
    assert detect_financing_subsidiary("Verizon Finance BV") is True
    assert detect_financing_subsidiary("Apple Inc") is False
    assert detect_financing_subsidiary("") is False
    assert detect_financing_subsidiary("National Treasury Board") is True


@pytest.mark.asyncio
async def test_issuer_hierarchy_build(session):
    """Build parent -> subsidiary -> bonds hierarchy."""
    parent = {"entity_id": "integ-p1", "legal_name": "Mega Corp"}
    subs = [
        {"entity_id": "integ-s1", "legal_name": "Mega Capital LLC"},
        {"entity_id": "integ-s2", "legal_name": "Mega Funding Inc"},
    ]
    bonds_by_entity = {
        "integ-p1": [{"cusip": "MEGAAA001", "name": "Mega 4% 2030"}],
        "integ-s1": [
            {"cusip": "MEGABB001", "name": "Mega Capital 5% 2032"},
            {"cusip": "MEGABB002", "name": "Mega Capital 3.5% 2028"},
        ],
        "integ-s2": [{"cusip": "MEGACC001", "name": "Mega Funding 6% 2040"}],
    }

    tree = build_issuer_bond_hierarchy(parent, subs, bonds_by_entity)
    assert tree["entity_id"] == "integ-p1"
    assert len(tree["bonds"]) == 1
    assert len(tree["subsidiaries"]) == 2

    sub1 = next(s for s in tree["subsidiaries"] if s["entity_id"] == "integ-s1")
    assert len(sub1["bonds"]) == 2

    sub2 = next(s for s in tree["subsidiaries"] if s["entity_id"] == "integ-s2")
    assert len(sub2["bonds"]) == 1


@pytest.mark.asyncio
async def test_entity_subsidiary_linkage(session):
    """Create parent + subsidiary entities, set financing_parent_id."""
    parent = await _seed_entity(session, legal_name="Linkage Parent Corp P9")
    child = await _seed_entity(
        session,
        legal_name="Linkage Capital LLC P9",
        is_financing_subsidiary=True,
        financing_parent_id=parent.entity_id,
    )

    result = await session.execute(
        select(Entity).where(Entity.entity_id == child.entity_id)
    )
    fetched = result.scalar_one()
    assert fetched.financing_parent_id == parent.entity_id
    assert fetched.is_financing_subsidiary is True


@pytest.mark.asyncio
async def test_corporate_bond_with_ratings(session):
    """Entity + CorporateBond + CreditRatingEvent all linked together."""
    entity = await _seed_entity(session, legal_name="Rated Bond Corp P9")
    bond = await _seed_bond(
        session,
        entity.entity_id,
        cusip="INT200BB2",
        name="Rated Bond 4.5% 2033",
        initial_rating_sp="BBB+",
        initial_rating_moodys="Baa1",
        is_investment_grade=True,
    )

    event = CreditRatingEvent(
        event_id=uuid.uuid4(),
        entity_id=entity.entity_id,
        agency="SP",
        new_rating="BBB",
        old_rating="BBB+",
        direction="DOWNGRADE",
        event_date=date(2026, 1, 15),
        new_rating_numeric=9,
        old_rating_numeric=8,
        notches_changed=-1,
        is_fallen_angel=False,
        is_rising_star=False,
    )
    session.add(event)
    await session.flush()

    # Verify bond and rating event share the same entity
    bond_result = await session.execute(
        select(CorporateBond).where(CorporateBond.bond_id == bond.bond_id)
    )
    fetched_bond = bond_result.scalars().unique().one()
    assert fetched_bond.issuer_entity_id == entity.entity_id
    assert fetched_bond.initial_rating_sp == "BBB+"

    rating_result = await session.execute(
        select(CreditRatingEvent).where(CreditRatingEvent.entity_id == entity.entity_id)
    )
    fetched_rating = rating_result.scalar_one()
    assert fetched_rating.new_rating == "BBB"
    assert fetched_rating.entity_id == entity.entity_id


@pytest.mark.asyncio
async def test_treasury_benchmark_link(session):
    """FixedIncomeDetails with benchmark_treasury_cusip matching a TreasurySecurity."""
    # Create treasury
    treasury = TreasurySecurity(
        treasury_id=uuid.uuid4(),
        cusip="912828YY1",
        treasury_type="NOTE",
        coupon_rate=0.025,
        coupon_frequency=2,
        issue_date=date(2025, 1, 15),
        maturity_date=date(2035, 1, 15),
        is_outstanding=True,
        status="OUTSTANDING",
    )
    session.add(treasury)
    await session.flush()

    # Create security with FI details pointing to that treasury
    sec_id = uuid.uuid4()
    security = Security(
        security_id=sec_id,
        security_type="CORPORATE_BOND",
        name="Treasury Linked Bond",
        status="ACTIVE",
        asset_class="FIXED_INCOME",
    )
    session.add(security)
    await session.flush()

    fi_details = FixedIncomeDetails(
        security_id=sec_id,
        face_value=1000.0,
        coupon_rate=0.05,
        coupon_type="FIXED",
        coupon_frequency="SEMI_ANNUAL",
        benchmark_treasury_cusip="912828YY1",
        oas_bps=180.00,
    )
    session.add(fi_details)
    await session.flush()

    # Verify the link
    result = await session.execute(
        select(FixedIncomeDetails).where(FixedIncomeDetails.security_id == sec_id)
    )
    fetched_fi = result.scalar_one()
    assert fetched_fi.benchmark_treasury_cusip == "912828YY1"

    treas_result = await session.execute(
        select(TreasurySecurity).where(TreasurySecurity.cusip == fetched_fi.benchmark_treasury_cusip)
    )
    fetched_treas = treas_result.scalar_one()
    assert fetched_treas.treasury_type == "NOTE"
    assert fetched_treas.maturity_date == date(2035, 1, 15)


@pytest.mark.asyncio
async def test_full_bond_lifecycle(session):
    """Full lifecycle: entity -> bond -> trades -> EOD price -> rating -> all linked."""
    # 1. Create entity
    entity = await _seed_entity(session, legal_name="Lifecycle Corp P9")

    # 2. Create bond
    bond = await _seed_bond(
        session,
        entity.entity_id,
        cusip="INT300CC3",
        name="Lifecycle 5.25% 2034",
        coupon_rate=5.25,
        issue_date=date(2024, 6, 1),
        maturity_date=date(2034, 6, 1),
    )

    # 3. Create trades
    trade1 = BondTrade(
        trade_id=uuid.uuid4(),
        bond_id=bond.bond_id,
        trade_date=date(2025, 10, 1),
        price=99.5,
        yield_value=0.0530,
        quantity=500_000.00,
        trade_type="CUSTOMER_BUY",
        source="TRACE",
    )
    trade2 = BondTrade(
        trade_id=uuid.uuid4(),
        bond_id=bond.bond_id,
        trade_date=date(2025, 10, 1),
        price=99.25,
        yield_value=0.0535,
        quantity=1_000_000.00,
        trade_type="INTER_DEALER",
        source="TRACE",
    )
    session.add_all([trade1, trade2])
    await session.flush()

    # 4. Create EOD price
    eod = BondEODPrice(
        id=uuid.uuid4(),
        bond_id=bond.bond_id,
        price_date=date(2025, 10, 1),
        last_trade_price=99.25,
        vwap=99.333,
        high_price=99.5,
        low_price=99.25,
        trade_count=2,
        total_volume=1_500_000.00,
        yield_to_maturity=0.0532,
        g_spread_bps=132,
        has_sufficient_trades=False,
        price_source="TRACE",
    )
    session.add(eod)
    await session.flush()

    # 5. Create credit rating event
    rating_event = CreditRatingEvent(
        event_id=uuid.uuid4(),
        entity_id=entity.entity_id,
        agency="SP",
        new_rating="BBB",
        old_rating="BBB+",
        direction="DOWNGRADE",
        event_date=date(2025, 9, 15),
        new_rating_numeric=9,
        old_rating_numeric=8,
        notches_changed=-1,
        is_fallen_angel=False,
        is_rising_star=False,
    )
    session.add(rating_event)
    await session.flush()

    # Verify the full chain
    # Entity
    entity_result = await session.execute(
        select(Entity).where(Entity.entity_id == entity.entity_id)
    )
    assert entity_result.scalar_one().legal_name == "Lifecycle Corp P9"

    # Bond linked to entity
    bond_result = await session.execute(
        select(CorporateBond).where(CorporateBond.issuer_entity_id == entity.entity_id)
    )
    fetched_bond = bond_result.scalars().unique().one()
    assert fetched_bond.cusip == "INT300CC3"

    # Trades linked to bond
    trades_result = await session.execute(
        select(BondTrade).where(BondTrade.bond_id == fetched_bond.bond_id)
    )
    trades = trades_result.scalars().all()
    assert len(trades) == 2

    # EOD price linked to bond
    eod_result = await session.execute(
        select(BondEODPrice).where(BondEODPrice.bond_id == fetched_bond.bond_id)
    )
    fetched_eod = eod_result.scalar_one()
    assert fetched_eod.g_spread_bps == 132
    assert fetched_eod.trade_count == 2

    # Rating event linked to entity
    rating_result = await session.execute(
        select(CreditRatingEvent).where(CreditRatingEvent.entity_id == entity.entity_id)
    )
    fetched_rating = rating_result.scalar_one()
    assert fetched_rating.new_rating == "BBB"
    assert fetched_rating.notches_changed == -1
