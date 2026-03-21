"""Custom index and portfolio upload tables.

Revision ID: 029
Revises: 028
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "029"
down_revision = "028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "custom_indices",
        sa.Column("index_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("weighting_method", sa.String(20)),
        sa.Column("rebalance_frequency", sa.String(20)),
        sa.Column("max_constituents", sa.Integer),
        sa.Column("min_market_cap", sa.Numeric(20, 2)),
        sa.Column("inception_date", sa.Date),
        sa.Column("total_return_inception", sa.Numeric(10, 6)),
        sa.Column("annualized_return", sa.Numeric(10, 6)),
        sa.Column("annualized_volatility", sa.Numeric(8, 6)),
        sa.Column("sharpe_ratio", sa.Numeric(8, 4)),
        sa.Column("max_drawdown", sa.Numeric(8, 6)),
        sa.Column("created_by", sa.String(100)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "index_constituents",
        sa.Column("constituent_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("index_id", UUID(as_uuid=True), sa.ForeignKey("custom_indices.index_id"), nullable=False),
        sa.Column("security_id", UUID(as_uuid=True), sa.ForeignKey("securities.security_id"), nullable=False),
        sa.Column("weight", sa.Numeric(8, 6)),
        sa.Column("added_date", sa.Date, nullable=False),
        sa.Column("removed_date", sa.Date),
        sa.Column("is_active", sa.Boolean, nullable=False, default=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_ic_index_sec_date", "index_constituents", ["index_id", "security_id", "added_date"], unique=True)

    op.create_table(
        "index_performance",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("index_id", UUID(as_uuid=True), sa.ForeignKey("custom_indices.index_id"), nullable=False),
        sa.Column("perf_date", sa.Date, nullable=False),
        sa.Column("index_level", sa.Numeric(12, 4)),
        sa.Column("daily_return", sa.Numeric(10, 8)),
        sa.Column("cumulative_return", sa.Numeric(10, 6)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_ip_index_date", "index_performance", ["index_id", "perf_date"], unique=True)

    op.create_table(
        "portfolio_uploads",
        sa.Column("upload_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("file_name", sa.String(500), nullable=False),
        sa.Column("file_format", sa.String(10), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("total_rows", sa.Integer),
        sa.Column("matched_rows", sa.Integer),
        sa.Column("unmatched_rows", sa.Integer),
        sa.Column("mapping_results", JSONB),
        sa.Column("parsed_holdings", JSONB),
        sa.Column("created_by", sa.String(100)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("portfolio_uploads")
    op.drop_table("index_performance")
    op.drop_table("index_constituents")
    op.drop_table("custom_indices")
