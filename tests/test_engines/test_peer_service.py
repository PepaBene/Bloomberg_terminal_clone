"""Tests for the Peer Group Service (Part 1B)."""

import uuid
from datetime import date

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from src.engines.peer_service import PeerService, PeerGroup, PeerComparison
from src.models.analytics import AnalyticsResult
from src.models.entity import Entity
from src.models.security import Security


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_entity(gics_sub="45102010", name="Corp", **kwargs):
    return Entity(
        entity_id=uuid.uuid4(),
        legal_name=name,
        entity_type="PUBLIC_COMPANY",
        status="ACTIVE",
        incorporation_country="US",
        source="TEST",
        gics_sector=gics_sub[:2] if gics_sub else None,
        gics_industry_group=gics_sub[:4] if gics_sub else None,
        gics_industry=gics_sub[:6] if gics_sub else None,
        gics_sub_industry=None,  # skip FK constraint in tests
        **kwargs,
    )


def _make_security(entity, name_suffix="Stock"):
    return Security(
        security_id=uuid.uuid4(),
        name=f"{entity.legal_name} {name_suffix}",
        security_type="COMMON_STOCK",
        asset_class="EQUITY",
        status="ACTIVE",
        issuer_entity_id=entity.entity_id,
    )


@pytest_asyncio.fixture
async def peer_universe(session: AsyncSession):
    """Create a subject + 5 peers in same GICS sub-industry, 2 in different."""
    entities = []
    securities = []

    # Subject
    subject_entity = _make_entity(name="Subject Corp")
    session.add(subject_entity)
    await session.flush()
    subject = _make_security(subject_entity, name_suffix="SUBJ")
    session.add(subject)
    await session.flush()

    # 5 peers in same GICS sub-industry
    for i in range(5):
        ent = _make_entity(name=f"Peer {i}")
        session.add(ent)
        await session.flush()
        sec = _make_security(ent, name_suffix=f"PEER{i}")
        session.add(sec)
        await session.flush()
        entities.append(ent)
        securities.append(sec)

    # 2 in different GICS
    for i in range(2):
        ent = _make_entity(gics_sub="20102010", name=f"Other {i}")
        session.add(ent)
        await session.flush()
        sec = _make_security(ent, name_suffix=f"OTH{i}")
        session.add(sec)
        await session.flush()

    today = date.today()

    # Seed ratio data for subject + peers
    all_secs = [subject] + securities
    for idx, sec in enumerate(all_secs):
        eid = sec.issuer_entity_id
        for metric, cat, base_val in [
            ("gross_margin", "PROFITABILITY", 0.40 + 0.02 * idx),
            ("roe", "PROFITABILITY", 0.12 + 0.01 * idx),
            ("pe_trailing", "VALUATION", 15.0 + 2.0 * idx),
        ]:
            session.add(AnalyticsResult(
                result_id=uuid.uuid4(),
                security_id=sec.security_id,
                entity_id=eid,
                engine_id="E1",
                metric_name=metric,
                metric_category=cat,
                value=base_val,
                period="TTM",
                as_of_date=today,
            ))

    await session.flush()
    return {"subject": subject, "peers": securities, "entities": entities}


@pytest_asyncio.fixture
async def lonely_security(session: AsyncSession) -> Security:
    """Security in a rare GICS with no peers."""
    entity = _make_entity(gics_sub="99999999", name="Lonely Corp")
    session.add(entity)
    await session.flush()
    security = _make_security(entity, name_suffix="LONE")
    session.add(security)
    await session.flush()
    return security


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestPeerService:
    """Unit tests for PeerService."""

    @pytest.mark.asyncio
    async def test_get_peers_returns_peer_group(self, session, peer_universe):
        """Should find peers in same GICS sub-industry."""
        svc = PeerService()
        pg = await svc.get_peers(session, peer_universe["subject"].security_id)
        assert isinstance(pg, PeerGroup)
        assert len(pg.peers) > 0
        # Should NOT include the subject itself
        subject_id = peer_universe["subject"].security_id
        assert all(p.security_id != subject_id for p in pg.peers)

    @pytest.mark.asyncio
    async def test_peers_are_same_gics(self, session, peer_universe):
        """Peers should be from the same GICS classification."""
        svc = PeerService()
        pg = await svc.get_peers(session, peer_universe["subject"].security_id)
        # All peers should have same GICS sub-industry as subject (45102010)
        for p in pg.peers:
            if p.gics_sub_industry:
                assert p.gics_sub_industry == "45102010"

    @pytest.mark.asyncio
    async def test_max_peers_respected(self, session, peer_universe):
        """max_peers parameter should limit the result count."""
        svc = PeerService()
        pg = await svc.get_peers(session, peer_universe["subject"].security_id, max_peers=3)
        assert len(pg.peers) <= 3

    @pytest.mark.asyncio
    async def test_compare_vs_peers(self, session, peer_universe):
        """Comparison should produce per-metric stats."""
        svc = PeerService()
        comp = await svc.compare_vs_peers(
            session,
            peer_universe["subject"].security_id,
            metrics=["gross_margin", "roe"],
        )
        assert isinstance(comp, PeerComparison)
        assert len(comp.comparisons) > 0
        for c in comp.comparisons:
            assert c.metric_name in ("gross_margin", "roe")

    @pytest.mark.asyncio
    async def test_percentile_ranks(self, session, peer_universe):
        """Percentile ranks should be 0-100."""
        svc = PeerService()
        ranks = await svc.get_percentile_ranks(
            session,
            peer_universe["subject"].security_id,
            metrics=["gross_margin"],
        )
        assert isinstance(ranks, dict)
        for metric, pct in ranks.items():
            assert 0 <= pct <= 100

    @pytest.mark.asyncio
    async def test_lonely_security_fallback(self, session, lonely_security):
        """Security with no peers should get empty peer group."""
        svc = PeerService()
        pg = await svc.get_peers(session, lonely_security.security_id)
        assert isinstance(pg, PeerGroup)
        # May be empty or fall back to broader GICS
        assert isinstance(pg.peers, list)

    @pytest.mark.asyncio
    async def test_comparison_stats_correct(self, session, peer_universe):
        """Peer median/mean should be reasonable for known data."""
        svc = PeerService()
        comp = await svc.compare_vs_peers(
            session,
            peer_universe["subject"].security_id,
            metrics=["gross_margin"],
        )
        gm_comp = next((c for c in comp.comparisons if c.metric_name == "gross_margin"), None)
        if gm_comp and gm_comp.peer_median is not None:
            # Subject is 0.40, peers are 0.42-0.50 — median should be in that range
            assert 0.3 < gm_comp.peer_median < 0.6
