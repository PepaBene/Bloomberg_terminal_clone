"""Pillar 3 Phase 3B Part 8: Commodity profiles, prices, and company exposure tables.

Revision ID: 058
Revises: 057
"""

import sqlalchemy as sa
from alembic import op

revision = "058"
down_revision = "057"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- commodity_profiles ---
    op.create_table(
        "commodity_profiles",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("commodity_code", sa.String(20), nullable=False, unique=True),
        sa.Column("commodity_name", sa.String(100)),
        sa.Column("category", sa.String(20)),
        sa.Column("unit", sa.String(30)),
        sa.Column("primary_source", sa.String(20)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # --- commodity_prices ---
    op.create_table(
        "commodity_prices",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("commodity_code", sa.String(20), nullable=False),
        sa.Column("price_date", sa.Date(), nullable=False),
        sa.Column("close_price", sa.Numeric(15, 4)),
        sa.Column("open_price", sa.Numeric(15, 4)),
        sa.Column("high_price", sa.Numeric(15, 4)),
        sa.Column("low_price", sa.Numeric(15, 4)),
        sa.Column("volume", sa.Numeric(20, 2)),
        sa.Column("source", sa.String(20)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("commodity_code", "price_date", name="uq_cp_commodity_date"),
    )
    op.create_index("idx_cp_commodity", "commodity_prices", ["commodity_code"])

    # --- commodity_company_exposures ---
    op.create_table(
        "commodity_company_exposures",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("commodity_code", sa.String(20), nullable=False),
        sa.Column(
            "entity_id",
            sa.UUID(),
            sa.ForeignKey("entities.entity_id"),
            nullable=False,
        ),
        sa.Column("exposure_type", sa.String(20)),
        sa.Column("exposure_description", sa.String(500)),
        sa.Column("sensitivity_score", sa.Numeric(5, 2)),
        sa.Column("historical_correlation", sa.Numeric(5, 4)),
        sa.Column("source", sa.String(20)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("commodity_company_exposures")
    op.drop_table("commodity_prices")
    op.drop_table("commodity_profiles")
