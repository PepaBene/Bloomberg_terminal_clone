"""API tests for the Complex Financial Structure endpoints.

Covers GET /v1/complex-structure/entity/{id} with seeded Subsidiary rows
and multi-class Security/EquityDetails rows, asserting the response
reflects real seeded data rather than the old always-empty defaults.
"""

import uuid
from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.entity import Entity
from src.models.security import EquityDetails, Security
from src.models.subsidiary import Subsidiary


async def _seed_entity(session: AsyncSession, name: str = "Acme Holdings Inc.") -> Entity:
    entity = Entity(
        entity_id=uuid.uuid4(),
        entity_type="PUBLIC_COMPANY",
        legal_name=name,
        status="ACTIVE",
        source="TEST",
    )
    session.add(entity)
    await session.flush()
    return entity


async def _seed_subsidiaries(session: AsyncSession, entity: Entity, as_of: date) -> None:
    rows = [
        ("Acme Manufacturing LLC", "Delaware", 100.0, False),
        ("Acme Distribution LLC", "Delaware", 100.0, False),
        ("Acme International Holdings Ltd.", "Cayman Islands", 100.0, True),
        ("Acme Finance Ltd.", "Cayman Islands", None, False),
        ("Acme Europe B.V.", "Netherlands", 75.5, False),
        ("Acme Trading Co.", "California", 100.0, False),
        ("Acme Logistics Co.", "California", 100.0, False),
    ]
    for name, jurisdiction, pct, is_vie in rows:
        session.add(
            Subsidiary(
                subsidiary_id=uuid.uuid4(),
                parent_entity_id=entity.entity_id,
                name=name,
                jurisdiction=jurisdiction,
                ownership_pct=pct,
                is_vie=is_vie,
                source_filing_accession="0001193125-24-000075",
                as_of_date=as_of,
            )
        )
    await session.flush()


async def _seed_share_classes(session: AsyncSession, entity: Entity) -> None:
    class_a = Security(
        security_id=uuid.uuid4(),
        name="Acme Holdings Inc. Class A Common Stock",
        security_type="COMMON_STOCK",
        asset_class="EQUITY",
        status="ACTIVE",
        issuer_entity_id=entity.entity_id,
    )
    class_b = Security(
        security_id=uuid.uuid4(),
        name="Acme Holdings Inc. Class B Common Stock",
        security_type="COMMON_STOCK",
        asset_class="EQUITY",
        status="ACTIVE",
        issuer_entity_id=entity.entity_id,
    )
    session.add_all([class_a, class_b])
    await session.flush()

    session.add_all(
        [
            EquityDetails(
                security_id=class_a.security_id,
                share_class="A",
                share_class_description="Class A Common Stock",
                shares_outstanding=100_000_000,
                votes_per_share=1,
            ),
            EquityDetails(
                security_id=class_b.security_id,
                share_class="B",
                share_class_description="Class B Common Stock",
                shares_outstanding=20_000_000,
                votes_per_share=10,
            ),
        ]
    )
    await session.flush()


async def _seed_single_share_class(session: AsyncSession, entity: Entity) -> None:
    common = Security(
        security_id=uuid.uuid4(),
        name="SingleCo Inc. Common Stock",
        security_type="COMMON_STOCK",
        asset_class="EQUITY",
        status="ACTIVE",
        issuer_entity_id=entity.entity_id,
    )
    session.add(common)
    await session.flush()
    session.add(
        EquityDetails(
            security_id=common.security_id,
            share_class=None,
            shares_outstanding=50_000_000,
        )
    )
    await session.flush()


# ── Tests ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_entity_structure_404_for_unknown_entity(client: AsyncClient):
    resp = await client.get(f"/v1/complex-structure/entity/{uuid.uuid4()}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_entity_structure_returns_subsidiaries_and_share_classes(
    client: AsyncClient, session: AsyncSession
):
    entity = await _seed_entity(session)
    await _seed_subsidiaries(session, entity, date(2024, 2, 20))
    await _seed_share_classes(session, entity)
    await session.commit()

    resp = await client.get(f"/v1/complex-structure/entity/{entity.entity_id}")
    assert resp.status_code == 200
    data = resp.json()

    tree = data["subsidiary_tree"]
    assert tree["total_subsidiaries"] == 7
    assert tree["distinct_jurisdictions"] == 4
    # Delaware, Cayman Islands, Netherlands are offshore-flagged; California
    # is not: 5 of 7 subsidiaries -> a non-trivial offshore_pct.
    assert tree["offshore_count"] == 5
    assert tree["offshore_pct"] == pytest.approx(71.4, abs=0.1)
    assert tree["vie_count"] == 1

    classes = data["share_classes"]
    assert classes["num_classes"] == 2
    by_name = {c["class_name"]: c for c in classes["classes"]}
    assert by_name["A"]["shares_outstanding"] == 100_000_000.0
    assert by_name["B"]["shares_outstanding"] == 20_000_000.0
    # Real shares_outstanding are wired in; votes_per_share/economic_rights
    # are the documented pari-passu defaults (no ingested source for actual
    # per-class voting multipliers yet), so is_dual_class is False here even
    # though the seeded EquityDetails rows have different underlying
    # (unused) votes_per_share values -- that's the known limitation.
    assert by_name["A"]["votes_per_share"] == 1
    assert by_name["B"]["votes_per_share"] == 1
    assert classes["is_dual_class"] is False

    assert data["complexity_score"] > 0
    assert "Sprawling / offshore-heavy subsidiary network" in data["flags"]


@pytest.mark.asyncio
async def test_entity_structure_single_share_class_omits_share_classes_section(
    client: AsyncClient, session: AsyncSession
):
    entity = await _seed_entity(session, name="SingleCo Inc.")
    await _seed_single_share_class(session, entity)
    await session.commit()

    resp = await client.get(f"/v1/complex-structure/entity/{entity.entity_id}")
    assert resp.status_code == 200
    data = resp.json()

    # Single disclosed class (or none) -> no fabricated share-class section,
    # matching analyze_share_classes()'s "no data" default.
    assert data["share_classes"]["num_classes"] == 0
    assert data["share_classes"]["classes"] == []
    assert data["subsidiary_tree"]["total_subsidiaries"] == 0


@pytest.mark.asyncio
async def test_entity_structure_only_uses_most_recent_subsidiary_snapshot(
    client: AsyncClient, session: AsyncSession
):
    entity = await _seed_entity(session, name="SnapshotCo Inc.")
    # Older snapshot: 2 subs.
    await _seed_subsidiaries(session, entity, date(2023, 2, 15))
    # Delete the older batch's rows isn't needed -- add a newer, smaller
    # batch under a different as_of_date and confirm only the newer one
    # is counted (not the sum of both).
    session.add(
        Subsidiary(
            subsidiary_id=uuid.uuid4(),
            parent_entity_id=entity.entity_id,
            name="Acme NewCo LLC",
            jurisdiction="Delaware",
            ownership_pct=100.0,
            is_vie=False,
            source_filing_accession="0001193125-25-000010",
            as_of_date=date(2025, 2, 18),
        )
    )
    await session.commit()

    resp = await client.get(f"/v1/complex-structure/entity/{entity.entity_id}")
    assert resp.status_code == 200
    data = resp.json()
    # Only the single most recent as_of_date's row(s) should be counted --
    # not the 7 from the 2023 batch plus the 1 from 2025.
    assert data["subsidiary_tree"]["total_subsidiaries"] == 1
