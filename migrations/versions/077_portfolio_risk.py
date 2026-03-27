"""Pillar 4 Phase 3: Portfolio risk — VaR snapshots and concentration analysis.

Revision ID: 077
Revises: 076
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "077"
down_revision = "076"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "portfolio_var_snapshots",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("portfolio_id", sa.UUID(), sa.ForeignKey("portfolios.id"), nullable=False, index=True),
        sa.Column("snapshot_date", sa.Date, nullable=False),
        sa.Column("var_1d_95", sa.Numeric(15, 4)),
        sa.Column("var_1d_99", sa.Numeric(15, 4)),
        sa.Column("var_10d_95", sa.Numeric(15, 4)),
        sa.Column("var_10d_99", sa.Numeric(15, 4)),
        sa.Column("undiversified_var", sa.Numeric(15, 4)),
        sa.Column("diversification_ratio", sa.Numeric(8, 4)),
        sa.Column("marginal_var", JSONB),
        sa.Column("component_var", JSONB),
        sa.Column("incremental_var", JSONB),
        sa.Column("portfolio_nav", sa.Numeric(20, 2)),
        sa.Column("method", sa.String(20), server_default="HISTORICAL"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.UniqueConstraint("portfolio_id", "snapshot_date", name="uq_var_portfolio_date"),
    )

    op.create_table(
        "concentration_analyses",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("portfolio_id", sa.UUID(), sa.ForeignKey("portfolios.id"), nullable=False, index=True),
        sa.Column("snapshot_date", sa.Date, nullable=False),
        sa.Column("hhi_position", sa.Numeric(10, 4)),
        sa.Column("hhi_sector", sa.Numeric(10, 4)),
        sa.Column("hhi_industry", sa.Numeric(10, 4)),
        sa.Column("largest_position_weight", sa.Numeric(8, 4)),
        sa.Column("top_5_weight", sa.Numeric(8, 4)),
        sa.Column("top_10_weight", sa.Numeric(8, 4)),
        sa.Column("effective_num_positions", sa.Numeric(8, 2)),
        sa.Column("concentration_classification", sa.String(15)),
        sa.Column("sector_detail", JSONB),
        sa.Column("industry_detail", JSONB),
        sa.Column("issuer_detail", JSONB),
        sa.Column("geographic_detail", JSONB),
        sa.Column("flags", JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.UniqueConstraint("portfolio_id", "snapshot_date", name="uq_conc_portfolio_date"),
    )


def downgrade() -> None:
    op.drop_table("concentration_analyses")
    op.drop_table("portfolio_var_snapshots")
