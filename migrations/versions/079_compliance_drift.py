"""Pillar 4 Phase 3: Compliance rules/results and drift monitoring.

Revision ID: 079
Revises: 078
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "079"
down_revision = "078"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "compliance_rules",
        sa.Column("rule_id", sa.UUID(), primary_key=True),
        sa.Column("portfolio_id", sa.UUID(), sa.ForeignKey("portfolios.id"), nullable=False, index=True),
        sa.Column("rule_name", sa.String(100), nullable=False),
        sa.Column("rule_type", sa.String(30), nullable=False),
        sa.Column("rule_definition", JSONB, nullable=False),
        sa.Column("threshold", sa.Numeric(15, 6)),
        sa.Column("upper_threshold", sa.Numeric(15, 6)),
        sa.Column("comparison", sa.String(10), nullable=False),
        sa.Column("severity", sa.String(10), server_default="WARNING"),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    op.create_table(
        "compliance_results",
        sa.Column("result_id", sa.UUID(), primary_key=True),
        sa.Column("portfolio_id", sa.UUID(), sa.ForeignKey("portfolios.id"), nullable=False, index=True),
        sa.Column("rule_id", sa.UUID(), sa.ForeignKey("compliance_rules.rule_id"), nullable=False),
        sa.Column("check_date", sa.Date, nullable=False),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("current_value", sa.Numeric(15, 6)),
        sa.Column("threshold_value", sa.Numeric(15, 6)),
        sa.Column("breach_positions", JSONB),
        sa.Column("notes", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("portfolio_id", "rule_id", "check_date", name="uq_compliance_portfolio_rule_date"),
    )

    op.create_table(
        "drift_snapshots",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("portfolio_id", sa.UUID(), sa.ForeignKey("portfolios.id"), nullable=False, index=True),
        sa.Column("snapshot_date", sa.Date, nullable=False),
        sa.Column("total_drift_pct", sa.Numeric(8, 4)),
        sa.Column("max_position_drift_pct", sa.Numeric(8, 4)),
        sa.Column("max_sector_drift_pct", sa.Numeric(8, 4)),
        sa.Column("drift_classification", sa.String(15)),
        sa.Column("position_drifts", JSONB),
        sa.Column("sector_drifts", JSONB),
        sa.Column("rebalance_needed", sa.Boolean, server_default=sa.text("false")),
        sa.Column("target_allocation", JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.UniqueConstraint("portfolio_id", "snapshot_date", name="uq_drift_portfolio_date"),
    )


def downgrade() -> None:
    op.drop_table("drift_snapshots")
    op.drop_table("compliance_results")
    op.drop_table("compliance_rules")
