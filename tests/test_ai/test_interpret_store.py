"""Tests for src/ai/interpret/store.py — persistence + compute-on-miss caching."""
from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import select

from src.ai.interpret.context import MetricSnapshot
from src.ai.interpret.interpreter import MetricInterpretationOutput, SubjectSynthesisOutput
from src.ai.interpret.store import (
    get_interpretation,
    get_or_compute_entity_interpretation,
    get_or_compute_metric_interpretation,
    save_metric_interpretation,
    save_subject_interpretation,
)
from src.models.interpretation import Interpretation


class FakeStructuredClient:
    def __init__(self, *, enabled: bool = True, response_for: dict | None = None):
        self.enabled = enabled
        self._response_for = response_for or {}
        self.calls: list[str] = []

    async def complete_structured(self, *, response_model, user, system, tier, max_tokens, feature):
        self.calls.append(user)
        for substr, resp in self._response_for.items():
            if substr in user:
                return resp
        raise AssertionError(f"no canned response for user={user!r}")


def _snapshot(metric_name="ROE", value=18.0) -> MetricSnapshot:
    return MetricSnapshot(
        metric_name=metric_name, metric_category="PROFITABILITY", value=value,
        unit="PERCENT", period="FY2025", as_of_date=date(2026, 1, 1), trend="IMPROVING",
        source_table="analytics_results", source_id="abc123", lineage=None,
    )


METRIC_OUT = MetricInterpretationOutput(
    interpretation="ROE improved.", trend="IMPROVING", direction="FAVORABLE",
    drivers=["net_margin"], confidence=0.8,
)
SYNTHESIS_OUT = SubjectSynthesisOutput(
    interpretation="Margin expansion drives ROE.", trend="IMPROVING", direction="FAVORABLE",
    drivers=["net_margin"], consequences=["higher_value"], key_connections=["net_margin -> roe"],
    confidence=0.75,
)


# --------------------------------------------------------------------------- #
# get_interpretation
# --------------------------------------------------------------------------- #
async def test_get_interpretation_null_metric_key_matches_only_null_rows(session):
    session.add(Interpretation(
        id=uuid.uuid4(), subject_type="ENTITY", subject_id="e1", scope="SUBJECT",
        metric_key=None, as_of=date(2026, 1, 1), interpretation="x",
    ))
    session.add(Interpretation(
        id=uuid.uuid4(), subject_type="ENTITY", subject_id="e1", scope="METRIC",
        metric_key="ROE", as_of=date(2026, 1, 1), interpretation="y",
    ))
    await session.flush()

    subject_row = await get_interpretation(
        session, subject_type="ENTITY", subject_id="e1", scope="SUBJECT",
        metric_key=None, as_of=date(2026, 1, 1),
    )
    metric_row = await get_interpretation(
        session, subject_type="ENTITY", subject_id="e1", scope="METRIC",
        metric_key="ROE", as_of=date(2026, 1, 1),
    )
    assert subject_row.interpretation == "x"
    assert metric_row.interpretation == "y"


async def test_get_interpretation_missing_returns_none(session):
    assert await get_interpretation(
        session, subject_type="ENTITY", subject_id="nope", scope="METRIC",
        metric_key="ROE", as_of=date(2026, 1, 1),
    ) is None


