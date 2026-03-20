"""Point-in-Time (PIT) temporal data management (Spec 14.1).

Implements the 4 temporal dimensions:
1. Period Time — when did it happen (fiscal period)
2. Publication Time — when was it published (filing date)
3. Knowledge Time — when did we know it (our ingestion timestamp)
4. Revision Time — which version is it (revision number)
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import and_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.entity import Entity, EntityHistory


async def record_entity_history(
    entity: Entity, session: AsyncSession
) -> EntityHistory:
    """Snapshot the current entity state into the history table.

    Creates a new history record with valid_from = NOW.
    Also closes the previous history record by setting its valid_to.
    """
    now = datetime.now(timezone.utc)

    # Close previous history record
    await session.execute(
        update(EntityHistory)
        .where(
            EntityHistory.entity_id == entity.entity_id,
            EntityHistory.valid_to.is_(None),
        )
        .values(valid_to=now)
    )

    # Get next revision number
    result = await session.execute(
        select(EntityHistory.revision_number)
        .where(EntityHistory.entity_id == entity.entity_id)
        .order_by(EntityHistory.revision_number.desc())
        .limit(1)
    )
    last_rev = result.scalar_one_or_none()
    next_rev = (last_rev if last_rev is not None else -1) + 1

    # Create new history snapshot
    history = EntityHistory(
        history_id=uuid.uuid4(),
        entity_id=entity.entity_id,
        entity_type=entity.entity_type,
        legal_name=entity.legal_name,
        short_name=entity.short_name,
        status=entity.status,
        incorporation_country=entity.incorporation_country,
        domicile_country=entity.domicile_country,
        fiscal_year_end=entity.fiscal_year_end,
        reporting_currency=entity.reporting_currency,
        accounting_standard=entity.accounting_standard,
        primary_sic=entity.primary_sic,
        gics_sub_industry=entity.gics_sub_industry,
        ultimate_parent_id=entity.ultimate_parent_id,
        immediate_parent_id=entity.immediate_parent_id,
        source=entity.source,
        confidence_score=entity.confidence_score,
        valid_from=now,
        valid_to=None,
        revision_number=next_rev,
    )
    session.add(history)
    await session.flush()
    return history


async def get_entity_as_of(
    entity_id: uuid.UUID,
    as_of: datetime,
    session: AsyncSession,
) -> EntityHistory | None:
    """Get the entity state as known at a specific point in time.

    Returns the history record where valid_from <= as_of < valid_to
    (or valid_to is NULL, meaning it's the current version).
    """
    result = await session.execute(
        select(EntityHistory).where(
            EntityHistory.entity_id == entity_id,
            EntityHistory.valid_from <= as_of,
            (
                EntityHistory.valid_to.is_(None)
                | (EntityHistory.valid_to > as_of)
            ),
        )
    )
    return result.scalar_one_or_none()


async def get_entity_revisions(
    entity_id: uuid.UUID, session: AsyncSession
) -> list[EntityHistory]:
    """Get all versions of an entity, ordered by revision number."""
    result = await session.execute(
        select(EntityHistory)
        .where(EntityHistory.entity_id == entity_id)
        .order_by(EntityHistory.revision_number)
    )
    return list(result.scalars().all())


async def get_current_revision(
    entity_id: uuid.UUID, session: AsyncSession
) -> EntityHistory | None:
    """Get the current (latest) history record for an entity."""
    result = await session.execute(
        select(EntityHistory).where(
            EntityHistory.entity_id == entity_id,
            EntityHistory.valid_to.is_(None),
        )
    )
    return result.scalar_one_or_none()


# ── Fundamentals PIT Support ──────────────────────────────────────────


async def get_fundamentals_as_of(
    entity_id: uuid.UUID,
    period_end_date,
    as_of: datetime,
    session: AsyncSession,
):
    """Get the financial period data as known at a specific point in time.

    This is useful for avoiding look-ahead bias in backtests: it returns
    the financial data that was available as of ``as_of``, even if the
    data has been subsequently revised.

    Parameters
    ----------
    entity_id : uuid.UUID
        Entity to query.
    period_end_date : date
        The fiscal period end date (e.g. 2024-12-31).
    as_of : datetime
        The point-in-time knowledge cutoff.
    session : AsyncSession
        Database session.

    Returns
    -------
    FinancialPeriod | None
        The financial period that was known at ``as_of``, or None.
    """
    from src.models.fundamentals import FinancialPeriod

    result = await session.execute(
        select(FinancialPeriod)
        .where(
            FinancialPeriod.entity_id == entity_id,
            FinancialPeriod.period_end_date == period_end_date,
            FinancialPeriod.created_at <= as_of,
        )
        .order_by(FinancialPeriod.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_fundamentals_revisions(
    entity_id: uuid.UUID,
    period_end_date,
    session: AsyncSession,
) -> list:
    """Get all revisions of financial data for a specific period.

    Returns all FinancialPeriod records for the given entity/period,
    ordered by creation time (earliest first).
    """
    from src.models.fundamentals import FinancialPeriod

    result = await session.execute(
        select(FinancialPeriod)
        .where(
            FinancialPeriod.entity_id == entity_id,
            FinancialPeriod.period_end_date == period_end_date,
        )
        .order_by(FinancialPeriod.created_at)
    )
    return list(result.scalars().all())


# ── Security PIT Support ─────────────────────────────────────────────


async def get_security_as_of(
    security_id: uuid.UUID,
    as_of: datetime,
    session: AsyncSession,
):
    """Get the security master state as known at a specific point in time.

    Returns the security record that was current as of ``as_of``.
    For point-in-time queries on security attributes (name, status,
    exchange, etc.).
    """
    from src.models.security import Security

    result = await session.execute(
        select(Security)
        .where(
            Security.security_id == security_id,
            Security.created_at <= as_of,
        )
        .order_by(Security.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_eod_price_as_of(
    security_id: uuid.UUID,
    price_date,
    session: AsyncSession,
):
    """Get the EOD price for a security on a given date.

    This is the standard PIT lookup for prices — returns the most
    recent price on or before the given date.
    """
    from src.models.security import EODPrice

    result = await session.execute(
        select(EODPrice)
        .where(
            EODPrice.security_id == security_id,
            EODPrice.price_date <= price_date,
        )
        .order_by(EODPrice.price_date.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()
