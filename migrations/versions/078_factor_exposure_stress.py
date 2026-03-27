"""Pillar 4 Phase 3: Factor exposures and stress test results.

Revision ID: 078
Revises: 077
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "078"
down_revision = "077"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "factor_exposure_snapshots",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("portfolio_id", sa.UUID(), sa.ForeignKey("portfolios.id"), nullable=False, index=True),
        sa.Column("snapshot_date", sa.Date, nullable=False),
        sa.Column("value_exposure", sa.Numeric(8, 4)),
        sa.Column("growth_exposure", sa.Numeric(8, 4)),
        sa.Column("momentum_exposure", sa.Numeric(8, 4)),
        sa.Column("quality_exposure", sa.Numeric(8, 4)),
        sa.Column("size_exposure", sa.Numeric(8, 4)),
        sa.Column("low_vol_exposure", sa.Numeric(8, 4)),
        sa.Column("benchmark_value", sa.Numeric(8, 4)),
        sa.Column("benchmark_growth", sa.Numeric(8, 4)),
        sa.Column("benchmark_momentum", sa.Numeric(8, 4)),
        sa.Column("benchmark_quality", sa.Numeric(8, 4)),
        sa.Column("benchmark_size", sa.Numeric(8, 4)),
        sa.Column("benchmark_low_vol", sa.Numeric(8, 4)),
        sa.Column("active_exposures", JSONB),
        sa.Column("factor_contributions", JSONB),
        sa.Column("unintended_flags", JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.UniqueConstraint("portfolio_id", "snapshot_date", name="uq_factor_portfolio_date"),
    )

    op.create_table(
        "stress_test_results",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("portfolio_id", sa.UUID(), sa.ForeignKey("portfolios.id"), nullable=False, index=True),
        sa.Column("snapshot_date", sa.Date, nullable=False),
        sa.Column("scenario_name", sa.String(50), nullable=False),
        sa.Column("scenario_type", sa.String(15), nullable=False),
        sa.Column("total_pnl_dollar", sa.Numeric(20, 2)),
        sa.Column("total_pnl_percent", sa.Numeric(10, 6)),
        sa.Column("max_drawdown_pct", sa.Numeric(10, 6)),
        sa.Column("recovery_time_months", sa.Numeric(5, 1)),
        sa.Column("per_position_pnl", JSONB),
        sa.Column("worst_positions", JSONB),
        sa.Column("scenario_params", JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("portfolio_id", "snapshot_date", "scenario_name", name="uq_stress_portfolio_date_scenario"),
    )


def downgrade() -> None:
    op.drop_table("stress_test_results")
    op.drop_table("factor_exposure_snapshots")
