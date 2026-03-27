"""Pillar 3 Phase 3A Part 1: Industry intelligence tables.

Revision ID: 053
Revises: 052
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "053"
down_revision = "052"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- industry_profiles ---
    op.create_table(
        "industry_profiles",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("gics_code", sa.String(8), nullable=False),
        sa.Column("gics_level", sa.String(20), nullable=False),
        sa.Column("gics_name", sa.String(200), nullable=False),
        sa.Column("as_of_date", sa.Date(), nullable=False),
        sa.Column("company_count", sa.Integer()),
        sa.Column("total_market_cap", sa.Numeric(20, 2)),
        sa.Column("median_market_cap", sa.Numeric(20, 2)),
        sa.Column("revenue_growth_3y_cagr", sa.Numeric(8, 4)),
        sa.Column("revenue_growth_5y_cagr", sa.Numeric(8, 4)),
        sa.Column("revenue_dispersion", sa.Numeric(8, 4)),
        sa.Column("median_gross_margin", sa.Numeric(8, 4)),
        sa.Column("median_operating_margin", sa.Numeric(8, 4)),
        sa.Column("median_capex_to_revenue", sa.Numeric(8, 4)),
        sa.Column("median_rd_to_revenue", sa.Numeric(8, 4)),
        sa.Column("median_roic", sa.Numeric(8, 4)),
        sa.Column("median_wacc", sa.Numeric(8, 4)),
        sa.Column("roic_wacc_spread", sa.Numeric(8, 4)),
        sa.Column("roic_dispersion", sa.Numeric(8, 4)),
        sa.Column("capital_cycle_indicator", sa.String(20)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("gics_code", "as_of_date", name="uq_ip_gics_date"),
    )
    op.create_index("idx_ip_gics_code", "industry_profiles", ["gics_code"])

    # --- industry_cycle_positions ---
    op.create_table(
        "industry_cycle_positions",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("gics_code", sa.String(8), nullable=False),
        sa.Column("as_of_date", sa.Date(), nullable=False),
        sa.Column("revenue_growth_acceleration", sa.Numeric(8, 4)),
        sa.Column("capacity_utilization_proxy", sa.Numeric(8, 4)),
        sa.Column("inventory_dynamics", sa.String(20)),
        sa.Column("inventory_to_sales_trend", sa.Numeric(8, 4)),
        sa.Column("margin_cycle_direction", sa.String(20)),
        sa.Column("operating_margin_momentum", sa.Numeric(8, 4)),
        sa.Column("cycle_position", sa.String(15), nullable=False),
        sa.Column("cycle_confidence", sa.Numeric(5, 2)),
        sa.Column("prior_cycle_position", sa.String(15)),
        sa.Column("cycle_duration_quarters", sa.Integer()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("gics_code", "as_of_date", name="uq_icp_gics_date"),
    )
    op.create_index("idx_icp_gics_code", "industry_cycle_positions", ["gics_code"])

    # --- industry_competitive_structures ---
    op.create_table(
        "industry_competitive_structures",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("gics_code", sa.String(8), nullable=False),
        sa.Column("as_of_date", sa.Date(), nullable=False),
        sa.Column("hhi_index", sa.Numeric(10, 2)),
        sa.Column("hhi_classification", sa.String(20)),
        sa.Column("top3_market_share", sa.Numeric(8, 4)),
        sa.Column("top5_market_share", sa.Numeric(8, 4)),
        sa.Column("top10_market_share", sa.Numeric(8, 4)),
        sa.Column("consolidation_trend", sa.String(20)),
        sa.Column("consolidation_5y_delta", sa.Numeric(8, 4)),
        sa.Column("barrier_to_entry", sa.String(10)),
        sa.Column("barrier_factors", JSONB),
        sa.Column("pricing_power", sa.String(10)),
        sa.Column("pricing_power_evidence", JSONB),
        sa.Column("competitive_dynamics", sa.String(30)),
        sa.Column("market_share_data", JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("gics_code", "as_of_date", name="uq_ics_gics_date"),
    )
    op.create_index("idx_ics_gics_code", "industry_competitive_structures", ["gics_code"])


def downgrade() -> None:
    op.drop_table("industry_competitive_structures")
    op.drop_table("industry_cycle_positions")
    op.drop_table("industry_profiles")
