"""Backtesting tables.

Revision ID: 028
Revises: 027
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "028"
down_revision = "027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "backtest_runs",
        sa.Column("backtest_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("strategy_definition", JSONB),
        sa.Column("start_date", sa.Date, nullable=False),
        sa.Column("end_date", sa.Date, nullable=False),
        sa.Column("benchmark", sa.String(30)),
        sa.Column("weighting_method", sa.String(20)),
        sa.Column("rebalance_frequency", sa.String(20)),
        sa.Column("max_positions", sa.Integer),
        sa.Column("transaction_cost_bps", sa.Numeric(6, 2)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "backtest_results",
        sa.Column("result_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("backtest_id", UUID(as_uuid=True), sa.ForeignKey("backtest_runs.backtest_id"), nullable=False),
        sa.Column("total_return", sa.Numeric(10, 6)),
        sa.Column("annualized_return", sa.Numeric(10, 6)),
        sa.Column("benchmark_return", sa.Numeric(10, 6)),
        sa.Column("excess_return", sa.Numeric(10, 6)),
        sa.Column("sharpe_ratio", sa.Numeric(8, 4)),
        sa.Column("sortino_ratio", sa.Numeric(8, 4)),
        sa.Column("max_drawdown", sa.Numeric(8, 6)),
        sa.Column("max_drawdown_duration_days", sa.Integer),
        sa.Column("annualized_volatility", sa.Numeric(8, 6)),
        sa.Column("beta", sa.Numeric(6, 4)),
        sa.Column("tracking_error", sa.Numeric(8, 6)),
        sa.Column("information_ratio", sa.Numeric(8, 4)),
        sa.Column("win_rate", sa.Numeric(6, 4)),
        sa.Column("avg_win", sa.Numeric(8, 6)),
        sa.Column("avg_loss", sa.Numeric(8, 6)),
        sa.Column("turnover_annual", sa.Numeric(6, 4)),
        sa.Column("total_trades", sa.Integer),
        sa.Column("monthly_returns", JSONB),
        sa.Column("period_holdings", JSONB),
        sa.Column("sector_attribution", JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_br_backtest_id", "backtest_results", ["backtest_id"])


def downgrade() -> None:
    op.drop_table("backtest_results")
    op.drop_table("backtest_runs")
