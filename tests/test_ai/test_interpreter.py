"""Unit tests for src/ai/interpret/interpreter.py."""
from __future__ import annotations

import uuid
from datetime import date

import pytest

from src.ai.interpret.context import MetricSnapshot, SubjectContext
from src.ai.interpret.graph import Edge
from src.ai.interpret.interpreter import (
    MetricInterpretationOutput,
    SubjectSynthesisOutput,
    _relevant_edges,
    _render_graph_edges,
    _render_metric_interpretations,
    interpret_entity,
    interpret_metric,
    interpret_metrics_batch,
    render_lineage,
    synthesize_subject,
)


class FakeStructuredClient:
    """Duck-typed stand-in for AIClient.complete_structured, dispatching by
    substring match against the rendered user prompt (order-independent,
    safe for concurrent batch calls)."""

    def __init__(self, *, enabled: bool = True, response_for: dict | None = None, raise_for: tuple = ()):
        self.enabled = enabled
        self._response_for = response_for or {}
        self._raise_for = raise_for
        self.calls: list[str] = []

    async def complete_structured(self, *, response_model, user, system, tier, max_tokens, feature):
        self.calls.append(user)
        for substr in self._raise_for:
            if substr in user:
                raise RuntimeError(f"simulated failure for {substr}")
        for substr, resp in self._response_for.items():
            if substr in user:
                return resp
        raise AssertionError(f"no canned response for user={user!r}")


def _snapshot(metric_name="ROE", value=18.0, trend="IMPROVING", lineage=None) -> MetricSnapshot:
    return MetricSnapshot(
        metric_name=metric_name, metric_category="PROFITABILITY", value=value,
        unit="PERCENT", period="FY2025", as_of_date=date(2026, 1, 1), trend=trend,
        source_table="analytics_results", source_id="abc", lineage=lineage,
    )


METRIC_OUT = MetricInterpretationOutput(
    interpretation="ROE improved due to margin expansion.", trend="IMPROVING",
    direction="FAVORABLE", drivers=["net_margin"], confidence=0.8,
)


# --------------------------------------------------------------------------- #
# pure helpers
# --------------------------------------------------------------------------- #
def test_render_lineage_empty():
    assert "no source detail" in render_lineage(None)
    assert "no source detail" in render_lineage([])


def test_render_lineage_renders_entries():
    out = render_lineage([{"name": "net_income", "value": 100.0, "source": "fundamentals"}])
    assert "net_income = 100.0" in out
    assert "fundamentals" in out


def test_render_lineage_skips_non_dict_entries():
    out = render_lineage(["not-a-dict", {"name": "x", "value": 1}])
    assert "x = 1" in out


def test_relevant_edges_finds_connected_edges_for_known_metric():
    ctx = SubjectContext(subject_type="ENTITY", subject_id="e1", as_of=date.today(),
                          metrics=[_snapshot("ROE")], analytics_version="1:2026-01-01")
    edges = _relevant_edges(ctx)
    assert any(e.target == "roe" or e.source == "roe" for e in edges)


def test_relevant_edges_empty_for_unmapped_metrics():
    ctx = SubjectContext(subject_type="ENTITY", subject_id="e1", as_of=date.today(),
                          metrics=[_snapshot("SOME_UNMAPPED_METRIC")], analytics_version="x")
    assert _relevant_edges(ctx) == []


def test_render_metric_interpretations_empty():
    assert "no per-metric" in _render_metric_interpretations({})


def test_render_metric_interpretations_renders():
    out = _render_metric_interpretations({"ROE": METRIC_OUT})
    assert "ROE" in out and "IMPROVING" in out and "0.80" in out


def test_render_graph_edges_empty():
    assert "no curated" in _render_graph_edges([])


def test_render_graph_edges_renders():
    edges = [Edge("a", "b", "a causes b", "test")]
    out = _render_graph_edges(edges)
    assert "a -> b: a causes b" in out


# --------------------------------------------------------------------------- #
# interpret_metric / interpret_metrics_batch
# --------------------------------------------------------------------------- #
async def test_interpret_metric_raises_when_disabled():
    client = FakeStructuredClient(enabled=False)
    with pytest.raises(RuntimeError):
        await interpret_metric(client, _snapshot())


async def test_interpret_metric_returns_structured_output():
    client = FakeStructuredClient(response_for={"Metric: ROE": METRIC_OUT})
    out = await interpret_metric(client, _snapshot("ROE"))
    assert out.direction == "FAVORABLE"
    assert client.calls  # prompt was actually sent


async def test_interpret_metrics_batch_empty_when_disabled():
    client = FakeStructuredClient(enabled=False)
    assert await interpret_metrics_batch(client, [_snapshot()]) == {}


async def test_interpret_metrics_batch_empty_for_no_snapshots():
    client = FakeStructuredClient()
    assert await interpret_metrics_batch(client, []) == {}


