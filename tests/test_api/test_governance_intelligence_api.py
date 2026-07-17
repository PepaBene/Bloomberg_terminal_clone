"""API tests for Governance Intelligence endpoints (Pillar 3 Phase 1)."""

import uuid
from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.analytics import AnalyticsResult
from src.models.entity import Entity
from src.models.fundamentals import FinancialPeriod, IncomeStatement
from src.models.governance_intelligence import (
    BoardMember,
    ExecutiveCompensation,
    ProxyFiling,
    ShareholderProposal,
)
from src.models.security import EODPrice, Security


# ── Seed helpers (R-005: board-interlocks / proposals-analysis / pay-alignment) ──


async def _seed_entity(session: AsyncSession) -> Entity:
    entity = Entity(
        entity_id=uuid.uuid4(), entity_type="PUBLIC_COMPANY",
        legal_name="R-005 Test Corp", status="ACTIVE", source="TEST",
    )
    session.add(entity)
    await session.flush()
    return entity


async def _seed_proxy(session: AsyncSession, entity_id) -> ProxyFiling:
    proxy = ProxyFiling(
        id=uuid.uuid4(), entity_id=entity_id, fiscal_year=2024,
        filing_date=date(2025, 4, 15), meeting_date=date(2025, 6, 10),
    )
    session.add(proxy)
    await session.flush()
    return proxy


# ── Tests ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_proxy(client: AsyncClient, session: AsyncSession):
    """GET /v3/filings/{entity_id}/proxy returns 200 or 404."""
    resp = await client.get(f"/v3/filings/{uuid4()}/proxy")
    assert resp.status_code in (200, 404)


@pytest.mark.asyncio
async def test_get_proxy_compensation(client: AsyncClient, session: AsyncSession):
    """GET /v3/filings/{entity_id}/proxy/compensation returns 200 or 404."""
    resp = await client.get(f"/v3/filings/{uuid4()}/proxy/compensation")
    assert resp.status_code in (200, 404)


@pytest.mark.asyncio
async def test_get_proxy_governance(client: AsyncClient, session: AsyncSession):
    """GET /v3/filings/{entity_id}/proxy/governance returns 200 or 404."""
    resp = await client.get(f"/v3/filings/{uuid4()}/proxy/governance")
    assert resp.status_code in (200, 404)


@pytest.mark.asyncio
async def test_get_proxy_red_flags(client: AsyncClient, session: AsyncSession):
    """GET /v3/filings/{entity_id}/proxy/red-flags returns 200 or 404."""
    resp = await client.get(f"/v3/filings/{uuid4()}/proxy/red-flags")
    assert resp.status_code in (200, 404)


@pytest.mark.asyncio
async def test_get_proxy_proposals(client: AsyncClient, session: AsyncSession):
    """GET /v3/filings/{entity_id}/proxy/proposals returns 200 or 404."""
    resp = await client.get(f"/v3/filings/{uuid4()}/proxy/proposals")
    assert resp.status_code in (200, 404)


@pytest.mark.asyncio
async def test_get_proxy_board(client: AsyncClient, session: AsyncSession):
    """GET /v3/filings/{entity_id}/proxy/board returns 200 or 404."""
    resp = await client.get(f"/v3/filings/{uuid4()}/proxy/board")
    assert resp.status_code in (200, 404)


# ── R-005: board-interlocks / proposals-analysis / pay-alignment ─────


@pytest.mark.asyncio
async def test_board_interlocks_no_proxy_404(client: AsyncClient, session: AsyncSession):
    resp = await client.get(f"/v3/filings/{uuid4()}/proxy/board-interlocks")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_board_interlocks_real_data(client: AsyncClient, session: AsyncSession):
    entity = await _seed_entity(session)
    proxy = await _seed_proxy(session, entity.entity_id)
    session.add_all([
        BoardMember(
            id=uuid.uuid4(), proxy_id=proxy.id, entity_id=entity.entity_id,
            person_name="Interlocked Director", other_boards=["OtherCorp Inc.", "TechFirm LLC"],
        ),
        BoardMember(
            id=uuid.uuid4(), proxy_id=proxy.id, entity_id=entity.entity_id,
            person_name="Single-Board Director", other_boards=["OnlyOneCorp"],
        ),
    ])
    await session.commit()

    resp = await client.get(f"/v3/filings/{entity.entity_id}/proxy/board-interlocks")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["person_name"] == "Interlocked Director"
    assert body[0]["interlock_count"] == 2


