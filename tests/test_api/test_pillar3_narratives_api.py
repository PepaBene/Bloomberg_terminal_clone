"""API tests for src/api/routers/pillar3_narratives.py (§4.7).

No live ANTHROPIC_API_KEY in the test env, so these exercise the
not-yet-cached (AI disabled -> 404) and already-cached (seeded narrative
row -> served without needing AI) paths -- the AI computation path itself
is covered by tests/test_ai/test_narratives_commodity.py and
test_narratives_insider.py's fake-client tests.
"""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.commodity_intelligence import CommodityPrice
from src.models.entity import Entity
from src.models.pillar3_narratives import CommodityNarrative, InsiderNarrative


@pytest.mark.asyncio
async def test_commodity_narrative_404_when_no_price_data(client: AsyncClient):
    resp = await client.get("/v5/commodities/NOSUCHCODE/narrative")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_commodity_narrative_404_when_ai_disabled_and_no_cache(client: AsyncClient, session: AsyncSession):
    code = f"WTI-{uuid.uuid4().hex[:8].upper()}"
    session.add(CommodityPrice(
        id=uuid.uuid4(), commodity_code=code, price_date=date.today(), close_price=Decimal("80.00"),
    ))
    await session.commit()

    resp = await client.get(f"/v5/commodities/{code}/narrative")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_commodity_narrative_served_from_cache(client: AsyncClient, session: AsyncSession):
    code = f"WTI-{uuid.uuid4().hex[:8].upper()}"
    session.add(CommodityPrice(
        id=uuid.uuid4(), commodity_code=code, price_date=date.today(), close_price=Decimal("80.00"),
    ))
    session.add(CommodityNarrative(
        id=uuid.uuid4(), commodity_code=code, as_of_date=date.today(),
        narrative="Crude rose this week on tight supply.",
    ))
    await session.commit()

    resp = await client.get(f"/v5/commodities/{code}/narrative")
    assert resp.status_code == 200
    body = resp.json()
    assert body["narrative"] == "Crude rose this week on tight supply."
    assert body["commodity_code"] == code


@pytest.mark.asyncio
async def test_commodity_narrative_uppercases_code(client: AsyncClient, session: AsyncSession):
    code = f"WTI{uuid.uuid4().hex[:8].upper()}"
    session.add(CommodityPrice(
        id=uuid.uuid4(), commodity_code=code, price_date=date.today(), close_price=Decimal("80.00"),
    ))
    session.add(CommodityNarrative(
        id=uuid.uuid4(), commodity_code=code, as_of_date=date.today(), narrative="Cached.",
    ))
    await session.commit()

    resp = await client.get(f"/v5/commodities/{code.lower()}/narrative")
    assert resp.status_code == 200
    assert resp.json()["commodity_code"] == code


@pytest.mark.asyncio
async def test_insider_narrative_404_for_unknown_entity(client: AsyncClient):
    resp = await client.get(f"/v5/entities/{uuid.uuid4()}/insider-narrative")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_insider_narrative_404_when_ai_disabled_and_no_cache(client: AsyncClient, session: AsyncSession):
    entity_id = uuid.uuid4()
    session.add(Entity(
        entity_id=entity_id, entity_type="PUBLIC_COMPANY", legal_name="Acme Corp",
        status="ACTIVE", source="TEST",
    ))
    await session.commit()

    resp = await client.get(f"/v5/entities/{entity_id}/insider-narrative")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_insider_narrative_served_from_cache(client: AsyncClient, session: AsyncSession):
    entity_id = uuid.uuid4()
    session.add(Entity(
        entity_id=entity_id, entity_type="PUBLIC_COMPANY", legal_name="Acme Corp",
        status="ACTIVE", source="TEST",
    ))
    session.add(InsiderNarrative(
        id=uuid.uuid4(), entity_id=entity_id, as_of_date=date.today(),
        narrative="Insiders net-bought this quarter.",
    ))
    await session.commit()

    resp = await client.get(f"/v5/entities/{entity_id}/insider-narrative")
    assert resp.status_code == 200
    body = resp.json()
    assert body["narrative"] == "Insiders net-bought this quarter."
    assert body["entity_id"] == str(entity_id)
