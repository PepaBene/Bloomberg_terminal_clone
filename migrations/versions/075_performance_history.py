"""Pillar 4 Phase 2: Performance measurement snapshots.

Revision ID: 075
Revises: 074
"""

import sqlalchemy as sa
from alembic import op

revision = "075"
down_revision = "074"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "performance_snapshots",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("portfolio_id", sa.UUID(), sa.ForeignKey("portfolios.id"), nullable=False, index=True),
        sa.Column("period_type", sa.String(10), nullable=False),
        sa.Column("period_start", sa.Date, nullable=False),
        sa.Column("period_end", sa.Date, nullable=False),
        sa.Column("twr_return", sa.Numeric(12, 8)),
        sa.Column("mwr_return", sa.Numeric(12, 8)),
        sa.Column("benchmark_return", sa.Numeric(12, 8)),
        sa.Column("active_return", sa.Numeric(12, 8)),
        sa.Column("sharpe_ratio", sa.Numeric(10, 6)),
        sa.Column("sortino_ratio", sa.Numeric(10, 6)),
        sa.Column("information_ratio", sa.Numeric(10, 6)),
        sa.Column("tracking_error", sa.Numeric(10, 6)),
        sa.Column("max_drawdown", sa.Numeric(10, 6)),
        sa.Column("calmar_ratio", sa.Numeric(10, 6)),
        sa.Column("beta", sa.Numeric(10, 6)),
        sa.Column("alpha", sa.Numeric(10, 6)),
        sa.Column("volatility", sa.Numeric(10, 6)),
        sa.Column("up_capture", sa.Numeric(10, 6)),
        sa.Column("down_capture", sa.Numeric(10, 6)),
        sa.Column("batting_average", sa.Numeric(10, 6)),
        sa.Column("best_day", sa.Numeric(12, 8)),
        sa.Column("worst_day", sa.Numeric(12, 8)),
        sa.Column("positive_days", sa.Integer),
        sa.Column("negative_days", sa.Integer),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("portfolio_id", "period_type", "period_end", name="uq_perf_portfolio_type_end"),
    )


def downgrade() -> None:
    op.drop_table("performance_snapshots")
