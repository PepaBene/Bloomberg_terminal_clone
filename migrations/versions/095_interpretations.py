"""Add interpretations table (Layer 1 — Interpreter output storage).

Revision ID: 095
Revises: 094
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "095"
down_revision = "094"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "interpretations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("subject_type", sa.String(20), nullable=False),
        sa.Column("subject_id", sa.String(100), nullable=False),
        sa.Column("scope", sa.String(10), nullable=False),
        sa.Column("metric_key", sa.String(100)),
        sa.Column("as_of", sa.Date(), nullable=False),
        sa.Column("analytics_version", sa.String(20)),
        sa.Column("interpretation", sa.Text(), nullable=False),
        sa.Column("trend", sa.String(20)),
        sa.Column("direction", sa.String(20)),
        sa.Column("drivers", JSONB),
        sa.Column("consequences", JSONB),
        sa.Column("connections", JSONB),
        sa.Column("confidence", sa.Numeric(4, 3)),
        sa.Column("citations", JSONB),
        sa.Column("model", sa.String(64)),
        sa.Column("prompt_id", sa.String(64)),
        sa.Column("prompt_version", sa.Integer()),
        sa.Column("ai_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        comment="Layer 1 (Interpreter) grounded interpretations of metrics/subjects",
    )
    op.create_index(
        "idx_interpretations_lookup", "interpretations",
        ["subject_type", "subject_id", "scope", "metric_key", "as_of"],
    )
    op.create_index("idx_interpretations_as_of", "interpretations", ["as_of"])


def downgrade() -> None:
    op.drop_index("idx_interpretations_as_of", table_name="interpretations")
    op.drop_index("idx_interpretations_lookup", table_name="interpretations")
    op.drop_table("interpretations")
