"""Integration tests: AIClient.complete_text/complete_structured actually
skip the API call on a §6 Redis response-cache hit.

No `anthropic` package is installed in this test environment (confirmed
by every other AIClient test in this suite), so `AIClient(api_key=...)`
always ends up disabled via its own graceful-degradation path. These
tests construct a disabled client and then monkeypatch `_client` directly
to a fake mimicking `anthropic.AsyncAnthropic`'s `messages.create`
surface -- the same "duck-typed enough to exercise the real control flow"
approach `tests/test_ai/test_agents.py` already uses for the agent loop.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from pydantic import BaseModel

from src.ai import response_cache
from src.ai.client import AIClient


class FakeMessages:
    def __init__(self, responses: list):
        self._responses = list(responses)
        self.calls: list[dict] = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        if not self._responses:
            raise AssertionError("FakeMessages ran out of queued responses")
        return self._responses.pop(0)


def _text_response(text: str):
    block = SimpleNamespace(type="text", text=text)
    return SimpleNamespace(content=[block], stop_reason="end_turn", usage=None, model="claude-sonnet-5")


def _tool_response(tool_name: str, data: dict):
    block = SimpleNamespace(type="tool_use", name=tool_name, input=data)
    return SimpleNamespace(content=[block], stop_reason="tool_use", usage=None, model="claude-sonnet-5")


def _enabled_client(responses: list) -> tuple[AIClient, FakeMessages]:
    client = AIClient(api_key="")
    fake_messages = FakeMessages(responses)
    client._client = SimpleNamespace(messages=fake_messages)
    return client, fake_messages


class Answer(BaseModel):
    text: str
    confidence: float


@pytest.fixture(autouse=True)
def fake_redis(monkeypatch):
    class FakeRedisCache:
        def __init__(self):
            self._store: dict = {}

        async def get(self, key):
            return self._store.get(key)

        async def set(self, key, value, ttl=None):
            self._store[key] = value

        @staticmethod
        def make_key(*parts):
            return ":".join(parts)

    monkeypatch.setattr(response_cache, "cache", FakeRedisCache())


@pytest.mark.asyncio
class TestCompleteTextCaching:

    async def test_second_identical_call_skips_the_api(self):
        client, fake = _enabled_client([_text_response("Cached answer.")])

        first = await client.complete_text(user="What is ROE?", system="sys", feature="company_primer")
        second = await client.complete_text(user="What is ROE?", system="sys", feature="company_primer")

        assert first == "Cached answer."
        assert second == "Cached answer."
        assert len(fake.calls) == 1  # only the first call actually hit the API

    async def test_different_input_is_not_a_cache_hit(self):
        client, fake = _enabled_client([_text_response("A"), _text_response("B")])

        r1 = await client.complete_text(user="question 1", system="sys", feature="company_primer")
        r2 = await client.complete_text(user="question 2", system="sys", feature="company_primer")

        assert (r1, r2) == ("A", "B")
        assert len(fake.calls) == 2

    async def test_uncached_feature_always_calls_the_api(self):
        client, fake = _enabled_client([_text_response("A"), _text_response("B")])

        r1 = await client.complete_text(user="hi", system="sys", feature="adviser_chat")
        r2 = await client.complete_text(user="hi", system="sys", feature="adviser_chat")

        assert (r1, r2) == ("A", "B")
        assert len(fake.calls) == 2


@pytest.mark.asyncio
class TestCompleteStructuredCaching:

    async def test_second_identical_call_skips_the_api(self):
        client, fake = _enabled_client([_tool_response("emit_Answer", {"text": "ROE is favorable.", "confidence": 0.8})])

        first = await client.complete_structured(response_model=Answer, user="What is ROE?", system="sys", feature="interpret_metric")
        second = await client.complete_structured(response_model=Answer, user="What is ROE?", system="sys", feature="interpret_metric")

        assert first == second == Answer(text="ROE is favorable.", confidence=0.8)
        assert len(fake.calls) == 1

    async def test_uncached_feature_always_calls_the_api(self):
        client, fake = _enabled_client([
            _tool_response("emit_Answer", {"text": "A", "confidence": 0.5}),
            _tool_response("emit_Answer", {"text": "A", "confidence": 0.5}),
        ])

        await client.complete_structured(response_model=Answer, user="hi", system="sys", feature="deep_research")
        await client.complete_structured(response_model=Answer, user="hi", system="sys", feature="deep_research")

        assert len(fake.calls) == 2
