"""Add commodity_inventories table (real supply/demand signal for R-023).

Revision ID: 090
Revises: 089
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "090"
down_revision = "089"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "commodity_inventories",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("commodity_code", sa.String(20), nullable=False, index=True),
        sa.Column("as_of_date", sa.Date(), nullable=False),
        sa.Column("stock_level", sa.Numeric(20, 4), nullable=False),
        sa.Column("stock_unit", sa.String(30)),
        sa.Column("metric_name", sa.String(100)),
        sa.Column("source", sa.String(20)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        comment="Periodic commodity stock/inventory levels (supply-side reports)",
    )
    op.create_index(
        "uq_commodity_inventory_code_date", "commodity_inventories",
        ["commodity_code", "as_of_date"], unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_commodity_inventory_code_date", table_name="commodity_inventories")
    op.drop_table("commodity_inventories")
