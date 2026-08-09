"""Unit tests for src/ai/adviser/adviser.py."""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest

from src.ai.adviser.adviser import (
    AdviceExtractionOutput,
    RecommendationOutput,
    _trade_action_fields,
    gather_advice,
    render_transcript,
    run_adviser_turn,
    verify_recommendation,
)
from src.ai.agents.loop import AgentResult, AgentStep
from src.ai.client import AIResponse
from src.models.compliance import ComplianceRule
from src.models.portfolio import Portfolio
from src.models.position import Position


def _tool_use_response(*, text: str, tool_name: str, tool_input: dict, tool_id: str = "tu_1") -> AIResponse:
    block = SimpleNamespace(type="tool_use", name=tool_name, input=tool_input, id=tool_id)
    return AIResponse(text=text, tool_uses=[block], stop_reason="tool_use", raw=SimpleNamespace(content=[block]))


def _final_response(text: str) -> AIResponse:
    block = SimpleNamespace(type="text", text=text)
    return AIResponse(text=text, tool_uses=[], stop_reason="end_turn", raw=SimpleNamespace(content=[block]))


class FakeAdviserClient:
    def __init__(self, *, enabled: bool = True, complete_responses=None, structured_response=None):
        self.enabled = enabled
        self._complete_responses = list(complete_responses or [])
        self._structured_response = structured_response
        self.complete_calls: list[dict] = []
        self.structured_calls: list[dict] = []

    async def complete(self, **kwargs):
        self.complete_calls.append(kwargs)
        if not self._complete_responses:
            raise AssertionError("ran out of queued complete() responses")
        return self._complete_responses.pop(0)

    async def complete_structured(self, **kwargs):
        self.structured_calls.append(kwargs)
        return self._structured_response


async def _seed_portfolio(session, **kwargs) -> Portfolio:
    defaults = dict(
        id=uuid.uuid4(), user_id="default_user", portfolio_name="Adviser Test Portfolio",
        portfolio_type="REAL", inception_date=date(2025, 1, 1),
        initial_cash=Decimal("100000.00"), current_cash=Decimal("20000.00"),
    )
    defaults.update(kwargs)
    p = Portfolio(**defaults)
    session.add(p)
    await session.flush()
    return p


async def _seed_position(session, portfolio_id, **kwargs) -> Position:
    defaults = dict(
        id=uuid.uuid4(), portfolio_id=portfolio_id, ticker="AAPL", status="OPEN",
        shares=Decimal("100"), market_value=Decimal("40000.00"), weight=Decimal("0.5"),
        closing_price=Decimal("400.00"),
    )
    defaults.update(kwargs)
    p = Position(**defaults)
    session.add(p)
    await session.flush()
    return p


class TestRenderTranscript:

    def test_empty_steps(self):
        assert "no steps" in render_transcript([])

    def test_renders_reasoning_and_tool_calls(self):
        steps = [AgentStep(
            role="assistant", text="Checking the portfolio first.",
            tool_calls=[{"name": "portfolio_snapshot", "input": {"portfolio_id": "x"}, "tool_use_id": "t1"}],
            tool_results=[{"tool_use_id": "t1", "content": "NAV: 100000", "is_error": False}],
        )]
        result = render_transcript(steps)
        assert "Checking the portfolio first" in result
        assert "portfolio_snapshot" in result
        assert "NAV: 100000" in result


class TestTradeActionFields:

    def test_well_formed_trade(self):
        result = _trade_action_fields({"ticker": "AAPL", "action": "SELL", "shares": 50, "price_per_share": 400.0})
        assert result == ("AAPL", "SELL", 50.0, 400.0)

    def test_missing_fields_returns_none(self):
        assert _trade_action_fields({"ticker": "AAPL"}) is None

    def test_empty_dict_returns_none(self):
        assert _trade_action_fields({}) is None

    def test_non_numeric_shares_returns_none(self):
        assert _trade_action_fields({"ticker": "AAPL", "action": "BUY", "shares": "many", "price_per_share": 10}) is None


