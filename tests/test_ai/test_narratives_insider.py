"""Tests for src/ai/narratives/insider.py (§4.7: narrative around Form 4
/ congressional disclosures; corroborating news)."""
from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest

from src.ai.narratives.insider import (
    assemble_insider_context,
    generate_insider_narrative,
    get_or_compute_insider_narrative,
)
from src.models.congressional_trades import CongressionalTrade
from src.models.entity import Entity
from src.models.insider_intelligence import InsiderSignal
from src.models.pillar3_narratives import InsiderNarrative
from src.models.security import Security, SecurityIdentifier


class FakeTextClient:
    def __init__(self, *, enabled: bool = True, text: str | None = "Insiders net-bought this quarter."):
        self.enabled = enabled
        self._text = text
        self.calls: list[dict] = []

    async def complete_text(self, **kwargs):
        self.calls.append(kwargs)
        return self._text


async def _seed_entity(session, name="Acme Corp") -> Entity:
    e = Entity(entity_id=uuid.uuid4(), entity_type="PUBLIC_COMPANY", legal_name=name, status="ACTIVE", source="TEST")
    session.add(e)
    await session.flush()
    return e


async def _seed_ticker(session, entity: Entity, ticker: str) -> Security:
    security = Security(
        security_id=uuid.uuid4(), security_type="EQUITY", issuer_entity_id=entity.entity_id,
        name=entity.legal_name, status="ACTIVE", asset_class="EQUITY",
    )
    session.add(security)
    await session.flush()
    session.add(SecurityIdentifier(
        id=uuid.uuid4(), security_id=security.security_id, identifier_type="TICKER", identifier_value=ticker,
    ))
    await session.flush()
    return security


async def _seed_signal(session, entity_id, *, signal_type="OPEN_MARKET_BUY", signal_date=None, **kwargs) -> InsiderSignal:
    defaults = dict(
        id=uuid.uuid4(), entity_id=entity_id, signal_date=signal_date or date.today(),
        signal_type=signal_type, signal_strength=5,
        net_value_30d=Decimal("500000"), insider_count_buying_30d=3, insider_count_selling_30d=0,
    )
    defaults.update(kwargs)
    row = InsiderSignal(**defaults)
    session.add(row)
    await session.flush()
    return row


async def _seed_congressional_trade(session, ticker, *, transaction_date=None, **kwargs) -> CongressionalTrade:
    defaults = dict(
        id=uuid.uuid4(), politician_name="Jane Legislator", ticker=ticker,
        transaction_type="BUY", transaction_date=transaction_date or date.today(),
        amount_range_low=Decimal("15001"), amount_range_high=Decimal("50000"),
    )
    defaults.update(kwargs)
    row = CongressionalTrade(**defaults)
    session.add(row)
    await session.flush()
    return row


@pytest.mark.asyncio
class TestAssembleInsiderContext:

    async def test_unknown_entity_returns_none(self, session):
        result = await assemble_insider_context(session, uuid.uuid4())
        assert result is None

    async def test_no_data_returns_none(self, session):
        entity = await _seed_entity(session)
        result = await assemble_insider_context(session, entity.entity_id)
        assert result is None

    async def test_includes_insider_signal(self, session):
        entity = await _seed_entity(session)
        await _seed_signal(session, entity.entity_id, net_value_30d=Decimal("750000"))

        result = await assemble_insider_context(session, entity.entity_id)
        assert result.company_name == "Acme Corp"
        assert len(result.signals) == 1
        assert result.signals[0]["net_value_30d"] == 750000.0

    async def test_dedups_to_latest_per_signal_type(self, session):
        entity = await _seed_entity(session)
        await _seed_signal(
            session, entity.entity_id, signal_type="OPEN_MARKET_BUY",
            signal_date=date.today() - timedelta(days=10), net_value_30d=Decimal("100"),
        )
        await _seed_signal(
            session, entity.entity_id, signal_type="OPEN_MARKET_BUY",
            signal_date=date.today(), net_value_30d=Decimal("999"),
        )

        result = await assemble_insider_context(session, entity.entity_id)
        assert len(result.signals) == 1
        assert result.signals[0]["net_value_30d"] == 999.0

    async def test_includes_congressional_trades_via_ticker_resolution(self, session):
        entity = await _seed_entity(session)
        await _seed_ticker(session, entity, "ACME")
        await _seed_congressional_trade(session, "ACME")

        result = await assemble_insider_context(session, entity.entity_id)
        assert result.ticker == "ACME"
        assert len(result.congressional_trades) == 1
        assert result.congressional_trades[0]["politician_name"] == "Jane Legislator"

    async def test_no_ticker_skips_congressional_lookup(self, session):
        entity = await _seed_entity(session)
        await _seed_signal(session, entity.entity_id)

        result = await assemble_insider_context(session, entity.entity_id)
        assert result.ticker is None
        assert result.congressional_trades == []

    async def test_congressional_trades_for_different_ticker_excluded(self, session):
        entity = await _seed_entity(session)
        await _seed_ticker(session, entity, "ACME")
        await _seed_signal(session, entity.entity_id)
        await _seed_congressional_trade(session, "OTHERCO")

        result = await assemble_insider_context(session, entity.entity_id)
        assert result.congressional_trades == []


