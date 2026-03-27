"""Pillar 3 Phase 4B: Analyst Q&A sessions and feedback tracking.

Revision ID: 067
Revises: 066
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "067"
down_revision = "066"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "qa_sessions",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("user_id", sa.String(100), nullable=False, index=True),
        sa.Column("entity_id", sa.UUID(), sa.ForeignKey("entities.entity_id"), nullable=True),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("answer_text", sa.Text()),
        sa.Column("answer_type", sa.String(20)),
        sa.Column("confidence_level", sa.Numeric(3, 2)),
        sa.Column("confidence_narrative", sa.Text()),
        sa.Column("sources", JSONB),
        sa.Column("supporting_data", JSONB),
        sa.Column("follow_up_suggestions", JSONB),
        sa.Column("data_completeness", JSONB),
        sa.Column("user_rating", sa.Integer(), nullable=True),
        sa.Column("execution_time_ms", sa.Integer()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "qa_feedback",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("session_id", sa.UUID(), sa.ForeignKey("qa_sessions.id"), nullable=False),
        sa.Column("rating", sa.Integer()),
        sa.Column("feedback_text", sa.Text()),
        sa.Column("is_accurate", sa.Boolean()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("qa_feedback")
    op.drop_table("qa_sessions")
