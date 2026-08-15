"""Tests for scripts/run_analytics_batch.py's central persistence helper.

Regression coverage for the CalculationLineage "no writer" bug: every
engine's EngineOutput.inputs already carries full lineage data, but nothing
ever copied it into the dedicated calculation_lineage table, so
GET /v2/analytics/audit/{id}/{metric} 404'd permanently even for metrics
that had genuinely been computed and persisted.
"""

import uuid
from datetime import date, datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.engines.base import EngineOutput
from src.models.analytics import AnalyticsResult, CalculationLineage
from src.models.entity import Entity
from src.models.security import Security

from scripts.run_analytics_batch import _persist_outputs, reopen_stale_engine_analytics


@pytest_asyncio.fixture
async def seeded_entity_security(session: AsyncSession):
    entity = Entity(
        entity_id=uuid.uuid4(), legal_name="Batch Persistence Test Corp",
        entity_type="PUBLIC_COMPANY", status="ACTIVE", source="TEST",
    )
    session.add(entity)
    await session.flush()
    security = Security(
        security_id=uuid.uuid4(), name="Batch Persistence Test Corp Stock",
        security_type="COMMON_STOCK", asset_class="EQUITY", status="ACTIVE",
        issuer_entity_id=entity.entity_id,
    )
    session.add(security)
    await session.flush()
    return entity, security


@pytest.mark.asyncio
async def test_persist_outputs_writes_calculation_lineage(session: AsyncSession, seeded_entity_security):
    """_persist_outputs must write a CalculationLineage row alongside
    AnalyticsResult for every EngineOutput, not just AnalyticsResult."""
    entity, security = seeded_entity_security

    output = EngineOutput(
        security_id=security.security_id,
        entity_id=entity.entity_id,
        engine_id="E1",
        metric_name="gross_margin",
        metric_category="PROFITABILITY",
        value=0.45,
        unit="PERCENT",
        period="TTM",
        as_of_date=date.today(),
        data_quality="COMPLETE",
        inputs=[
            {"name": "gross_profit", "source": "income_statements", "value": 180_000_000, "period": "", "filing_source": ""},
            {"name": "total_revenue", "source": "income_statements", "value": 400_000_000, "period": "", "filing_source": ""},
        ],
    )

    count = await _persist_outputs(session, [output])
    assert count == 1

    ar = (await session.execute(
        select(AnalyticsResult).where(
            AnalyticsResult.security_id == security.security_id,
            AnalyticsResult.metric_name == "gross_margin",
        )
    )).scalar_one()
    assert float(ar.value) == pytest.approx(0.45)

    lineage = (await session.execute(
        select(CalculationLineage).where(
            CalculationLineage.security_id == security.security_id,
            CalculationLineage.output_metric == "gross_margin",
        )
    )).scalar_one()
    assert float(lineage.output_value) == pytest.approx(0.45)
    assert lineage.engine_id == "E1"
    assert lineage.period == "TTM"
    assert len(lineage.inputs) == 2
    assert lineage.inputs[0]["name"] == "gross_profit"


@pytest.mark.asyncio
async def test_persist_outputs_lineage_survives_string_value(session: AsyncSession, seeded_entity_security):
    """A classification-style EngineOutput (value=None, or a string) must
    not crash lineage persistence -- output_value is a Numeric column and
    can only ever hold None for non-numeric outputs."""
    entity, security = seeded_entity_security

    output = EngineOutput(
        security_id=security.security_id,
        entity_id=entity.entity_id,
        engine_id="E3",
        metric_name="altman_zone",
        metric_category="QUALITY_SCORE",
        value=None,
        unit="CLASSIFICATION",
        period="TTM",
        as_of_date=date.today(),
        data_quality="SAFE",
        inputs=[{"name": "altman_z_score", "source": "E3", "value": 3.2, "period": "", "filing_source": ""}],
    )

    count = await _persist_outputs(session, [output])
    assert count == 1

    lineage = (await session.execute(
        select(CalculationLineage).where(
            CalculationLineage.security_id == security.security_id,
            CalculationLineage.output_metric == "altman_zone",
        )
    )).scalar_one()
    assert lineage.output_value is None