@pytest.mark.asyncio
class TestGenerateInsiderNarrative:

    async def test_renders_context_and_returns_text(self, session):
        entity = await _seed_entity(session)
        await _seed_signal(session, entity.entity_id)
        context = await assemble_insider_context(session, entity.entity_id)
        client = FakeTextClient(text="Insiders bought aggressively.")

        result = await generate_insider_narrative(client, context)

        assert result == "Insiders bought aggressively."
        assert client.calls[0]["feature"] == "insider_narrative"
        assert "Acme Corp" in client.calls[0]["user"]


@pytest.mark.asyncio
class TestGetOrComputeInsiderNarrative:

    async def test_returns_none_for_unknown_entity(self, session):
        client = FakeTextClient(enabled=True)
        result = await get_or_compute_insider_narrative(session, client, uuid.uuid4())
        assert result is None
        assert client.calls == []

    async def test_returns_none_when_ai_disabled_and_no_cache(self, session):
        entity = await _seed_entity(session)
        await _seed_signal(session, entity.entity_id)
        client = FakeTextClient(enabled=False)

        result = await get_or_compute_insider_narrative(session, client, entity.entity_id)
        assert result is None

    async def test_computes_and_persists_on_miss(self, session):
        entity = await _seed_entity(session)
        await _seed_signal(session, entity.entity_id)
        client = FakeTextClient(text="Net insider buying this month.")

        row = await get_or_compute_insider_narrative(session, client, entity.entity_id)

        assert row is not None
        assert row.narrative == "Net insider buying this month."
        assert row.entity_id == entity.entity_id
        assert row.as_of_date == date.today()
        assert row.signal_summary["signals"]

    async def test_cache_hit_skips_client_call(self, session):
        entity = await _seed_entity(session)
        await _seed_signal(session, entity.entity_id)
        session.add(InsiderNarrative(
            id=uuid.uuid4(), entity_id=entity.entity_id, as_of_date=date.today(),
            narrative="Already computed.",
        ))
        await session.flush()
        client = FakeTextClient()

        row = await get_or_compute_insider_narrative(session, client, entity.entity_id)

        assert row.narrative == "Already computed."
        assert client.calls == []

    async def test_force_refresh_updates_existing_row(self, session):
        entity = await _seed_entity(session)
        await _seed_signal(session, entity.entity_id)
        session.add(InsiderNarrative(
            id=uuid.uuid4(), entity_id=entity.entity_id, as_of_date=date.today(),
            narrative="Stale.",
        ))
        await session.flush()
        client = FakeTextClient(text="Fresh.")

        row = await get_or_compute_insider_narrative(session, client, entity.entity_id, force_refresh=True)

        assert row.narrative == "Fresh."
        assert len(client.calls) == 1

    async def test_none_response_from_client_returns_none(self, session):
        entity = await _seed_entity(session)
        await _seed_signal(session, entity.entity_id)
        client = FakeTextClient(text=None)

        result = await get_or_compute_insider_narrative(session, client, entity.entity_id)
        assert result is None
