"""Layer 2 (News/Information) output storage — AI_THREE_LAYER_REBUILD_PLAN.md
§4.6: on-demand Deep Research.

One row per research run: a multi-step agent's gathered, corroborated,
cited report on a subject or free-text question -- the qualitative
"later-relevant" information not already captured by this app's structured
data (management commentary, competitive dynamics, regulatory exposure,
supply-chain signals, controversies, expert views).
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Index, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class ResearchReport(Base):
    """A completed (or in-progress/failed) Deep Research run."""

    __tablename__ = "research_reports"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # Polymorphic subject -- same convention as Interpretation
    # (src/models/interpretation.py): a plain string, not a UUID FK, since
    # FREE_TEXT subjects (a question with no entity_id at all) are a first-
    # class case here, unlike Layer 1 which is always subject-anchored.
    subject_type: Mapped[str] = mapped_column(String(20), nullable=False)  # ENTITY|SECTOR|MACRO|FREE_TEXT
    subject_id: Mapped[str | None] = mapped_column(String(100))  # NULL for FREE_TEXT
    subject_label: Mapped[str] = mapped_column(String(500), nullable=False)  # human-readable (entity name, or the free-text question itself)
    focus: Mapped[str | None] = mapped_column(Text)

    # list[{title, content, citations: [str]}] -- flexible rather than
    # fixed named fields (management_commentary, competitive_dynamics,
    # ...): not every subject surfaces all of §4.6's example angles, and
    # forcing empty sections for the ones that don't apply is worse than a
    # variable-length list of only what the agent actually found.
    sections: Mapped[list | None] = mapped_column(JSONB)
    # list[{url_or_citation, title, source_trust}] -- deduped across all
    # sections, corroborated/trust-weighted per §4.6.
    sources: Mapped[list | None] = mapped_column(JSONB)
    confidence: Mapped[float | None] = mapped_column(Numeric(4, 3))

    model: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDING")  # PENDING|RUNNING|COMPLETE|FAILED
    error: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index("idx_research_reports_subject", "subject_type", "subject_id"),
        Index("idx_research_reports_created_at", "created_at"),
    )
