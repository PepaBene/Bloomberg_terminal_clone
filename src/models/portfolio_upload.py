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
    # P4-M-019: ownership so an upload can eventually be scoped/authorized
    # per caller. Mirrors Portfolio.user_id (src/models/portfolio.py): a
    # free-form identity string resolved from the JWT ``sub`` claim, or the
    # shared anonymous fallback identity when no Bearer token is present
    # (ANONYMOUS_USER/_resolve_user in src/api/routers/portfolios.py) --
    # not a hard FK to ``users``, for the same reason Portfolio.user_id
    # (src/models/portfolio.py) isn't one: this identity isn't guaranteed
    # to correspond to a real ``users`` row.
    user_id: Mapped[str | None] = mapped_column(String(100), index=True)
    created_by: Mapped[str | None] = mapped_column(String(100))
