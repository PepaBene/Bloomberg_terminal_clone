"""Pillar 1 FI Supplement D11.1: Treasury Securities table.

Revision ID: 035
Revises: 034
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "035"
down_revision = "034"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "treasury_securities",
        sa.Column("treasury_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("cusip", sa.String(9), nullable=False),
        sa.Column("treasury_type", sa.String(25), nullable=False),
        # Terms
        sa.Column("coupon_rate", sa.Numeric(8, 6)),
        sa.Column("coupon_frequency", sa.Integer),
        sa.Column("issue_date", sa.Date),
        sa.Column("maturity_date", sa.Date, nullable=False),
        # Outstanding
        sa.Column("original_issue_amount", sa.Numeric(20, 2)),
        sa.Column("outstanding_amount", sa.Numeric(20, 2)),
        # Auction data
        sa.Column("auction_date", sa.Date),
        sa.Column("auction_high_yield", sa.Numeric(8, 6)),
        sa.Column("auction_price", sa.Numeric(10, 6)),
        sa.Column("auction_bid_to_cover", sa.Numeric(6, 3)),
        sa.Column("auction_median_yield", sa.Numeric(8, 6)),
        sa.Column("auction_low_yield", sa.Numeric(8, 6)),
        # TIPS
        sa.Column("is_inflation_indexed", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("index_ratio", sa.Numeric(12, 8)),
        sa.Column("ref_cpi_date", sa.Date),
        sa.Column("ref_cpi_value", sa.Numeric(10, 4)),
        # STRIPS
        sa.Column("is_stripped", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("stripped_from_cusip", sa.String(9)),
        sa.Column("strip_type", sa.String(15)),
        # Status
        sa.Column("is_outstanding", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("status", sa.String(20)),
        # Linkage
        sa.Column("security_id", UUID(as_uuid=True)),
        # Timestamps
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    # Indexes
    op.create_unique_constraint("uq_treasury_cusip", "treasury_securities", ["cusip"])
    op.create_index("idx_treasury_cusip", "treasury_securities", ["cusip"])
    op.create_index("idx_treasury_type", "treasury_securities", ["treasury_type"])
    op.create_index("idx_treas_maturity", "treasury_securities", ["maturity_date"])
    op.create_index("idx_treas_type_outstanding", "treasury_securities", ["treasury_type", "is_outstanding"])


def downgrade() -> None:
    op.drop_table("treasury_securities")
