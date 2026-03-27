"""Pillar 3 Phase 3C Part 14: Alert expansion table and alert_rules category column.

Revision ID: 061
Revises: 060
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "061"
down_revision = "060"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- fi_alert_configs ---
    op.create_table(
        "fi_alert_configs",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("user_id", sa.String(100), nullable=False),
        sa.Column("alert_type", sa.String(40), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("threshold_value", sa.Numeric(10, 2)),
        sa.Column("entity_scope", JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Add alert_category column to existing alert_rules table
    op.add_column("alert_rules", sa.Column("alert_category", sa.String(30)))


def downgrade() -> None:
    op.drop_column("alert_rules", "alert_category")
    op.drop_table("fi_alert_configs")
