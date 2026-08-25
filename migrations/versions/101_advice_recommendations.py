"""Add advice_recommendations table (Layer 3 — Financial Adviser, §5.4).

Revision ID: 101
Revises: 100
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "101"
down_revision = "100"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "advice_recommendations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        # Free-form string, not a UUID FK to users -- matches Portfolio.user_id's
        # existing convention (portfolio ownership isn't anchored to the real
        # `users` table anywhere in this codebase today).
        sa.Column("user_id", sa.String(100), nullable=False),
        sa.Column("portfolio_id", UUID(as_uuid=True), sa.ForeignKey("portfolios.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),  # REBALANCE|RISK|OPPORTUNITY|THESIS|HEDGE
        sa.Column("action", JSONB()),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("evidence", JSONB()),
        sa.Column("whatif_impact", JSONB()),
        sa.Column("compliance", JSONB()),
        sa.Column("confidence", sa.Numeric(4, 3)),
        sa.Column("status", sa.String(20), nullable=False, server_default="PROPOSED"),  # PROPOSED|ACCEPTED|DISMISSED
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        comment="Layer 3 (Financial Adviser) recommendations, guardrail-filtered before persistence (§5.4)",
    )
    op.create_index("idx_advice_recommendations_user_portfolio", "advice_recommendations", ["user_id", "portfolio_id"])
    op.create_index("idx_advice_recommendations_created_at", "advice_recommendations", ["created_at"])


def downgrade() -> None:
    op.drop_index("idx_advice_recommendations_created_at", table_name="advice_recommendations")
    op.drop_index("idx_advice_recommendations_user_portfolio", table_name="advice_recommendations")
    op.drop_table("advice_recommendations")
