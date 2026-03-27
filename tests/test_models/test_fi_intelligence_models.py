"""Tests for Pillar 3 Phase 3C: FI Intelligence + Alert Expansion models."""

import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from src.models.entity import Entity
from src.models.fi_intelligence import (
    CrossAssetSignal,
    FIMarketBriefing,
    NewIssuanceEvent,
)
from src.models.alert_expansion import FIAlertConfig


# ── Helpers ──────────────────────────────────────────────────────────


async def _seed_entity(session, entity_id: uuid.UUID | None = None) -> Entity:
    eid = entity_id or uuid.uuid4()
    entity = Entity(
        entity_id=eid,
        entity_type="PUBLIC_COMPANY",
        legal_name="FI Intelligence Test Corp",
        status="ACTIVE",
        source="TEST",
    )
    session.add(entity)
    await session.flush()
    return entity


# ── FIMarketBriefing Tests ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_fi_market_briefing(session):
    """Create a full FI market briefing and verify all fields."""
    bid = uuid.uuid4()
    briefing = FIMarketBriefing(
        id=bid,
        briefing_date=date(2025, 7, 15),
        briefing_type="CREDIT",
        ig_oas_bps=Decimal("95.50"),
        hy_oas_bps=Decimal("350.25"),
        ig_oas_1w_change=Decimal("-5.00"),
        hy_oas_1w_change=Decimal("12.00"),
        credit_regime="NORMAL",
        spread_2s10s_bps=Decimal("45.00"),
        spread_3m10y_bps=Decimal("-20.00"),
        curve_shape="INVERTED",
        narrative="Credit spreads tightened this week.",
        ai_enabled=True,
    )
    session.add(briefing)
    await session.flush()

    result = await session.execute(
        select(FIMarketBriefing).where(FIMarketBriefing.id == bid)
    )
    fetched = result.scalar_one()
    assert fetched.briefing_date == date(2025, 7, 15)
    assert fetched.briefing_type == "CREDIT"
    assert fetched.ig_oas_bps == Decimal("95.50")
    assert fetched.hy_oas_bps == Decimal("350.25")
    assert fetched.ig_oas_1w_change == Decimal("-5.00")
    assert fetched.hy_oas_1w_change == Decimal("12.00")
    assert fetched.credit_regime == "NORMAL"
    assert fetched.spread_2s10s_bps == Decimal("45.00")
    assert fetched.spread_3m10y_bps == Decimal("-20.00")
    assert fetched.curve_shape == "INVERTED"
    assert fetched.narrative == "Credit spreads tightened this week."
    assert fetched.ai_enabled is True


@pytest.mark.asyncio
async def test_briefing_decimal_precision(session):
    """Verify Numeric(8,2) precision on spread fields."""
    bid = uuid.uuid4()
    session.add(FIMarketBriefing(
        id=bid,
        briefing_date=date(2025, 8, 1),
        ig_oas_bps=Decimal("123.45"),
        hy_oas_bps=Decimal("456.78"),
    ))
    await session.flush()

    result = await session.execute(
        select(FIMarketBriefing).where(FIMarketBriefing.id == bid)
    )
    fetched = result.scalar_one()
    assert fetched.ig_oas_bps == Decimal("123.45")
    assert fetched.hy_oas_bps == Decimal("456.78")


@pytest.mark.asyncio
async def test_briefing_fallen_angels_jsonb(session):
    """Round-trip JSONB fallen_angels_this_period."""
    bid = uuid.uuid4()
    fa_data = {"entity_name": "TestCorp", "old_rating": "BBB-", "new_rating": "BB+"}
    session.add(FIMarketBriefing(
        id=bid,
        briefing_date=date(2025, 8, 5),
        fallen_angels_this_period=fa_data,
    ))
    await session.flush()

    result = await session.execute(
        select(FIMarketBriefing).where(FIMarketBriefing.id == bid)
    )
    fetched = result.scalar_one()
    assert fetched.fallen_angels_this_period == fa_data
    assert fetched.fallen_angels_this_period["entity_name"] == "TestCorp"


