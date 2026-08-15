"""Tests for src/ai/narratives/commodity.py (§4.7: commodity news/
supply-demand narrative to complement FRED prices)."""
from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest

from src.ai.narratives.commodity import (
    assemble_commodity_context,
    generate_commodity_narrative,
    get_or_compute_commodity_narrative,
)
from src.models.commodity_intelligence import CommodityInventory, CommodityPrice, CommodityProfile
from src.models.news_article import NewsArticle
from src.models.pillar3_narratives import CommodityNarrative


class FakeTextClient:
    def __init__(self, *, enabled: bool = True, text: str | None = "Crude oil rose 5% this week."):
        self.enabled = enabled
        self._text = text
        self.calls: list[dict] = []

    async def complete_text(self, **kwargs):
        self.calls.append(kwargs)
        return self._text


async def _seed_profile(session, code="WTI", **kwargs) -> CommodityProfile:
    defaults = dict(id=uuid.uuid4(), commodity_code=code, commodity_name="WTI Crude Oil", unit="USD/barrel")
    defaults.update(kwargs)
    p = CommodityProfile(**defaults)
    session.add(p)
    await session.flush()
    return p


async def _seed_price(session, code, price_date, close, **kwargs) -> CommodityPrice:
    defaults = dict(id=uuid.uuid4(), commodity_code=code, price_date=price_date, close_price=Decimal(str(close)))
    defaults.update(kwargs)
    row = CommodityPrice(**defaults)
    session.add(row)
    await session.flush()
    return row


async def _seed_inventory(session, code, as_of_date, stock_level, **kwargs) -> CommodityInventory:
    defaults = dict(
        id=uuid.uuid4(), commodity_code=code, as_of_date=as_of_date,
        stock_level=Decimal(str(stock_level)), stock_unit="thousand barrels", metric_name="Crude Stocks",
    )
    defaults.update(kwargs)
    row = CommodityInventory(**defaults)
    session.add(row)
    await session.flush()
    return row


async def _seed_article(session, *, title, summary="Summary.", topics=None, publish_date=None, source_url=None) -> NewsArticle:
    a = NewsArticle(
        id=uuid.uuid4(), source_url=source_url or f"https://reuters.com/{uuid.uuid4()}",
        title=title, summary=summary, source_name="Reuters",
        publish_date=publish_date or date.today(), ingest_date=publish_date or date.today(),
        topics=topics,
    )
    session.add(a)
    await session.flush()
    return a


@pytest.mark.asyncio
class TestAssembleCommodityContext:

    async def test_no_price_data_returns_none(self, session):
        await _seed_profile(session, code="XAU")
        result = await assemble_commodity_context(session, "XAU")
        assert result is None

    async def test_computes_pct_change_over_period(self, session):
        await _seed_profile(session, code="WTI")
        today = date.today()
        await _seed_price(session, "WTI", today - timedelta(days=1), 80.0)
        await _seed_price(session, "WTI", today, 88.0)

        result = await assemble_commodity_context(session, "WTI")
        assert result.latest_price == 88.0
        assert result.pct_change_period == 10.0
        assert result.period_days == 2

    async def test_includes_latest_inventory(self, session):
        await _seed_profile(session, code="WTI")
        await _seed_price(session, "WTI", date.today(), 80.0)
        await _seed_inventory(session, "WTI", date.today(), 420000)

        result = await assemble_commodity_context(session, "WTI")
        assert result.inventory["stock_level"] == 420000.0
        assert result.inventory["stock_unit"] == "thousand barrels"

    async def test_no_profile_falls_back_to_code_as_name(self, session):
        await _seed_price(session, "XYZ", date.today(), 10.0)
        result = await assemble_commodity_context(session, "XYZ")
        assert result.commodity_name == "XYZ"
        assert result.unit is None

    async def test_matches_commodity_tagged_news_by_name(self, session):
        await _seed_profile(session, code="WTI")
        await _seed_price(session, "WTI", date.today(), 80.0)
        await _seed_article(
            session, title="WTI Crude Oil prices surge on OPEC cut",
            topics=["COMMODITY", "PRICING"],
        )
        await _seed_article(
            session, title="Unrelated tech earnings beat",
            topics=["EARNINGS"],
        )

        result = await assemble_commodity_context(session, "WTI")
        assert len(result.news_headlines) == 1
        assert "WTI Crude Oil" in result.news_headlines[0]

    async def test_ignores_commodity_tagged_article_with_no_name_match(self, session):
        await _seed_profile(session, code="WTI")
        await _seed_price(session, "WTI", date.today(), 80.0)
        await _seed_article(session, title="Gold prices hit record high", topics=["COMMODITY"])

        result = await assemble_commodity_context(session, "WTI")
        assert result.news_headlines == []

    async def test_ignores_matching_article_without_commodity_topic(self, session):
        await _seed_profile(session, code="WTI")
        await _seed_price(session, "WTI", date.today(), 80.0)
        await _seed_article(session, title="WTI Crude Oil producer announces layoffs", topics=["RESTRUCTURING"])

        result = await assemble_commodity_context(session, "WTI")
        assert result.news_headlines == []


