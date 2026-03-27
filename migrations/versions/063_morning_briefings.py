"""Pillar 3 Phase 4A: Morning briefings and user preferences.

Revision ID: 063
Revises: 062
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "063"
down_revision = "062"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "morning_briefings",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("user_id", sa.String(100), nullable=False, index=True),
        sa.Column("briefing_date", sa.Date(), nullable=False),
        sa.Column("regional_context", sa.String(10)),
        sa.Column("executive_summary", sa.Text()),
        sa.Column("portfolio_impact", JSONB),
        sa.Column("key_news", JSONB),
        sa.Column("thesis_updates", JSONB),
        sa.Column("macro_context", JSONB),
        sa.Column("actionable_insights", JSONB),
        sa.Column("delivery_format", sa.String(15)),
        sa.Column("ai_enabled", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "briefing_date", name="uq_briefing_user_date"),
    )

    op.create_table(
        "briefing_preferences",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("user_id", sa.String(100), nullable=False, unique=True),
        sa.Column("portfolio_entity_ids", JSONB),
        sa.Column("watchlist_entity_ids", JSONB),
        sa.Column("sector_focus", JSONB),
        sa.Column("risk_tolerance", sa.String(15)),
        sa.Column("delivery_time_utc", sa.String(5)),
        sa.Column("delivery_format", sa.String(15)),
        sa.Column("timezone", sa.String(30)),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("briefing_preferences")
    op.drop_table("morning_briefings")