@pytest.mark.asyncio
async def test_briefing_rising_stars_jsonb(session):
    """Round-trip JSONB rising_stars_this_period."""
    bid = uuid.uuid4()
    rs_data = {"entity_name": "UpgradeCo", "old_rating": "BB+", "new_rating": "BBB-"}
    session.add(FIMarketBriefing(
        id=bid,
        briefing_date=date(2025, 8, 10),
        rising_stars_this_period=rs_data,
    ))
    await session.flush()

    result = await session.execute(
        select(FIMarketBriefing).where(FIMarketBriefing.id == bid)
    )
    fetched = result.scalar_one()
    assert fetched.rising_stars_this_period == rs_data
    assert fetched.rising_stars_this_period["new_rating"] == "BBB-"


@pytest.mark.asyncio
async def test_briefing_defaults(session):
    """Verify default values on ai_enabled."""
    bid = uuid.uuid4()
    session.add(FIMarketBriefing(
        id=bid,
        briefing_date=date(2025, 9, 1),
    ))
    await session.flush()

    result = await session.execute(
        select(FIMarketBriefing).where(FIMarketBriefing.id == bid)
    )
    fetched = result.scalar_one()
    assert fetched.ai_enabled is False


# ── NewIssuanceEvent Tests ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_new_issuance_event(session):
    """Create a new issuance event with all fields."""
    entity = await _seed_entity(session)
    iid = uuid.uuid4()
    event = NewIssuanceEvent(
        id=iid,
        entity_id=entity.entity_id,
        issue_date=date(2025, 7, 20),
        coupon_rate=Decimal("5.2500"),
        maturity_date=date(2035, 7, 20),
        size_mm=Decimal("750.00"),
        spread_at_issue_bps=Decimal("125.00"),
        initial_talk_bps=Decimal("135.00"),
        rating="BBB+",
        use_of_proceeds="GENERAL_CORPORATE",
        oversubscribed=True,
        source_url="https://example.com/issuance",
    )
    session.add(event)
    await session.flush()

    result = await session.execute(
        select(NewIssuanceEvent).where(NewIssuanceEvent.id == iid)
    )
    fetched = result.scalar_one()
    assert fetched.entity_id == entity.entity_id
    assert fetched.issue_date == date(2025, 7, 20)
    assert fetched.coupon_rate == Decimal("5.2500")
    assert fetched.maturity_date == date(2035, 7, 20)
    assert fetched.size_mm == Decimal("750.00")
    assert fetched.spread_at_issue_bps == Decimal("125.00")
    assert fetched.initial_talk_bps == Decimal("135.00")
    assert fetched.rating == "BBB+"
    assert fetched.use_of_proceeds == "GENERAL_CORPORATE"
    assert fetched.oversubscribed is True
    assert fetched.source_url == "https://example.com/issuance"


@pytest.mark.asyncio
async def test_issuance_entity_fk(session):
    """Verify issuance event FK relationship to Entity."""
    entity = await _seed_entity(session)
    iid = uuid.uuid4()
    session.add(NewIssuanceEvent(
        id=iid,
        entity_id=entity.entity_id,
        issue_date=date(2025, 8, 1),
        size_mm=Decimal("500.00"),
    ))
    await session.flush()

    result = await session.execute(
        select(NewIssuanceEvent).where(NewIssuanceEvent.id == iid)
    )
    fetched = result.scalar_one()
    assert fetched.entity_id == entity.entity_id


@pytest.mark.asyncio
async def test_issuance_oversubscribed_default(session):
    """Verify oversubscribed defaults to False."""
    iid = uuid.uuid4()
    session.add(NewIssuanceEvent(
        id=iid,
        issue_date=date(2025, 8, 5),
    ))
    await session.flush()

    result = await session.execute(
        select(NewIssuanceEvent).where(NewIssuanceEvent.id == iid)
    )
    fetched = result.scalar_one()
    assert fetched.oversubscribed is False