@pytest.mark.asyncio
class TestGenerateCommodityNarrative:

    async def test_renders_context_and_returns_text(self, session):
        await _seed_profile(session, code="WTI")
        await _seed_price(session, "WTI", date.today(), 80.0)
        context = await assemble_commodity_context(session, "WTI")
        client = FakeTextClient(text="Crude rose on tight supply.")

        result = await generate_commodity_narrative(client, context)

        assert result == "Crude rose on tight supply."
        assert len(client.calls) == 1
        assert client.calls[0]["feature"] == "commodity_narrative"
        assert "WTI Crude Oil" in client.calls[0]["user"]


@pytest.mark.asyncio
class TestGetOrComputeCommodityNarrative:

    async def test_returns_none_when_ai_disabled_and_no_cache(self, session):
        await _seed_profile(session, code="WTI")
        await _seed_price(session, "WTI", date.today(), 80.0)
        client = FakeTextClient(enabled=False)

        result = await get_or_compute_commodity_narrative(session, client, "WTI")
        assert result is None

    async def test_returns_none_when_no_price_data(self, session):
        client = FakeTextClient(enabled=True)
        result = await get_or_compute_commodity_narrative(session, client, "NOPRICEDATA")
        assert result is None
        assert client.calls == []

    async def test_computes_and_persists_on_miss(self, session):
        await _seed_profile(session, code="WTI")
        await _seed_price(session, "WTI", date.today(), 80.0)
        client = FakeTextClient(text="Crude rose this week.")

        row = await get_or_compute_commodity_narrative(session, client, "WTI")

        assert row is not None
        assert row.narrative == "Crude rose this week."
        assert row.commodity_code == "WTI"
        assert row.as_of_date == date.today()
        assert row.price_summary["latest_price"] == 80.0
        assert row.model is not None

    async def test_cache_hit_skips_client_call(self, session):
        await _seed_profile(session, code="WTI")
        await _seed_price(session, "WTI", date.today(), 80.0)
        session.add(CommodityNarrative(
            id=uuid.uuid4(), commodity_code="WTI", as_of_date=date.today(),
            narrative="Already computed.",
        ))
        await session.flush()
        client = FakeTextClient()

        row = await get_or_compute_commodity_narrative(session, client, "WTI")

        assert row.narrative == "Already computed."
        assert client.calls == []

    async def test_force_refresh_bypasses_cache(self, session):
        await _seed_profile(session, code="WTI")
        await _seed_price(session, "WTI", date.today(), 80.0)
        session.add(CommodityNarrative(
            id=uuid.uuid4(), commodity_code="WTI", as_of_date=date.today(),
            narrative="Stale narrative.",
        ))
        await session.flush()
        client = FakeTextClient(text="Fresh narrative.")

        row = await get_or_compute_commodity_narrative(session, client, "WTI", force_refresh=True)

        assert row.narrative == "Fresh narrative."
        assert len(client.calls) == 1

    async def test_none_response_from_client_returns_none(self, session):
        await _seed_profile(session, code="WTI")
        await _seed_price(session, "WTI", date.today(), 80.0)
        client = FakeTextClient(text=None)

        result = await get_or_compute_commodity_narrative(session, client, "WTI")
        assert result is None
