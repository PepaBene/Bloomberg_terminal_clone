"""Smoke test for the Interpretation model (Layer 1 — Phase 1)."""
from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import select

from src.models.interpretation import Interpretation


async def test_create_metric_scope_interpretation(session):
    row = Interpretation(
        id=uuid.uuid4(),
        subject_type="ENTITY",
        subject_id=str(uuid.uuid4()),
        scope="METRIC",
        metric_key="ROE",
        as_of=date(2026, 1, 1),
        interpretation="ROE of 18% is favorable versus the 5yr average of 12%.",
        trend="IMPROVING",
        direction="FAVORABLE",
        drivers=["net_margin_expansion"],
        consequences=["higher_intrinsic_value"],
        confidence=0.82,
        citations=["analytics_results:abc123"],
        model="claude-haiku-4-5",
        ai_enabled=True,
    )
    session.add(row)
    await session.flush()

    fetched = (
        await session.execute(select(Interpretation).where(Interpretation.metric_key == "ROE"))
    ).scalar_one()
    assert fetched.subject_type == "ENTITY"
    assert fetched.scope == "METRIC"
    assert fetched.drivers == ["net_margin_expansion"]
    assert float(fetched.confidence) == 0.82
    assert fetched.ai_enabled is True


async def test_create_subject_scope_interpretation_metric_key_null(session):
    row = Interpretation(
        id=uuid.uuid4(),
        subject_type="ENTITY",
        subject_id=str(uuid.uuid4()),
        scope="SUBJECT",
        metric_key=None,
        as_of=date(2026, 1, 1),
        interpretation="Margin compression is flowing through to a lower DCF value.",
        connections=[{"source": "operating_margin", "target": "dcf_value", "mechanism": "..."}],
    )
    session.add(row)
    await session.flush()

    fetched = (
        await session.execute(select(Interpretation).where(Interpretation.scope == "SUBJECT"))
    ).scalar_one()
    assert fetched.metric_key is None
    assert fetched.ai_enabled is False  # model default


async def test_sector_and_macro_subject_ids_are_non_uuid_strings(session):
    # SECTOR/MACRO subjects use GICS/region codes, not UUIDs -- confirms
    # subject_id being a plain string (not a UUID FK) actually works.
    row = Interpretation(
        id=uuid.uuid4(),
        subject_type="SECTOR",
        subject_id="4510",  # GICS sub-industry code
        scope="SUBJECT",
        as_of=date(2026, 1, 1),
        interpretation="Sector is in a late-cycle contraction phase.",
    )
    session.add(row)
    await session.flush()
    fetched = (
        await session.execute(select(Interpretation).where(Interpretation.subject_type == "SECTOR"))
    ).scalar_one()
    assert fetched.subject_id == "4510"
