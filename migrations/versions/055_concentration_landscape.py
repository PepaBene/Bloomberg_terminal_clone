"""Pillar 3 Phase 3A Part 1: Concentration risk and competitive landscape tables.

Revision ID: 055
Revises: 054
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "055"
down_revision = "054"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- concentration_risk_assessments ---
    op.create_table(
        "concentration_risk_assessments",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column(
            "entity_id",
            sa.UUID(),
            sa.ForeignKey("entities.entity_id"),
            nullable=False,
        ),
        sa.Column("as_of_date", sa.Date(), nullable=False),
        sa.Column("customer_top1_pct", sa.Numeric(8, 4)),
        sa.Column("customer_top5_pct", sa.Numeric(8, 4)),
        sa.Column("customer_top10_pct", sa.Numeric(8, 4)),
        sa.Column("customer_concentration_risk", sa.String(15)),
        sa.Column("customer_details", JSONB),
        sa.Column("supplier_single_source_count", sa.Integer()),
        sa.Column("supplier_critical_count", sa.Integer()),
        sa.Column("supplier_geographic_concentration", JSONB),
        sa.Column("supplier_concentration_risk", sa.String(15)),
        sa.Column("supplier_details", JSONB),
        sa.Column("geographic_revenue_breakdown", JSONB),
        sa.Column("geographic_top1_pct", sa.Numeric(8, 4)),
        sa.Column("geographic_hhi", sa.Numeric(10, 2)),
        sa.Column("fx_exposure_score", sa.Numeric(5, 2)),
        sa.Column("geographic_concentration_risk", sa.String(15)),
        sa.Column("overall_concentration_risk", sa.String(15)),
        sa.Column("overall_risk_score", sa.Numeric(5, 2)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("entity_id", "as_of_date", name="uq_cra_entity_date"),
    )
    op.create_index("idx_cra_entity", "concentration_risk_assessments", ["entity_id"])

    # --- competitive_landscapes ---
    op.create_table(
        "competitive_landscapes",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column(
            "entity_id",
            sa.UUID(),
            sa.ForeignKey("entities.entity_id"),
            nullable=False,
        ),
        sa.Column("gics_code", sa.String(8), nullable=False),
        sa.Column("as_of_date", sa.Date(), nullable=False),
        sa.Column("peer_group", JSONB),
        sa.Column("market_share_est_pct", sa.Numeric(8, 4)),
        sa.Column("market_share_rank", sa.Integer()),
        sa.Column("revenue_growth_vs_peers", sa.Numeric(8, 4)),
        sa.Column("margin_vs_peers", sa.Numeric(8, 4)),
        sa.Column("roic_vs_peers", sa.Numeric(8, 4)),
        sa.Column("valuation_vs_peers", JSONB),
        sa.Column("share_gainer", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("value_chain_position", sa.String(20)),
        sa.Column("competitive_advantages", JSONB),
        sa.Column("competitive_threats", JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("entity_id", "as_of_date", name="uq_cl_entity_date"),
    )
    op.create_index("idx_cl_entity", "competitive_landscapes", ["entity_id"])


def downgrade() -> None:
    op.drop_table("competitive_landscapes")
    op.drop_table("concentration_risk_assessments")