# ── CrossAssetSignal Tests ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_cross_asset_signal(session):
    """Create a cross-asset signal with all fields."""
    entity = await _seed_entity(session)
    sid = uuid.uuid4()
    signal = CrossAssetSignal(
        id=sid,
        entity_id=entity.entity_id,
        signal_date=date(2025, 7, 25),
        signal_type="DIVERGENCE",
        equity_return_pct=Decimal("5.2300"),
        spread_change_bps=Decimal("-15.00"),
        severity="HIGH",
        narrative="Equity rallied while credit spreads widened.",
        ai_enabled=True,
    )
    session.add(signal)
    await session.flush()

    result = await session.execute(
        select(CrossAssetSignal).where(CrossAssetSignal.id == sid)
    )
    fetched = result.scalar_one()
    assert fetched.entity_id == entity.entity_id
    assert fetched.signal_date == date(2025, 7, 25)
    assert fetched.signal_type == "DIVERGENCE"
    assert fetched.equity_return_pct == Decimal("5.2300")
    assert fetched.spread_change_bps == Decimal("-15.00")
    assert fetched.severity == "HIGH"
    assert fetched.narrative == "Equity rallied while credit spreads widened."
    assert fetched.ai_enabled is True


@pytest.mark.asyncio
async def test_cross_asset_signal_entity_fk(session):
    """Verify cross-asset signal FK to Entity."""
    entity = await _seed_entity(session)
    sid = uuid.uuid4()
    session.add(CrossAssetSignal(
        id=sid,
        entity_id=entity.entity_id,
        signal_date=date(2025, 8, 1),
        signal_type="BOND_EQUITY_DIVERGENCE",
    ))
    await session.flush()

    result = await session.execute(
        select(CrossAssetSignal).where(CrossAssetSignal.id == sid)
    )
    fetched = result.scalar_one()
    assert fetched.entity_id == entity.entity_id
    assert fetched.signal_type == "BOND_EQUITY_DIVERGENCE"


@pytest.mark.asyncio
async def test_cross_asset_signal_defaults(session):
    """Verify ai_enabled defaults to False."""
    entity = await _seed_entity(session)
    sid = uuid.uuid4()
    session.add(CrossAssetSignal(
        id=sid,
        entity_id=entity.entity_id,
        signal_date=date(2025, 9, 1),
    ))
    await session.flush()

    result = await session.execute(
        select(CrossAssetSignal).where(CrossAssetSignal.id == sid)
    )
    fetched = result.scalar_one()
    assert fetched.ai_enabled is False


# ── FIAlertConfig Tests ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_fi_alert_config(session):
    """Create a FI alert config with all fields."""
    aid = uuid.uuid4()
    config = FIAlertConfig(
        id=aid,
        user_id="user-123",
        alert_type="SPREAD_MOVE",
        is_enabled=True,
        threshold_value=Decimal("25.00"),
        entity_scope={"sectors": ["TECH", "ENERGY"]},
    )
    session.add(config)
    await session.flush()

    result = await session.execute(
        select(FIAlertConfig).where(FIAlertConfig.id == aid)
    )
    fetched = result.scalar_one()
    assert fetched.user_id == "user-123"
    assert fetched.alert_type == "SPREAD_MOVE"
    assert fetched.is_enabled is True
    assert fetched.threshold_value == Decimal("25.00")
    assert fetched.entity_scope == {"sectors": ["TECH", "ENERGY"]}


@pytest.mark.asyncio
async def test_fi_alert_config_jsonb_roundtrip(session):
    """Round-trip JSONB entity_scope."""
    aid = uuid.uuid4()
    scope = {"entity_id": str(uuid.uuid4()), "watchlist": "FI_PORTFOLIO"}
    session.add(FIAlertConfig(
        id=aid,
        user_id="user-456",
        alert_type="QUALITY_SCORE",
        entity_scope=scope,
    ))
    await session.flush()

    result = await session.execute(
        select(FIAlertConfig).where(FIAlertConfig.id == aid)
    )
    fetched = result.scalar_one()
    assert fetched.entity_scope == scope
    assert fetched.entity_scope["watchlist"] == "FI_PORTFOLIO"


@pytest.mark.asyncio
async def test_fi_alert_config_default_enabled(session):
    """Verify is_enabled defaults to True."""
    aid = uuid.uuid4()
    session.add(FIAlertConfig(
        id=aid,
        user_id="user-789",
        alert_type="INSTITUTIONAL_FLOW",
    ))
    await session.flush()

    result = await session.execute(
        select(FIAlertConfig).where(FIAlertConfig.id == aid)
    )
    fetched = result.scalar_one()
    assert fetched.is_enabled is True