# --------------------------------------------------------------------------- #
# save_metric_interpretation / save_subject_interpretation (upsert)
# --------------------------------------------------------------------------- #
async def test_save_metric_interpretation_inserts_then_updates(session):
    row1 = await save_metric_interpretation(
        session, subject_type="ENTITY", subject_id="e1", as_of=date(2026, 1, 1),
        analytics_version="v1", snapshot=_snapshot(), output=METRIC_OUT,
    )
    assert row1.interpretation == "ROE improved."
    assert row1.ai_enabled is True
    assert row1.citations == ["analytics_results:abc123"]

    updated_output = MetricInterpretationOutput(
        interpretation="ROE improved further.", trend="IMPROVING",
        direction="FAVORABLE", drivers=["net_margin"], confidence=0.9,
    )
    row2 = await save_metric_interpretation(
        session, subject_type="ENTITY", subject_id="e1", as_of=date(2026, 1, 1),
        analytics_version="v2", snapshot=_snapshot(), output=updated_output,
    )
    assert row2.id == row1.id  # same row, updated in place
    assert row2.interpretation == "ROE improved further."
    assert row2.analytics_version == "v2"

    all_rows = (await session.execute(select(Interpretation))).scalars().all()
    assert len(all_rows) == 1  # no duplicate row created


async def test_save_subject_interpretation_inserts_then_updates(session):
    row1 = await save_subject_interpretation(
        session, subject_type="ENTITY", subject_id="e1", as_of=date(2026, 1, 1),
        analytics_version="v1", output=SYNTHESIS_OUT, citations=["interpretations:x"],
    )
    assert row1.scope == "SUBJECT"
    assert row1.metric_key is None
    assert row1.connections == ["net_margin -> roe"]

    row2 = await save_subject_interpretation(
        session, subject_type="ENTITY", subject_id="e1", as_of=date(2026, 1, 1),
        analytics_version="v2", output=SYNTHESIS_OUT, citations=["interpretations:x"],
    )
    assert row2.id == row1.id


# --------------------------------------------------------------------------- #
# get_or_compute_entity_interpretation (full compute-on-miss orchestration)
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


async def test_compute_on_miss_first_call_computes_and_persists(session):
    entity_id = await _seed_entity_with_roe(session)
    client = FakeStructuredClient(response_for={"Metric: ROE": METRIC_OUT, "Subject:": SYNTHESIS_OUT})

    result = await get_or_compute_entity_interpretation(session, client, entity_id)

    assert "ROE" in result["metrics"]
    assert result["subject"] is not None
    assert len(client.calls) == 2  # one metric call + one synthesis call


async def test_compute_on_miss_second_call_is_a_cache_hit_no_llm_calls(session):
    entity_id = await _seed_entity_with_roe(session)
    client = FakeStructuredClient(response_for={"Metric: ROE": METRIC_OUT, "Subject:": SYNTHESIS_OUT})

    await get_or_compute_entity_interpretation(session, client, entity_id)
    await session.flush()
    client.calls.clear()

    result = await get_or_compute_entity_interpretation(session, client, entity_id)

    assert "ROE" in result["metrics"]
    assert result["subject"] is not None
    assert client.calls == []  # fully served from cache, zero new LLM calls


async def test_compute_on_miss_stale_analytics_version_forces_recompute(session):
    entity_id = await _seed_entity_with_roe(session)
    client = FakeStructuredClient(response_for={"Metric: ROE": METRIC_OUT, "Subject:": SYNTHESIS_OUT})
    await get_or_compute_entity_interpretation(session, client, entity_id)
    await session.flush()

    # Simulate the analytics changing underneath the cached row.
    from src.models.analytics import AnalyticsResult
    session.add(AnalyticsResult(
        result_id=uuid.uuid4(),
        security_id=(await session.execute(select(AnalyticsResult.security_id).limit(1))).scalar(),
        entity_id=entity_id, engine_id="E1", metric_name="ROE",
        metric_category="PROFITABILITY", value=25.0, unit="PERCENT",
        period="FY2026", as_of_date=date(2026, 6, 1),
    ))
    await session.flush()
    client.calls.clear()

    result = await get_or_compute_entity_interpretation(session, client, entity_id)
    assert len(client.calls) == 2  # recomputed, not served stale from cache


