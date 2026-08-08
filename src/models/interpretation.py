"""Layer 1 (Interpreter) output storage — AI_THREE_LAYER_REBUILD_PLAN.md §3.4.

One row per (subject, scope, metric_key, as_of): a grounded, cited
interpretation of what a computed figure (or a subject as a whole) means,
its trend, drivers, consequences, and cross-domain connections walked via
``src/ai/interpret/graph.py``.
"""
import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class Interpretation(Base):
    """A grounded interpretation of a metric or subject (Layer 1 output)."""

    __tablename__ = "interpretations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # Polymorphic subject -- deliberately a plain string, not a UUID FK:
    # SECTOR (GICS code) and MACRO (region code) subjects aren't rows in any
    # single table the way ENTITY/SECURITY/PORTFOLIO are.
    subject_type: Mapped[str] = mapped_column(String(20), nullable=False)  # ENTITY|SECURITY|SECTOR|MACRO|PORTFOLIO
    subject_id: Mapped[str] = mapped_column(String(100), nullable=False)

    scope: Mapped[str] = mapped_column(String(10), nullable=False)  # METRIC|GROUP|SUBJECT
    # Single metric_name (METRIC scope), a group label like "DUPONT" (GROUP
    # scope), or NULL (SUBJECT scope -- the whole-subject synthesis row).
    metric_key: Mapped[str | None] = mapped_column(String(100))

    as_of: Mapped[date] = mapped_column(Date, nullable=False)
    # Pins this row to the analytics snapshot it was computed from, so a
    # later analytics recompute can tell "is this interpretation stale"
    # without re-diffing every input row -- see compute-on-miss cache logic.
    analytics_version: Mapped[str | None] = mapped_column(String(20))

    interpretation: Mapped[str] = mapped_column(Text, nullable=False)
    trend: Mapped[str | None] = mapped_column(String(20))
    direction: Mapped[str | None] = mapped_column(String(20))
    drivers: Mapped[list | None] = mapped_column(JSONB)
    consequences: Mapped[list | None] = mapped_column(JSONB)
    # Serialized graph.Edge objects (src/ai/interpret/graph.py) walked to
    # produce this interpretation -- the audit trail for "why does this
    # narrative connect X to Y."
    connections: Mapped[list | None] = mapped_column(JSONB)
    confidence: Mapped[float | None] = mapped_column(Numeric(4, 3))
    citations: Mapped[list | None] = mapped_column(JSONB)

    model: Mapped[str | None] = mapped_column(String(64))
    prompt_id: Mapped[str | None] = mapped_column(String(64))
    prompt_version: Mapped[int | None] = mapped_column(Integer)
    ai_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    __table_args__ = (
        # The compute-on-miss cache lookup key. Not a DB-level unique
        # constraint: metric_key is NULL for SUBJECT-scope rows, and
        # Postgres unique indexes treat NULLs as always-distinct (multiple
        # SUBJECT rows for the same subject/as_of wouldn't be rejected) --
        # dedup for that case is handled at the application layer
        # (select-then-upsert in src/ai/interpret/store.py), same pattern
        # already used elsewhere in this codebase for nullable-key rows.
        Index(
            "idx_interpretations_lookup",
            "subject_type", "subject_id", "scope", "metric_key", "as_of",
        ),
        Index("idx_interpretations_as_of", "as_of"),
    )
