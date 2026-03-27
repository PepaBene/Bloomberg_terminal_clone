"""Pillar 3 Phase 4A: Anomaly detection events and configurable rules.

Revision ID: 064
Revises: 063
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "064"
down_revision = "063"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "detected_anomalies",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("entity_id", sa.UUID(), sa.ForeignKey("entities.entity_id"), nullable=False, index=True),
        sa.Column("anomaly_type", sa.String(25), nullable=False),
        sa.Column("severity_score", sa.Numeric(5, 2), nullable=False),
        sa.Column("detected_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("anomaly_window_start", sa.Date()),
        sa.Column("anomaly_window_end", sa.Date()),
        sa.Column("lookback_period", sa.String(10)),
        sa.Column("observed_value", sa.Numeric(15, 4)),
        sa.Column("expected_value", sa.Numeric(15, 4)),
        sa.Column("z_score", sa.Numeric(8, 4)),
        sa.Column("percentile_rank", sa.Numeric(5, 2)),
        sa.Column("contextual_analysis", JSONB),
        sa.Column("related_data", JSONB),
        sa.Column("ai_narrative", sa.Text()),
        sa.Column("recommended_actions", JSONB),
        sa.Column("confidence_level", sa.Numeric(3, 2)),
        sa.Column("is_acknowledged", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("acknowledged_by", sa.String(100)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "anomaly_rules",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("anomaly_type", sa.String(25), nullable=False),
        sa.Column("rule_name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("threshold_config", JSONB),
        sa.Column("is_enabled", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("anomaly_rules")
    op.drop_table("detected_anomalies")