async def test_compute_on_miss_force_refresh_bypasses_fresh_cache(session):
    entity_id = await _seed_entity_with_roe(session)
    client = FakeStructuredClient(response_for={"Metric: ROE": METRIC_OUT, "Subject:": SYNTHESIS_OUT})
    await get_or_compute_entity_interpretation(session, client, entity_id)
    await session.flush()
    client.calls.clear()

    result = await get_or_compute_entity_interpretation(session, client, entity_id, force_refresh=True)
    assert len(client.calls) == 2  # recomputed even though cache was fresh


async def test_compute_on_miss_disabled_client_returns_cached_metrics_only(session):
    entity_id = uuid.uuid4()  # no analytics seeded at all
    client = FakeStructuredClient(enabled=False)
    result = await get_or_compute_entity_interpretation(session, client, entity_id)
    assert result["metrics"] == {}
    assert result["subject"] is None
    assert result["context"].metrics == []


# --------------------------------------------------------------------------- #
# get_or_compute_metric_interpretation (single-metric popover path)
# --------------------------------------------------------------------------- #
async def test_get_or_compute_metric_unknown_metric_returns_none(session):
    entity_id = await _seed_entity_with_roe(session)
    client = FakeStructuredClient(response_for={"Metric: ROE": METRIC_OUT})
    ctx, row = await get_or_compute_metric_interpretation(session, client, entity_id, "NOT_A_METRIC")
    assert row is None
    assert len(ctx.metrics) == 1  # context was still assembled


async def test_get_or_compute_metric_computes_only_the_requested_metric(session):
    from src.models.analytics import AnalyticsResult

    entity_id = await _seed_entity_with_roe(session)
    security_id = (await session.execute(select(AnalyticsResult.security_id).limit(1))).scalar()
    session.add(AnalyticsResult(
        result_id=uuid.uuid4(), security_id=security_id, entity_id=entity_id,
        engine_id="E1", metric_name="CURRENT_RATIO", metric_category="LIQUIDITY",
        value=1.8, unit="RATIO", period="FY2025", as_of_date=date(2026, 1, 1),
    ))
    await session.flush()

    client = FakeStructuredClient(response_for={"Metric: ROE": METRIC_OUT})
    ctx, row = await get_or_compute_metric_interpretation(session, client, entity_id, "ROE")

    assert row is not None
    assert row.interpretation == "ROE improved."
    assert len(client.calls) == 1  # only ROE was computed, not CURRENT_RATIO or a subject synthesis
    all_rows = (await session.execute(select(Interpretation))).scalars().all()
    assert len(all_rows) == 1


async def test_get_or_compute_metric_cache_hit_skips_llm_call(session):
    entity_id = await _seed_entity_with_roe(session)
    client = FakeStructuredClient(response_for={"Metric: ROE": METRIC_OUT})
    await get_or_compute_metric_interpretation(session, client, entity_id, "ROE")
    await session.flush()
    client.calls.clear()

    ctx, row = await get_or_compute_metric_interpretation(session, client, entity_id, "ROE")
    assert row is not None
    assert client.calls == []


async def test_get_or_compute_metric_disabled_client_returns_none_when_uncached(session):
    entity_id = await _seed_entity_with_roe(session)
    client = FakeStructuredClient(enabled=False)
    ctx, row = await get_or_compute_metric_interpretation(session, client, entity_id, "ROE")
    assert row is None


async def test_get_or_compute_metric_stale_cache_with_disabled_client_returns_none_not_stale_row(session):
    # A stale row exists (wrong analytics_version) but AI is unavailable to
    # refresh it -- must NOT silently serve the outdated interpretation.
    entity_id = await _seed_entity_with_roe(session)
    session.add(Interpretation(
        id=uuid.uuid4(), subject_type="ENTITY", subject_id=str(entity_id),
        scope="METRIC", metric_key="ROE", as_of=date(2026, 1, 1),
        analytics_version="STALE", interpretation="outdated read", ai_enabled=True,
    ))
    await session.flush()

    client = FakeStructuredClient(enabled=False)
    ctx, row = await get_or_compute_metric_interpretation(session, client, entity_id, "ROE")
    assert row is None
