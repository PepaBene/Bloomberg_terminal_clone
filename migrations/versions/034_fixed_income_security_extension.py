"""D11 FI Supplement: Extend Security + FixedIncomeDetails for bond linkage.

Revision ID: 034
Revises: 033
"""

revision = "034"
down_revision = "033"

from alembic import op
import sqlalchemy as sa


def upgrade() -> None:
    # Security table: add bond CUSIP linkage columns
    op.add_column("securities", sa.Column("corporate_bond_cusip", sa.String(9), nullable=True))
    op.add_column("securities", sa.Column("treasury_cusip", sa.String(9), nullable=True))
    op.create_index("idx_securities_corp_bond_cusip", "securities", ["corporate_bond_cusip"])
    op.create_index("idx_securities_treasury_cusip", "securities", ["treasury_cusip"])

    # FixedIncomeDetails table: add D11 extension columns
    op.add_column("fixed_income_details", sa.Column("use_of_proceeds", sa.String(30), nullable=True))
    op.add_column("fixed_income_details", sa.Column("liquidity_tier", sa.String(20), nullable=True))
    op.add_column("fixed_income_details", sa.Column("benchmark_treasury_cusip", sa.String(9), nullable=True))
    op.add_column("fixed_income_details", sa.Column("oas_bps", sa.Numeric(8, 2), nullable=True))


def downgrade() -> None:
    op.drop_column("fixed_income_details", "oas_bps")
    op.drop_column("fixed_income_details", "benchmark_treasury_cusip")
    op.drop_column("fixed_income_details", "liquidity_tier")
    op.drop_column("fixed_income_details", "use_of_proceeds")

    op.drop_index("idx_securities_treasury_cusip", table_name="securities")
    op.drop_index("idx_securities_corp_bond_cusip", table_name="securities")
    op.drop_column("securities", "treasury_cusip")
    op.drop_column("securities", "corporate_bond_cusip")