@pytest.mark.asyncio
async def test_proposals_analysis_real_data(client: AsyncClient, session: AsyncSession):
    entity = await _seed_entity(session)
    proxy = await _seed_proxy(session, entity.entity_id)
    session.add(ShareholderProposal(
        id=uuid.uuid4(), proxy_id=proxy.id, entity_id=entity.entity_id,
        proposal_number=1, topic="ESG", management_recommendation="AGAINST",
        vote_for_pct=Decimal("55.00"), vote_against_pct=Decimal("43.00"), passed=True,
    ))
    await session.commit()

    resp = await client.get(f"/v3/filings/{entity.entity_id}/proxy/proposals/analysis")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_proposals"] == 1
    assert body["avg_support_pct"] == 55.0
    assert body["management_overrides"] == 1


@pytest.mark.asyncio
async def test_pay_alignment_no_ceo_404(client: AsyncClient, session: AsyncSession):
    entity = await _seed_entity(session)
    await _seed_proxy(session, entity.entity_id)
    await session.commit()
    resp = await client.get(f"/v3/filings/{entity.entity_id}/proxy/pay-alignment")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_pay_alignment_real_data(client: AsyncClient, session: AsyncSession):
    entity = await _seed_entity(session)
    proxy = await _seed_proxy(session, entity.entity_id)
    session.add(ExecutiveCompensation(
        id=uuid.uuid4(), proxy_id=proxy.id, entity_id=entity.entity_id,
        person_name="Jane Q. CEO", role="CEO", fiscal_year=2024,
        total_compensation=Decimal("15000000.00"), yoy_change_pct=Decimal("8.0"),
    ))
    security = Security(
        security_id=uuid.uuid4(), name="R-005 Test Corp Common Stock",
        security_type="COMMON_STOCK", asset_class="EQUITY", status="ACTIVE",
        issuer_entity_id=entity.entity_id,
    )
    session.add(security)
    await session.flush()
    session.add(AnalyticsResult(
        result_id=uuid.uuid4(), security_id=security.security_id, entity_id=entity.entity_id,
        engine_id="E1", metric_name="roic", metric_category="PROFITABILITY",
        value=18.0, period="TTM", as_of_date=date.today(),
    ))

    fp_old = FinancialPeriod(
        period_id=uuid.uuid4(), entity_id=entity.entity_id,
        period_end_date=date(2023, 12, 31), period_type="ANNUAL", fiscal_year=2023,
    )
    fp_new = FinancialPeriod(
        period_id=uuid.uuid4(), entity_id=entity.entity_id,
        period_end_date=date(2024, 12, 31), period_type="ANNUAL", fiscal_year=2024,
    )
    session.add_all([fp_old, fp_new])
    await session.flush()
    session.add(IncomeStatement(statement_id=uuid.uuid4(), period_id=fp_old.period_id, total_revenue=500_000_000))
    session.add(IncomeStatement(statement_id=uuid.uuid4(), period_id=fp_new.period_id, total_revenue=600_000_000))

    today = date.today()
    session.add(EODPrice(security_id=security.security_id, price_date=today, close_adjusted=110.0))
    session.add(EODPrice(security_id=security.security_id, price_date=today - timedelta(days=366), close_adjusted=100.0))
    await session.commit()

    resp = await client.get(f"/v3/filings/{entity.entity_id}/proxy/pay-alignment")
    assert resp.status_code == 200
    body = resp.json()
    assert body["metrics"]["roic"] == 18.0
    assert body["metrics"]["revenue_growth_pct"] == 20.0
    assert body["metrics"]["tsr_1y"] == 10.0
    assert body["data_coverage"] == {
        "roic_available": True,
        "revenue_growth_available": True,
        "tsr_1y_available": True,
        "tsr_1y_excludes_dividends": True,
    }
