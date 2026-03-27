"""D11 FI Supplement P6: Credit spread indices and percentiles.

Revision ID: 039
Revises: 038
"""

import sqlalchemy as sa
from alembic import op

revision = "039"
down_revision = "038"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "credit_spread_indices",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("series_id", sa.String(30), nullable=False),
        sa.Column("observation_date", sa.Date(), nullable=False),
        sa.Column("index_name", sa.String(200)),
        sa.Column("rating_category", sa.String(10)),
        sa.Column("spread_bps", sa.Numeric(10, 4)),
        sa.Column("total_return_index", sa.Numeric(12, 4)),
        sa.Column("source", sa.String(30)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("series_id", "observation_date", name="uq_spread_series_date"),
    )
    op.create_index("idx_spread_series_id", "credit_spread_indices", ["series_id"])
    op.create_index("idx_spread_observation_date", "credit_spread_indices", ["observation_date"])

    op.create_table(
        "credit_spread_percentiles",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("series_id", sa.String(30), nullable=False),
        sa.Column("as_of_date", sa.Date(), nullable=False),
        sa.Column("lookback_years", sa.Integer(), nullable=False),
        sa.Column("percentile_rank", sa.Numeric(5, 2)),
        sa.Column("current_oas", sa.Numeric(10, 4)),
        sa.Column("min_oas", sa.Numeric(10, 4)),
        sa.Column("max_oas", sa.Numeric(10, 4)),
        sa.Column("mean_oas", sa.Numeric(10, 4)),
        sa.Column("std_dev", sa.Numeric(10, 4)),
        sa.Column("z_score", sa.Numeric(8, 4)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint(
            "series_id", "as_of_date", "lookback_years",
            name="uq_percentile_series_date_lookback",
        ),
    )


def downgrade():
    op.drop_table("credit_spread_percentiles")
    op.drop_table("credit_spread_indices")
