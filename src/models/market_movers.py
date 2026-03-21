"""Market movers models (Pillar 2 Supplement – Part 5)."""

import uuid
from datetime import date

from sqlalchemy import Date, Index, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin


class MarketMoversSnapshot(TimestampMixin, Base):
    """Daily snapshot of market movers by category."""

    __tablename__ = "market_movers_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)
    category: Mapped[str] = mapped_column(String(20), nullable=False)
    sector: Mapped[str | None] = mapped_column(String(50))
    rankings: Mapped[dict | None] = mapped_column(JSONB)

    __table_args__ = (
        Index("idx_mm_date_category", "snapshot_date", "category"),
    )
