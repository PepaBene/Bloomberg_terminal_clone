"""Unit tests for the new src/ai core (Phase 0).

These run without the `anthropic` package or an API key: the client is disabled,
text helpers no-op, and structured/raw calls raise. Telemetry cost math and the
ai_call_log write are exercised against the in-memory SQLite test engine.
"""
from __future__ import annotations

import pytest
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.ai.client import AIClient, get_ai_client
from src.ai.llm_client import get_llm_client
from src.ai.models import MODEL_PRICING, Tier, estimate_cost_usd, model_for_tier
from src.ai.prompts import list_prompts, load_prompt
from src.ai.router import tier_for
from src.ai.telemetry import AICallRecord, Usage, record_call
from src.models.ai_call_log import AICallLog


# --------------------------------------------------------------------------- #
# models / pricing
# --------------------------------------------------------------------------- #
def test_model_for_tier():
    assert model_for_tier(Tier.LIGHT) == "claude-haiku-4-5"
    assert model_for_tier("synthesis") == "claude-sonnet-5"
    assert model_for_tier(Tier.DEEP) == "claude-opus-4-8"


def test_estimate_cost():
    # 1M input tokens at sonnet's input price == that price exactly
    cost = estimate_cost_usd("claude-sonnet-5", input_tokens=1_000_000)
    assert cost == pytest.approx(MODEL_PRICING["claude-sonnet-5"].input)
    assert estimate_cost_usd("does-not-exist", input_tokens=1000) == 0.0


# --------------------------------------------------------------------------- #
# router
# --------------------------------------------------------------------------- #
def test_tier_for():
    assert tier_for("deep_research") == Tier.DEEP
    assert tier_for("news_article_summary") == Tier.LIGHT
    assert tier_for("totally_unknown") == Tier.SYNTHESIS
    assert tier_for("news_article_summary", override="deep") == Tier.DEEP


# --------------------------------------------------------------------------- #
# prompt registry
# --------------------------------------------------------------------------- #
def test_prompt_registry_load_and_render():
    p = load_prompt("analyst_qa")
    assert p.id == "analyst_qa"
    assert p.version >= 1
    assert "cite" in p.system.lower() or "citation" in p.system.lower()

    rendered = load_prompt("interpret_metric").render(
        metric_name="ROE", value="18.2", unit="%", trend="rising", context="rows"
    )
    assert "ROE" in rendered and "rising" in rendered

    catalog = list_prompts()
    assert "analyst_qa" in catalog and "sentiment_score" in catalog


def test_prompt_registry_missing():
    with pytest.raises(KeyError):
        load_prompt("no_such_prompt")


# --------------------------------------------------------------------------- #
# client (disabled path)
# --------------------------------------------------------------------------- #
def test_client_disabled_flags():
    c = AIClient(api_key="")
    assert c.enabled is False
    assert c.api_key == ""


async def test_disabled_client_behaviour():
    c = AIClient(api_key="")

    assert await c.complete_text(user="hi", feature="test") is None

    with pytest.raises(RuntimeError):
        await c.complete(user="hi", feature="test")

    class M(BaseModel):
        x: int

    with pytest.raises(RuntimeError):
        await c.complete_structured(response_model=M, user="hi")

    chunks = [chunk async for chunk in c.stream(user="hi")]
    assert chunks == []


async def test_llm_shim_contract():
    llm = get_llm_client()
    # anthropic isn't installed in the test env, so the shim is disabled.
    assert llm.enabled is False
    assert await llm.generate("system", "user") is None
    # the shared singleton is also disabled
    assert get_ai_client().enabled is False


# --------------------------------------------------------------------------- #
# telemetry
# --------------------------------------------------------------------------- #
def test_usage_from_anthropic_handles_none_and_dict():
    assert Usage.from_anthropic(None).total_tokens == 0
    u = Usage.from_anthropic(
        {"input_tokens": 10, "output_tokens": 5, "cache_read_input_tokens": 2}
    )
    assert u.input_tokens == 10 and u.output_tokens == 5 and u.cache_read_tokens == 2


async def test_record_call_writes_row(engine):
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    rec = AICallRecord(
        feature="unit_test",
        model="claude-sonnet-5",
        usage=Usage(input_tokens=1000, output_tokens=500),
        latency_ms=12,
    )
    await record_call(rec, session_factory=factory)

    assert rec.cost_usd > 0
    async with factory() as s:
        count = await s.scalar(
            select(func.count()).select_from(AICallLog).where(AICallLog.feature == "unit_test")
        )
    assert count == 1
