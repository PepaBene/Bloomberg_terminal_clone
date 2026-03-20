"""Entity resolution review queue for uncertain matches (Spec 3.5).

When the resolution pipeline produces a confidence score in the *uncertain*
band (0.70 – 0.95), the candidate is parked in the ``resolution_queue`` table
for human review.  Reviewers can then **approve** (merge into the existing
entity) or **reject** (create a brand-new entity from the source record).
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.enums import ResolutionStatus
from src.models.entity import Entity, EntityIdentifier, ResolutionQueue

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Queue operations
# ---------------------------------------------------------------------------

async def add_to_queue(
    source_system: str,
    source_record: dict[str, Any],
    candidate_entity_id: uuid.UUID | None,
    confidence: float,
    match_method: str | None,
    session: AsyncSession,
) -> uuid.UUID:
    """Add an uncertain match to the review queue.

    Parameters
    ----------
    source_system:
        Identifier for the originating data feed (e.g. ``"SEC_EDGAR"``).
    source_record:
        Raw/normalised record from the source system, stored as JSONB.
    candidate_entity_id:
        The best-candidate entity id, or ``None`` if no candidate was found.
    confidence:
        Confidence score from the matching engine (0.0 – 1.0).
    match_method:
        Description of how the match was produced (e.g. ``"fuzzy_name"``).
    session:
        Active SQLAlchemy async session.

    Returns
    -------
    uuid.UUID
        The ``id`` of the newly created queue entry.
    """
    queue_entry = ResolutionQueue(
        source_system=source_system,
        source_record=source_record,
        candidate_entity_id=candidate_entity_id,
        confidence_score=confidence,
        match_method=match_method,
        status=ResolutionStatus.PENDING.value,
    )

    session.add(queue_entry)
    await session.flush()  # populate server-generated defaults (id, created_at)

    logger.info(
        "Added to review queue: id=%s source=%s candidate=%s confidence=%.4f method=%s",
        queue_entry.id,
        source_system,
        candidate_entity_id,
        confidence,
        match_method,
    )

    return queue_entry.id


async def get_pending(
    session: AsyncSession,
    limit: int = 50,
) -> list[ResolutionQueue]:
    """Retrieve pending review items, ordered by descending confidence.

    Higher-confidence items appear first so reviewers can quickly approve
    the most-likely matches.

    Parameters
    ----------
    session:
        Active SQLAlchemy async session.
    limit:
        Maximum number of items to return (default 50).

    Returns
    -------
    list[ResolutionQueue]
        Pending queue entries.
    """
    stmt = (
        select(ResolutionQueue)
        .where(ResolutionQueue.status == ResolutionStatus.PENDING.value)
        .order_by(ResolutionQueue.confidence_score.desc(), ResolutionQueue.created_at.asc())
        .limit(limit)
    )

    result = await session.execute(stmt)
    items = list(result.scalars().all())

    logger.debug("Retrieved %d pending review items (limit=%d)", len(items), limit)
    return items


async def approve(
    queue_id: uuid.UUID,
    session: AsyncSession,
    reviewer: str | None = None,
) -> None:
    """Approve a match: merge source identifiers into the existing entity.

    Reads the ``source_record`` from the queue entry, extracts any identifiers
    present, and inserts them against the ``candidate_entity_id``.  Duplicate
    identifiers (same type+value already exists) are silently skipped.

    Parameters
    ----------
    queue_id:
        Primary key of the queue entry to approve.
    session:
        Active SQLAlchemy async session.
    reviewer:
        Optional name/email of the approving user.

    Raises
    ------
    ValueError
        If the queue entry is not found or is not in ``PENDING`` status, or
        if there is no ``candidate_entity_id`` to merge into.
    """
    entry = await session.get(ResolutionQueue, queue_id)

    if entry is None:
        raise ValueError(f"Resolution queue entry not found: {queue_id}")
    if entry.status != ResolutionStatus.PENDING.value:
        raise ValueError(
            f"Queue entry {queue_id} is not pending (current status: {entry.status})"
        )
    if entry.candidate_entity_id is None:
        raise ValueError(
            f"Queue entry {queue_id} has no candidate entity to merge into. "
            "Use reject() to create a new entity instead."
        )

    # Merge identifiers from source_record into the candidate entity
    identifiers = entry.source_record.get("identifiers", {})
    merged_count = 0

    for id_type, id_value in identifiers.items():
        if not id_type or not id_value:
            continue

        # Check for existing identifier to avoid unique-constraint violation
        existing_stmt = select(EntityIdentifier).where(
            EntityIdentifier.identifier_type == id_type.upper(),
            EntityIdentifier.identifier_value == str(id_value).strip(),
        )
        existing = (await session.execute(existing_stmt)).scalar_one_or_none()

        if existing is not None:
            logger.debug(
                "Skipping duplicate identifier %s=%s (already on entity %s)",
                id_type,
                id_value,
                existing.entity_id,
            )
            continue

        new_id = EntityIdentifier(
            entity_id=entry.candidate_entity_id,
            identifier_type=id_type.upper(),
            identifier_value=str(id_value).strip(),
            source=entry.source_system,
            is_primary=False,
        )
        session.add(new_id)
        merged_count += 1

    # Mark queue entry as approved
    now = datetime.now(timezone.utc)
    await session.execute(
        update(ResolutionQueue)
        .where(ResolutionQueue.id == queue_id)
        .values(
            status=ResolutionStatus.APPROVED.value,
            reviewer=reviewer,
            resolved_at=now,
        )
    )

    await session.flush()

    logger.info(
        "Approved queue entry %s: merged %d identifiers into entity %s (reviewer=%s)",
        queue_id,
        merged_count,
        entry.candidate_entity_id,
        reviewer,
    )


async def reject(
    queue_id: uuid.UUID,
    session: AsyncSession,
    reviewer: str | None = None,
) -> uuid.UUID:
    """Reject a match: create a new entity from the source record.

    Builds a new :class:`Entity` from the fields present in ``source_record``
    and inserts it along with any identifiers.  The queue entry is updated to
    ``CREATED_NEW`` status and its ``candidate_entity_id`` is pointed at the
    newly created entity.

    Parameters
    ----------
    queue_id:
        Primary key of the queue entry to reject.
    session:
        Active SQLAlchemy async session.
    reviewer:
        Optional name/email of the rejecting user.

    Returns
    -------
    uuid.UUID
        The ``entity_id`` of the newly created entity.

    Raises
    ------
    ValueError
        If the queue entry is not found or is not in ``PENDING`` status.
    """
    entry = await session.get(ResolutionQueue, queue_id)

    if entry is None:
        raise ValueError(f"Resolution queue entry not found: {queue_id}")
    if entry.status != ResolutionStatus.PENDING.value:
        raise ValueError(
            f"Queue entry {queue_id} is not pending (current status: {entry.status})"
        )

    record = entry.source_record

    # Build a new Entity from the source record
    new_entity = Entity(
        entity_type=record.get("entity_type", "OTHER"),
        legal_name=record.get("legal_name", record.get("name", "UNKNOWN")),
        legal_name_local=record.get("legal_name_local"),
        short_name=record.get("short_name"),
        status=record.get("status", "ACTIVE"),
        incorporation_country=record.get("incorporation_country") or record.get("country"),
        incorporation_date=record.get("incorporation_date"),
        domicile_country=record.get("domicile_country"),
        domicile_address=record.get("domicile_address"),
        fiscal_year_end=record.get("fiscal_year_end"),
        reporting_currency=record.get("reporting_currency"),
        primary_sic=record.get("primary_sic"),
        primary_naics=record.get("primary_naics"),
        gics_sub_industry=record.get("gics_sub_industry"),
        source=entry.source_system,
        confidence_score=entry.confidence_score,
    )

    session.add(new_entity)
    await session.flush()  # populate entity_id

    # Insert identifiers
    identifiers = record.get("identifiers", {})
    id_count = 0
    for id_type, id_value in identifiers.items():
        if not id_type or not id_value:
            continue

        new_id = EntityIdentifier(
            entity_id=new_entity.entity_id,
            identifier_type=id_type.upper(),
            identifier_value=str(id_value).strip(),
            source=entry.source_system,
            is_primary=(id_count == 0),  # first identifier marked primary
        )
        session.add(new_id)
        id_count += 1

    # Update queue entry
    now = datetime.now(timezone.utc)
    await session.execute(
        update(ResolutionQueue)
        .where(ResolutionQueue.id == queue_id)
        .values(
            status=ResolutionStatus.CREATED_NEW.value,
            candidate_entity_id=new_entity.entity_id,
            reviewer=reviewer,
            resolved_at=now,
        )
    )

    await session.flush()

    logger.info(
        "Rejected queue entry %s: created new entity %s with %d identifiers (reviewer=%s)",
        queue_id,
        new_entity.entity_id,
        id_count,
        reviewer,
    )

    return new_entity.entity_id