@pytest.mark.asyncio
class TestGatherAdvice:

    async def test_disabled_client_raises(self, session):
        client = FakeAdviserClient(enabled=False)
        with pytest.raises(RuntimeError):
            await gather_advice(client, session, portfolio_id=uuid.uuid4(), message="how am I doing?")

    async def test_runs_agent_loop(self, session):
        p = await _seed_portfolio(session)
        await _seed_position(session, p.id)
        client = FakeAdviserClient(complete_responses=[
            _tool_use_response(text="", tool_name="portfolio_snapshot", tool_input={"portfolio_id": str(p.id)}),
            _final_response("Your portfolio is concentrated in AAPL."),
        ])

        result = await gather_advice(client, session, portfolio_id=p.id, message="How concentrated am I?")
        assert result.stopped_reason == "final_answer"
        assert "concentrated" in result.final_text


@pytest.mark.asyncio
class TestVerifyRecommendation:

    async def test_non_trade_recommendation_passes_through(self, session):
        p = await _seed_portfolio(session)
        rec = RecommendationOutput(kind="THESIS", action={}, rationale="Long-term bullish", confidence=0.6)
        result = await verify_recommendation(session, p.id, rec)
        assert result.whatif_impact is None
        assert result.compliance is None

    async def test_trade_recommendation_gets_real_verification(self, session):
        p = await _seed_portfolio(session)
        await _seed_position(session, p.id, ticker="AAPL", weight=Decimal("0.5"), market_value=Decimal("40000"))
        rec = RecommendationOutput(
            kind="REBALANCE",
            action={"ticker": "AAPL", "action": "SELL", "shares": 50, "price_per_share": 400.0},
            rationale="Reduce concentration", confidence=0.8,
        )
        result = await verify_recommendation(session, p.id, rec)
        assert result.whatif_impact is not None
        assert result.compliance is not None
        assert result.compliance["approved"] is True

    async def test_trade_recommendation_flags_compliance_violation(self, session):
        p = await _seed_portfolio(session)
        session.add(ComplianceRule(
            rule_id=uuid.uuid4(), portfolio_id=p.id, rule_name="Position Cap",
            rule_type="POSITION_LIMIT", rule_definition={}, threshold=Decimal("1000.000000"),
            comparison="LTE", severity="CRITICAL", is_active=True,
        ))
        await session.flush()
        rec = RecommendationOutput(
            kind="OPPORTUNITY",
            action={"ticker": "AAPL", "action": "BUY", "shares": 100, "price_per_share": 150.0},
            rationale="Attractive entry point", confidence=0.7,
        )
        result = await verify_recommendation(session, p.id, rec)
        assert result.compliance["approved"] is False


@pytest.mark.asyncio
class TestRunAdviserTurn:

    async def test_full_turn_no_recommendations(self, session):
        p = await _seed_portfolio(session)
        await _seed_position(session, p.id)
        client = FakeAdviserClient(
            complete_responses=[_final_response("Your NAV is 60,000.")],
            structured_response=AdviceExtractionOutput(recommendations=[]),
        )

        result = await run_adviser_turn(client, session, portfolio_id=p.id, message="What's my NAV?")
        assert result.reply_text == "Your NAV is 60,000."
        assert result.recommendations == []

    async def test_full_turn_with_verified_recommendation(self, session):
        p = await _seed_portfolio(session)
        await _seed_position(session, p.id, ticker="AAPL", weight=Decimal("0.5"), market_value=Decimal("40000"))
        client = FakeAdviserClient(
            complete_responses=[_final_response("I recommend trimming AAPL.")],
            structured_response=AdviceExtractionOutput(recommendations=[
                RecommendationOutput(
                    kind="REBALANCE",
                    action={"ticker": "AAPL", "action": "SELL", "shares": 50, "price_per_share": 400.0},
                    rationale="Overweight vs typical allocation", confidence=0.75,
                ),
            ]),
        )

        result = await run_adviser_turn(client, session, portfolio_id=p.id, message="Should I trim AAPL?")
        assert len(result.recommendations) == 1
        assert result.recommendations[0].whatif_impact is not None
        assert result.recommendations[0].compliance["approved"] is True

    async def test_on_step_hook_is_forwarded(self, session):
        p = await _seed_portfolio(session)
        client = FakeAdviserClient(
            complete_responses=[_final_response("ok")],
            structured_response=AdviceExtractionOutput(recommendations=[]),
        )
        seen = []

        async def on_step(step):
            seen.append(step)

        await run_adviser_turn(client, session, portfolio_id=p.id, message="hi", on_step=on_step)
        assert len(seen) == 1
