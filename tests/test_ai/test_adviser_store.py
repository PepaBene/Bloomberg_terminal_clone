"""Tests for src/ai/adviser/store.py (Layer 3 §5.4: guardrail-filtered
recommendation persistence)."""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest

from src.ai.adviser.adviser import RecommendationOutput, VerifiedRecommendation
from src.ai.adviser.store import passes_guardrails, save_recommendations, set_recommendation_status
from src.models.advice_recommendation import AdviceRecommendation
from src.models.portfolio import Portfolio


async def _seed_portfolio(session, **kwargs) -> Portfolio:
    defaults = dict(
        id=uuid.uuid4(), user_id="default_user", portfolio_name="Store Test Portfolio",
        portfolio_type="REAL", inception_date=date(2025, 1, 1),
        initial_cash=Decimal("100000.00"), current_cash=Decimal("20000.00"),
    )
    defaults.update(kwargs)
    p = Portfolio(**defaults)
    session.add(p)
    await session.flush()
    return p


def _verified(*, evidence=("some evidence",), compliance=None, **kwargs) -> VerifiedRecommendation:
    defaults = dict(kind="THESIS", action={}, rationale="Some rationale", confidence=0.7)
    defaults.update(kwargs)
    rec = RecommendationOutput(evidence=list(evidence), **defaults)
    return VerifiedRecommendation(recommendation=rec, whatif_impact=None, compliance=compliance)


class TestPassesGuardrails:

    def test_passes_with_evidence_and_no_compliance_check(self):
        ok, reason = passes_guardrails(_verified())
        assert ok is True
        assert reason is None

    def test_fails_with_no_evidence(self):
        ok, reason = passes_guardrails(_verified(evidence=[]))
        assert ok is False
        assert "evidence" in reason

    def test_passes_with_approved_compliance(self):
        ok, _ = passes_guardrails(_verified(compliance={"approved": True, "violations": [], "warnings": []}))
        assert ok is True

    def test_fails_with_rejected_compliance(self):
        ok, reason = passes_guardrails(_verified(compliance={"approved": False, "violations": [{}], "warnings": []}))
        assert ok is False
        assert "compliance" in reason


@pytest.mark.asyncio
class TestSaveRecommendations:

    async def test_saves_recommendations_that_pass_guardrails(self, session):
        p = await _seed_portfolio(session)
        verified = [_verified(kind="OPPORTUNITY", confidence=0.8)]

        saved = await save_recommendations(session, user_id="default_user", portfolio_id=p.id, verified=verified)
        assert len(saved) == 1
        assert saved[0].status == "PROPOSED"
        assert saved[0].kind == "OPPORTUNITY"

    async def test_drops_recommendations_without_evidence(self, session):
        p = await _seed_portfolio(session)
        verified = [_verified(evidence=[])]

        saved = await save_recommendations(session, user_id="default_user", portfolio_id=p.id, verified=verified)
        assert saved == []

    async def test_drops_recommendations_that_fail_compliance(self, session):
        p = await _seed_portfolio(session)
        verified = [_verified(compliance={"approved": False, "violations": [{"message": "over limit"}], "warnings": []})]

        saved = await save_recommendations(session, user_id="default_user", portfolio_id=p.id, verified=verified)
        assert saved == []

    async def test_mixed_batch_only_saves_passing_ones(self, session):
        p = await _seed_portfolio(session)
        verified = [
            _verified(kind="THESIS"),
            _verified(kind="HEDGE", evidence=[]),
            _verified(kind="RISK", compliance={"approved": True, "violations": [], "warnings": []}),
        ]
        saved = await save_recommendations(session, user_id="default_user", portfolio_id=p.id, verified=verified)
        assert {r.kind for r in saved} == {"THESIS", "RISK"}


@pytest.mark.asyncio
class TestSetRecommendationStatus:

    async def test_updates_status(self, session):
        p = await _seed_portfolio(session)
        saved = await save_recommendations(session, user_id="default_user", portfolio_id=p.id, verified=[_verified()])
        rec_id = saved[0].id

        updated = await set_recommendation_status(session, rec_id, "ACCEPTED")
        assert updated.status == "ACCEPTED"

        fetched = await session.get(AdviceRecommendation, rec_id)
        assert fetched.status == "ACCEPTED"

    async def test_returns_none_for_unknown_id(self, session):
        result = await set_recommendation_status(session, uuid.uuid4(), "DISMISSED")
        assert result is None
