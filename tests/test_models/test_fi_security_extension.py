"""Tests for D11 FI Supplement Part 1: Security extension + FI enums."""

import uuid
from datetime import date

import pytest
from sqlalchemy import select

from src.models.security import Security, FixedIncomeDetails

# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------
from src.enums import (
    TreasuryType,
    BondStatus,
    TradeReportType,
    AgencyType,
    BackingType,
    LiquidityTier,
    UseOfProceedsCategory,
    CreditSpreadRegime,
)


class TestTreasuryType:
    def test_values(self):
        assert TreasuryType.BILL == "BILL"
        assert TreasuryType.NOTE == "NOTE"
        assert TreasuryType.BOND == "BOND"
        assert TreasuryType.TIPS == "TIPS"
        assert TreasuryType.FRN == "FRN"
        assert TreasuryType.STRIP == "STRIP"

    def test_count(self):
        assert len(TreasuryType) == 6

    def test_str(self):
        assert str(TreasuryType.BILL) == "TreasuryType.BILL"


class TestBondStatus:
    def test_values(self):
        assert BondStatus.OUTSTANDING == "OUTSTANDING"
        assert BondStatus.MATURED == "MATURED"
        assert BondStatus.CALLED == "CALLED"
        assert BondStatus.DEFAULTED == "DEFAULTED"
        assert BondStatus.DEFEASED == "DEFEASED"
        assert BondStatus.EXCHANGED == "EXCHANGED"

    def test_count(self):
        assert len(BondStatus) == 6


class TestTradeReportType:
    def test_values(self):
        assert TradeReportType.CUSTOMER_BUY == "CUSTOMER_BUY"
        assert TradeReportType.CUSTOMER_SELL == "CUSTOMER_SELL"
        assert TradeReportType.INTERDEALER == "INTERDEALER"

    def test_count(self):
        assert len(TradeReportType) == 3


class TestAgencyType:
    def test_all_agencies(self):
        assert AgencyType.FNMA == "FNMA"
        assert AgencyType.FHLMC == "FHLMC"
        assert AgencyType.FHLB == "FHLB"
        assert AgencyType.FFCB == "FFCB"
        assert AgencyType.TVA == "TVA"
        assert AgencyType.SBA == "SBA"
        assert AgencyType.GNMA == "GNMA"

    def test_count(self):
        assert len(AgencyType) == 7


class TestBackingType:
    def test_values(self):
        assert BackingType.EXPLICIT_GUARANTEE == "EXPLICIT_GUARANTEE"
        assert BackingType.CONSERVATORSHIP == "CONSERVATORSHIP"
        assert BackingType.IMPLICIT_SUPPORT == "IMPLICIT_SUPPORT"

    def test_count(self):
        assert len(BackingType) == 3


class TestLiquidityTier:
    def test_values(self):
        assert LiquidityTier.ON_THE_RUN == "ON_THE_RUN"
        assert LiquidityTier.OFF_THE_RUN == "OFF_THE_RUN"
        assert LiquidityTier.ILLIQUID == "ILLIQUID"


class TestUseOfProceedsCategory:
    def test_values(self):
        expected = {
            "GENERAL_CORPORATE", "REFINANCING", "ACQUISITION",
            "CAPEX", "GREEN_BOND", "SOCIAL_BOND", "WORKING_CAPITAL",
        }
        actual = {e.value for e in UseOfProceedsCategory}
        assert actual == expected


class TestCreditSpreadRegime:
    def test_values(self):
        assert CreditSpreadRegime.TIGHT == "TIGHT"
        assert CreditSpreadRegime.NORMAL == "NORMAL"
        assert CreditSpreadRegime.WIDE == "WIDE"
        assert CreditSpreadRegime.CRISIS == "CRISIS"


# ---------------------------------------------------------------------------
# Security model extension tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_security_corporate_bond_cusip(session):
    """Security can store a corporate bond CUSIP reference."""
    sec = Security(
        security_type="CORPORATE_BOND",
        name="Apple Inc 3.85% 2043",
        status="ACTIVE",
        asset_class="FIXED_INCOME",
        corporate_bond_cusip="037833AK6",
    )
    session.add(sec)
    await session.flush()

    result = await session.get(Security, sec.security_id)
    assert result is not None
    assert result.corporate_bond_cusip == "037833AK6"
    assert result.treasury_cusip is None


@pytest.mark.asyncio
async def test_security_treasury_cusip(session):
    """Security can store a Treasury CUSIP reference."""
    sec = Security(
        security_type="US_TREASURY",
        name="US Treasury 10Y Note",
        status="ACTIVE",
        asset_class="FIXED_INCOME",
        treasury_cusip="91282CHT1",
    )
    session.add(sec)
    await session.flush()

    result = await session.get(Security, sec.security_id)
    assert result is not None
    assert result.treasury_cusip == "91282CHT1"
    assert result.corporate_bond_cusip is None


@pytest.mark.asyncio
async def test_security_cusip_columns_nullable(session):
    """CUSIP columns are nullable — equity securities don't have them."""
    sec = Security(
        security_type="COMMON_STOCK",
        name="Apple Inc",
        status="ACTIVE",
        asset_class="EQUITY",
    )
    session.add(sec)
    await session.flush()

    result = await session.get(Security, sec.security_id)
    assert result.corporate_bond_cusip is None
    assert result.treasury_cusip is None


@pytest.mark.asyncio
async def test_fixed_income_details_d11_extensions(session):
    """FixedIncomeDetails stores D11 extension fields."""
    sec = Security(
        security_type="CORPORATE_BOND",
        name="Test Bond",
        status="ACTIVE",
        asset_class="FIXED_INCOME",
    )
    session.add(sec)
    await session.flush()

    fi = FixedIncomeDetails(
        security_id=sec.security_id,
        coupon_rate=3.85,
        coupon_type="FIXED",
        seniority="SENIOR_UNSECURED",
        use_of_proceeds="REFINANCING",
        liquidity_tier="OFF_THE_RUN",
        benchmark_treasury_cusip="91282CHT1",
        oas_bps=125.50,
    )
    session.add(fi)
    await session.flush()

    result = await session.get(FixedIncomeDetails, sec.security_id)
    assert result is not None
    assert result.use_of_proceeds == "REFINANCING"
    assert result.liquidity_tier == "OFF_THE_RUN"
    assert result.benchmark_treasury_cusip == "91282CHT1"
    assert float(result.oas_bps) == pytest.approx(125.50, abs=0.01)


@pytest.mark.asyncio
async def test_fixed_income_details_d11_extensions_nullable(session):
    """D11 extension fields are nullable."""
    sec = Security(
        security_type="CORPORATE_BOND",
        name="Test Bond 2",
        status="ACTIVE",
        asset_class="FIXED_INCOME",
    )
    session.add(sec)
    await session.flush()

    fi = FixedIncomeDetails(
        security_id=sec.security_id,
        coupon_rate=4.0,
    )
    session.add(fi)
    await session.flush()

    result = await session.get(FixedIncomeDetails, sec.security_id)
    assert result.use_of_proceeds is None
    assert result.liquidity_tier is None
    assert result.benchmark_treasury_cusip is None
    assert result.oas_bps is None
