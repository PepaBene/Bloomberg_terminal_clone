"""Layer 3 (Financial Adviser) output storage —
AI_THREE_LAYER_REBUILD_PLAN.md §5.4: guardrail-filtered recommendations
persisted from an adviser conversation.
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class AdviceRecommendation(Base):
    """A single adviser recommendation, already guardrail-filtered before
    it reached this table (see ``src/ai/adviser/store.py``): evidence-
    backed and compliance-passing by the time it's persisted."""

    __tablename__ = "advice_recommendations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # Free-form string, not a UUID FK to `users` -- matches
    # Portfolio.user_id's existing convention; portfolio ownership isn't
    # anchored to the real `users` table anywhere in this codebase today.
    user_id: Mapped[str] = mapped_column(String(100), nullable=False)
    portfolio_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("portfolios.id", ondelete="CASCADE"), nullable=False,
    )

    kind: Mapped[str] = mapped_column(String(20), nullable=False)  # REBALANCE|RISK|OPPORTUNITY|THESIS|HEDGE
    action: Mapped[dict | None] = mapped_column(JSONB)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    evidence: Mapped[list | None] = mapped_column(JSONB)
    # Real computed output from src/services/portfolio_advisory.py
    # (dataclasses.asdict()), NOT the LLM's own account of what its tools
    # returned -- see adviser.py::verify_recommendation.
    whatif_impact: Mapped[dict | None] = mapped_column(JSONB)
    compliance: Mapped[dict | None] = mapped_column(JSONB)
    confidence: Mapped[float | None] = mapped_column(Numeric(4, 3))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="PROPOSED")  # PROPOSED|ACCEPTED|DISMISSED

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    __table_args__ = (
        Index("idx_advice_recommendations_user_portfolio", "user_id", "portfolio_id"),
        Index("idx_advice_recommendations_created_at", "created_at"),
    )
