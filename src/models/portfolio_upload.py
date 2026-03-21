"""Portfolio upload models (Pillar 2 Supplement – Part 4)."""

import uuid

from sqlalchemy import Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin


class PortfolioUpload(TimestampMixin, Base):
    """A portfolio upload session."""

    __tablename__ = "portfolio_uploads"

    upload_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    file_name: Mapped[str] = mapped_column(String(500), nullable=False)
    file_format: Mapped[str] = mapped_column(String(10), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDING")
    total_rows: Mapped[int | None] = mapped_column(Integer)
    matched_rows: Mapped[int | None] = mapped_column(Integer)
    unmatched_rows: Mapped[int | None] = mapped_column(Integer)
    mapping_results: Mapped[dict | None] = mapped_column(JSONB)
    parsed_holdings: Mapped[dict | None] = mapped_column(JSONB)
    created_by: Mapped[str | None] = mapped_column(String(100))