async def test_interpret_metrics_batch_best_effort_partial_failure():
    client = FakeStructuredClient(
        response_for={"Metric: ROE": METRIC_OUT},
        raise_for=("Metric: CURRENT_RATIO",),
    )
    snapshots = [_snapshot("ROE"), _snapshot("CURRENT_RATIO")]
    result = await interpret_metrics_batch(client, snapshots)
    assert set(result.keys()) == {"ROE"}


async def test_interpret_metrics_batch_all_succeed():
    client = FakeStructuredClient(response_for={
        "Metric: ROE": METRIC_OUT,
        "Metric: CURRENT_RATIO": METRIC_OUT,
    })
    result = await interpret_metrics_batch(client, [_snapshot("ROE"), _snapshot("CURRENT_RATIO")])
    assert set(result.keys()) == {"ROE", "CURRENT_RATIO"}


# --------------------------------------------------------------------------- #
# synthesize_subject
# --------------------------------------------------------------------------- #
SYNTHESIS_OUT = SubjectSynthesisOutput(
    interpretation="Margin expansion is driving ROE higher.",
    trend="IMPROVING", direction="FAVORABLE", drivers=["net_margin"],
    consequences=["higher_intrinsic_value"], key_connections=["net_margin -> roe"],
    confidence=0.75,
)


async def test_synthesize_subject_raises_when_disabled():
    client = FakeStructuredClient(enabled=False)
    ctx = SubjectContext(subject_type="ENTITY", subject_id="e1", as_of=date.today(),
                          metrics=[_snapshot()], analytics_version="x")
    with pytest.raises(RuntimeError):
        await synthesize_subject(client, ctx, {"ROE": METRIC_OUT}, subject_label="MegaCorp")


async def test_synthesize_subject_returns_output():
    client = FakeStructuredClient(response_for={"Subject: MegaCorp": SYNTHESIS_OUT})
    ctx = SubjectContext(subject_type="ENTITY", subject_id="e1", as_of=date.today(),
                          metrics=[_snapshot()], analytics_version="x")
    out = await synthesize_subject(client, ctx, {"ROE": METRIC_OUT}, subject_label="MegaCorp")
    assert out.trend == "IMPROVING"


# --------------------------------------------------------------------------- #
# interpret_entity (full pipeline, DB-backed context + fake client)
# --------------------------------------------------------------------------- #
async def _seed_entity_with_roe(session) -> uuid.UUID:
    from src.models.analytics import AnalyticsResult
    from src.models.entity import Entity
    from src.models.security import Security

    entity_id = uuid.uuid4()
    session.add(Entity(entity_id=entity_id, entity_type="PUBLIC_COMPANY",
                        legal_name="MegaCorp Inc.", status="ACTIVE", source="TEST"))
    security_id = uuid.uuid4()
    session.add(Security(security_id=security_id, security_type="COMMON_STOCK",
                          issuer_entity_id=entity_id, name="MegaCorp Common Stock",
                          status="ACTIVE", asset_class="EQUITY"))
    await session.flush()
    session.add(AnalyticsResult(
        result_id=uuid.uuid4(), security_id=security_id, entity_id=entity_id,
        engine_id="E1", metric_name="ROE", metric_category="PROFITABILITY",
        value=18.0, unit="PERCENT", period="FY2025", as_of_date=date(2026, 1, 1),
    ))
    await session.flush()
    return entity_id


async def test_interpret_entity_no_metrics_returns_empty(session):
    client = FakeStructuredClient()
    entity_id = uuid.uuid4()  # no seeded data
    ctx, interps, synthesis = await interpret_entity(client, session, entity_id)
    assert ctx.metrics == []
    assert interps == {}
    assert synthesis is None


async def test_interpret_entity_disabled_client_returns_context_only(session):
    entity_id = await _seed_entity_with_roe(session)
    client = FakeStructuredClient(enabled=False)
    ctx, interps, synthesis = await interpret_entity(client, session, entity_id)
    assert len(ctx.metrics) == 1
    assert interps == {}
    assert synthesis is None


async def test_interpret_entity_full_pipeline(session):
    entity_id = await _seed_entity_with_roe(session)
    client = FakeStructuredClient(response_for={
        "Metric: ROE": METRIC_OUT,
        "Subject:": SYNTHESIS_OUT,
    })
    ctx, interps, synthesis = await interpret_entity(
        client, session, entity_id, subject_label="MegaCorp Inc.",
    )
    assert len(ctx.metrics) == 1
    assert "ROE" in interps
    assert synthesis is not None
    assert synthesis.trend == "IMPROVING"


async def test_interpret_entity_synthesis_failure_still_returns_metric_interps(session):
    entity_id = await _seed_entity_with_roe(session)
    client = FakeStructuredClient(
        response_for={"Metric: ROE": METRIC_OUT},
        raise_for=("Subject:",),
    )
    ctx, interps, synthesis = await interpret_entity(client, session, entity_id)
    assert "ROE" in interps
    assert synthesis is None
