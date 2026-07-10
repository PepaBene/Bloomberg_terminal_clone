"""ai_call_log — LLM telemetry (cost/latency/token accounting).

Revision ID: 084
Revises: 083
"""

import sqlalchemy as sa
from alembic import op

revision = "084"
down_revision = "083"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_call_log",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("feature", sa.String(64), nullable=False),
        sa.Column("model", sa.String(64), nullable=False),
        sa.Column("prompt_id", sa.String(64)),
        sa.Column("prompt_version", sa.Integer()),
        sa.Column("user_id", sa.String(100)),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("cache_write_tokens", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("cache_read_tokens", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("cost_usd", sa.Numeric(12, 6), nullable=False, server_default=sa.text("0")),
        sa.Column("latency_ms", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("success", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("error", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_ai_call_log_feature_created", "ai_call_log", ["feature", "created_at"])
    op.create_index("idx_ai_call_log_user_created", "ai_call_log", ["user_id", "created_at"])


def downgrade() -> None:
    op.drop_index("idx_ai_call_log_user_created", table_name="ai_call_log")
    op.drop_index("idx_ai_call_log_feature_created", table_name="ai_call_log")
    op.drop_table("ai_call_log")