async def _ensure_ingestion_progress_table(session: AsyncSession) -> None:
    """ingestion_progress (migrations/versions/083_ingestion_progress.py) has
    no ORM model -- it's managed via raw SQL -- so it isn't part of the
    declarative Base metadata the test DB is built from. Create it ad hoc
    for tests that exercise this table.
    """
    await session.execute(text(
        """
        CREATE TABLE IF NOT EXISTS ingestion_progress (
            id TEXT PRIMARY KEY,
            data_type TEXT NOT NULL,
            subject_key TEXT NOT NULL,
            entity_id TEXT,
            status TEXT NOT NULL DEFAULT 'PENDING',
            attempts INTEGER NOT NULL DEFAULT 0,
            last_attempt_at TIMESTAMP,
            last_success_at TIMESTAMP,
            created_at TIMESTAMP,
            updated_at TIMESTAMP
        )
        """
    ))


async def _mark_progress(session: AsyncSession, data_type: str, security_id, when: datetime) -> None:
    await session.execute(
        text(
            """
            INSERT INTO ingestion_progress
                (id, data_type, subject_key, entity_id, status, attempts,
                 last_attempt_at, last_success_at, created_at, updated_at)
            VALUES (:id, :dt, :sk, NULL, 'SUCCESS', 1, :when, :when, :when, :when)
            """
        ),
        {"id": str(uuid.uuid4()), "dt": data_type, "sk": str(security_id), "when": when},
    )


@pytest.mark.asyncio
async def test_reopen_stale_engine_analytics_is_scoped_to_one_engine(
    session: AsyncSession, seeded_entity_security
):
    """Regression test: refreshing one engine (e.g. risk) on a recurring
    cadence must NOT wipe every other engine's analytics for the same
    security.

    reopen_stale_analytics (whole-security) deletes ALL of a security's
    AnalyticsResult rows once ANY of its engines goes stale -- fine for
    --engine all, but if it were used to force a e.g. daily refresh of
    just E5 risk (which needs to track daily EOD prices, unlike
    fundamentals-driven engines that recompute_security already refreshes
    on XBRL updates), it would silently force a full from-scratch
    recompute of ratios/DCF/comps/etc. every single day too.
    reopen_stale_engine_analytics must delete ONLY the targeted engine's
    rows and progress marker.
    """
    entity, security = seeded_entity_security
    old = datetime.now(timezone.utc) - timedelta(days=10)

    await _ensure_ingestion_progress_table(session)

    # E1 ratios: stale, but NOT the engine being refreshed -- must survive.
    session.add(AnalyticsResult(
        security_id=security.security_id, entity_id=entity.entity_id,
        engine_id="E1", metric_name="gross_margin", metric_category="PROFITABILITY",
        value=0.45, unit="PERCENT", period="TTM", as_of_date=date.today(),
        data_quality="COMPLETE",
    ))
    await _mark_progress(session, "analytics:ratios", security.security_id, old)

    # E5 risk: stale, and IS the engine being refreshed -- must be cleared.
    session.add(AnalyticsResult(
        security_id=security.security_id, entity_id=entity.entity_id,
        engine_id="E5", metric_name="var_historical_95_1d", metric_category="RISK",
        value=0.02, unit="RATIO", period="LATEST", as_of_date=date.today(),
        data_quality="COMPLETE",
    ))
    await _mark_progress(session, "analytics:risk", security.security_id, old)
    await session.flush()

    reopened = await reopen_stale_engine_analytics(session, "risk", days=1)
    assert reopened == 1

    # reopen_stale_engine_analytics deletes via raw SQL, which bypasses the
    # ORM session's identity map -- populate_existing forces this query to
    # re-read from the DB rather than return stale cached objects.
    remaining = (await session.execute(
        select(AnalyticsResult.engine_id)
        .where(AnalyticsResult.security_id == security.security_id)
        .execution_options(populate_existing=True)
    )).scalars().all()
    assert remaining == ["E1"]  # E5's row is gone; E1's survives untouched.

    progress_types = (await session.execute(
        text(
            "SELECT data_type FROM ingestion_progress WHERE subject_key = :sk"
        ),
        {"sk": str(security.security_id)},
    )).scalars().all()
    assert "analytics:risk" not in progress_types
    assert "analytics:ratios" in progress_types
