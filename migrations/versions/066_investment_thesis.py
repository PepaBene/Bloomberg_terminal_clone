"""Pillar 3 Phase 4B: Investment thesis generation and version tracking.

Revision ID: 066
Revises: 065
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "066"
down_revision = "065"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "investment_theses",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("entity_id", sa.UUID(), sa.ForeignKey("entities.entity_id"), nullable=False, index=True),
        sa.Column("analyst_id", sa.String(100), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("thesis_title", sa.String(200)),
        sa.Column("investment_horizon", sa.String(10)),
        sa.Column("conviction_level", sa.String(15)),
        sa.Column("executive_summary", sa.Text()),
        sa.Column("key_drivers", JSONB),
        sa.Column("primary_risks", JSONB),
        sa.Column("valuation_scenarios", JSONB),
        sa.Column("catalysts", JSONB),
        sa.Column("quality_metrics", JSONB),
        sa.Column("elevator_pitch", sa.String(500)),
        sa.Column("slide_outline", JSONB),
        sa.Column("ai_enabled", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("entity_id", "analyst_id", "version"),
    )

    op.create_table(
        "thesis_versions",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("thesis_id", sa.UUID(), sa.ForeignKey("investment_theses.id"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("conviction_change", sa.Numeric(5, 2)),
        sa.Column("updated_drivers", JSONB),
        sa.Column("analyst_note", sa.Text()),
        sa.Column("snapshot_data", JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("thesis_versions")
    op.drop_table("investment_theses")
