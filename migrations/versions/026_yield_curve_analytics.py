"""Yield curve fitted curves and analytics.

Revision ID: 026
Revises: 025
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "026"
down_revision = "025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- yield_curve_fitted ---
    op.create_table(
        "yield_curve_fitted",
        sa.Column("fit_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("curve_date", sa.Date, nullable=False),
        sa.Column("curve_type", sa.String(25), nullable=False),
        sa.Column("method", sa.String(20), nullable=False),
        sa.Column("beta0", sa.Numeric(10, 6)),
        sa.Column("beta1", sa.Numeric(10, 6)),
        sa.Column("beta2", sa.Numeric(10, 6)),
        sa.Column("tau", sa.Numeric(10, 6)),
        sa.Column("fit_error", sa.Numeric(10, 8)),
        sa.Column("fitted_rates", JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "idx_ycf_date_type_method",
        "yield_curve_fitted",
        ["curve_date", "curve_type", "method"],
        unique=True,
    )

    # --- curve_analytics ---
    op.create_table(
        "curve_analytics",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("curve_date", sa.Date, nullable=False, unique=True),
        sa.Column("spread_2s10s", sa.Numeric(8, 4)),
        sa.Column("spread_3m10y", sa.Numeric(8, 4)),
        sa.Column("steepness", sa.Numeric(8, 4)),
        sa.Column("curvature", sa.Numeric(8, 4)),
        sa.Column("breakeven_5y", sa.Numeric(8, 4)),
        sa.Column("breakeven_10y", sa.Numeric(8, 4)),
        sa.Column("is_inverted", sa.Boolean),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("curve_analytics")
    op.drop_table("yield_curve_fitted")
