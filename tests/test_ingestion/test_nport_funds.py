"""Tests for the SEC EDGAR N-PORT fund-holdings connector.

Exercises the namespace-agnostic XML parse, transform and the DB load of Fund +
FundHolding rows against a small representative N-PORT sample. No network.
"""

import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select

from src.ingestion.edgar_nport_funds import (
    EdgarNportFundsConnector,
    parse_nport_xml,
)

# Small representative N-PORT document, with the real SEC namespace, two
# holdings. Trimmed to the elements the connector reads.
SAMPLE_NPORT_XML = """<?xml version="1.0" encoding="UTF-8"?>
<edgarSubmission xmlns="http://www.sec.gov/edgar/nport">
  <formData>
    <genInfo>
      <seriesName>Example Growth ETF</seriesName>
      <seriesId>S000012345</seriesId>
      <repPdDate>2024-06-30</repPdDate>
    </genInfo>
    <fundInfo>
      <totAssets>1000000000.00</totAssets>
    </fundInfo>
    <invstOrSecs>
      <invstOrSec>
        <name>APPLE INC</name>
        <cusip>037833100</cusip>
        <identifiers><isin value="US0378331005"/></identifiers>
        <balance>100000.0000</balance>
        <valUSD>19000000.00</valUSD>
        <pctVal>1.9000</pctVal>
        <assetCat>EC</assetCat>
      </invstOrSec>
      <invstOrSec>
        <name>MICROSOFT CORP</name>
        <cusip>594918104</cusip>
        <identifiers><isin value="US5949181045"/></identifiers>
        <balance>50000.0000</balance>
        <valUSD>21000000.00</valUSD>
        <pctVal>2.1000</pctVal>
        <assetCat>EC</assetCat>
      </invstOrSec>
    </invstOrSecs>
  </formData>
</edgarSubmission>
"""


def test_parse_nport_xml():
    parsed = parse_nport_xml(SAMPLE_NPORT_XML)
    assert parsed is not None
    assert parsed["fund"]["fund_name"] == "Example Growth ETF"
    assert parsed["fund"]["series_id"] == "S000012345"
    assert parsed["fund"]["report_date"] == "2024-06-30"
    assert parsed["fund"]["total_net_assets"] == Decimal("1000000000.00")
    assert parsed["fund"]["number_of_holdings"] == 2
    h0 = parsed["holdings"][0]
    assert h0["security_name"] == "APPLE INC"
    assert h0["cusip"] == "037833100"
    assert h0["isin"] == "US0378331005"
    assert h0["market_value"] == Decimal("19000000.00")
    assert h0["pct_of_nav"] == Decimal("1.9000")


def test_parse_nport_no_holdings_returns_none():
    xml = '<edgarSubmission xmlns="http://www.sec.gov/edgar/nport"><formData><genInfo><seriesName>X</seriesName></genInfo></formData></edgarSubmission>'
    assert parse_nport_xml(xml) is None


@pytest.mark.asyncio
async def test_load_creates_fund_and_holdings(session):
    conn = EdgarNportFundsConnector()
    parsed = parse_nport_xml(SAMPLE_NPORT_XML)
    parsed["cik"] = "0001111111"
    parsed["accession_number"] = "0001111111-24-000001"
    recs = await conn.transform(await conn.validate([parsed]))
    stats = await conn.load(recs, session)
    assert stats["inserted"] == 2  # two holdings
    await session.flush()

    from src.models.fund_holdings import Fund, FundHolding

    funds = (await session.execute(select(Fund))).scalars().all()
    holdings = (await session.execute(select(FundHolding))).scalars().all()
    assert len(funds) == 1
    assert funds[0].fund_name == "Example Growth ETF"
    assert funds[0].number_of_holdings == 2
    assert len(holdings) == 2
    assert all(h.report_date == date(2024, 6, 30) for h in holdings)

    # Re-load is idempotent (holdings de-duped).
    stats2 = await conn.load(recs, session)
    assert stats2["inserted"] == 0
    assert stats2["skipped"] == 2
