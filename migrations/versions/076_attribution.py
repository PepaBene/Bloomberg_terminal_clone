"""Pillar 4 Phase 2: Attribution results and report requests.

Revision ID: 076
Revises: 075
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "076"
down_revision = "075"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "attribution_results",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("portfolio_id", sa.UUID(), sa.ForeignKey("portfolios.id"), nullable=False, index=True),
        sa.Column("period_start", sa.Date, nullable=False),
        sa.Column("period_end", sa.Date, nullable=False),
        sa.Column("attribution_type", sa.String(10), nullable=False),
        sa.Column("total_portfolio_return", sa.Numeric(12, 8)),
        sa.Column("total_benchmark_return", sa.Numeric(12, 8)),
        sa.Column("total_active_return", sa.Numeric(12, 8)),
        sa.Column("total_allocation", sa.Numeric(12, 8)),
        sa.Column("total_selection", sa.Numeric(12, 8)),
        sa.Column("total_interaction", sa.Numeric(12, 8)),
        sa.Column("residual", sa.Numeric(12, 8)),
        sa.Column("sector_detail", JSONB),
        sa.Column("security_detail", JSONB),
        sa.Column("factor_detail", JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("portfolio_id", "attribution_type", "period_end", name="uq_attr_portfolio_type_end"),
    )

    op.create_table(
        "report_requests",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("portfolio_id", sa.UUID(), sa.ForeignKey("portfolios.id"), nullable=False),
        sa.Column("report_type", sa.String(20), nullable=False),
        sa.Column("format", sa.String(10), nullable=False),
        sa.Column("period_start", sa.Date),
        sa.Column("period_end", sa.Date),
        sa.Column("parameters", JSONB),
        sa.Column("status", sa.String(15), server_default="COMPLETED"),
        sa.Column("result_data", JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("report_requests")
    op.drop_table("attribution_results")
