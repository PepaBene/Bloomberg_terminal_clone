"""D11 FI Supplement P8: Agency Bond Reference.

Revision ID: 041
Revises: 040
"""

import sqlalchemy as sa
from alembic import op

revision = "041"
down_revision = "040"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "agency_bonds",
        sa.Column("bond_id", sa.UUID(), primary_key=True),
        sa.Column("cusip", sa.String(9), nullable=False, unique=True),
        sa.Column("issuer_name", sa.String(200)),
        sa.Column("agency_type", sa.String(20)),
        sa.Column("backing_type", sa.String(25)),
        sa.Column("coupon_rate", sa.Numeric(8, 6)),
        sa.Column("coupon_type", sa.String(20)),
        sa.Column("coupon_frequency", sa.Integer()),
        sa.Column("maturity_date", sa.Date(), nullable=False),
        sa.Column("issue_date", sa.Date()),
        sa.Column("original_amount_mm", sa.Numeric(12, 2)),
        sa.Column("outstanding_amount_mm", sa.Numeric(12, 2)),
        sa.Column("currency", sa.String(3)),
        sa.Column("is_callable", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("first_call_date", sa.Date()),
        sa.Column("is_outstanding", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("status", sa.String(20)),
        sa.Column("security_id", sa.UUID()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_agency_bonds_cusip", "agency_bonds", ["cusip"])
    op.create_index("idx_agency_type_maturity", "agency_bonds", ["agency_type", "maturity_date"])


def downgrade():
    op.drop_table("agency_bonds")
