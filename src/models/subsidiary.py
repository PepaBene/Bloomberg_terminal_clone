"""Corporate subsidiary / org-tree data (EX-21 exhibits).

Feeds `complex_structure.analyze_subsidiary_tree()` (src/engines/
complex_structure.py) -- previously that engine's subsidiary-tree dimension
had no data source anywhere in the platform.
"""

import uuid
from datetime import date

from sqlalchemy import Boolean, Date, ForeignKey, Index, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin


class Subsidiary(TimestampMixin, Base):
    """A subsidiary of a registrant, from an SEC Exhibit 21 filing."""

    __tablename__ = "subsidiaries"

    subsidiary_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    parent_entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entities.entity_id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    jurisdiction: Mapped[str | None] = mapped_column(String(100))
    # Parent subsidiary's name, when EX-21 discloses nesting (most filings are
    # flat -- a single list with no explicit tree structure).
    parent_subsidiary_name: Mapped[str | None] = mapped_column(String(300))
    ownership_pct: Mapped[float | None] = mapped_column(Numeric(5, 2))
    is_vie: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    source_filing_accession: Mapped[str | None] = mapped_column(String(25))
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False)

    __table_args__ = (
        Index(
            "uq_subsidiary_parent_name_asof",
            "parent_entity_id", "name", "as_of_date",
            unique=True,
        ),
    )
