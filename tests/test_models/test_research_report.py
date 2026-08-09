"""Smoke test for the ResearchReport model (Layer 2 — on-demand Deep Research, §4.6)."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from src.models.research_report import ResearchReport


async def test_create_pending_report_defaults(session):
    row = ResearchReport(
        id=uuid.uuid4(), subject_type="ENTITY", subject_id=str(uuid.uuid4()),
        subject_label="Acme Corp",
    )
    session.add(row)
    await session.flush()

    fetched = (
        await session.execute(select(ResearchReport).where(ResearchReport.subject_label == "Acme Corp"))
    ).scalar_one()
    assert fetched.status == "PENDING"
    assert fetched.sections is None
    assert fetched.sources is None
    assert fetched.completed_at is None


async def test_create_free_text_report_has_no_subject_id(session):
    row = ResearchReport(
        id=uuid.uuid4(), subject_type="FREE_TEXT", subject_id=None,
        subject_label="What is the outlook for EV battery supply chains?",
    )
    session.add(row)
    await session.flush()

    fetched = (
        await session.execute(select(ResearchReport).where(ResearchReport.subject_type == "FREE_TEXT"))
    ).scalar_one()
    assert fetched.subject_id is None
    assert fetched.subject_label.startswith("What is the outlook")


async def test_completed_report_round_trips_sections_and_sources(session):
    row = ResearchReport(
        id=uuid.uuid4(), subject_type="ENTITY", subject_id=str(uuid.uuid4()),
        subject_label="Acme Corp", focus="competitive risk",
        sections=[{"title": "Competitive Dynamics", "content": "Beta Corp is a growing threat.", "citations": ["Reuters"]}],
        sources=["Reuters", "https://example.com/article"],
        confidence=0.72, model="claude-opus-4-8", status="COMPLETE",
        completed_at=datetime.now(timezone.utc),
    )
    session.add(row)
    await session.flush()

    fetched = (
        await session.execute(select(ResearchReport).where(ResearchReport.id == row.id))
    ).scalar_one()
    assert fetched.status == "COMPLETE"
    assert fetched.sections[0]["title"] == "Competitive Dynamics"
    assert fetched.sources == ["Reuters", "https://example.com/article"]
    assert float(fetched.confidence) == 0.72
    assert fetched.completed_at is not None


async def test_failed_report_carries_error(session):
    row = ResearchReport(
        id=uuid.uuid4(), subject_type="ENTITY", subject_id=str(uuid.uuid4()),
        subject_label="Acme Corp", status="FAILED", error="RuntimeError: AI disabled",
    )
    session.add(row)
    await session.flush()

    fetched = (
        await session.execute(select(ResearchReport).where(ResearchReport.status == "FAILED"))
    ).scalar_one()
    assert fetched.error == "RuntimeError: AI disabled"
