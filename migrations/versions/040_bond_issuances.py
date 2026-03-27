"""D11 FI Supplement P7: Bond Issuance Database.

Revision ID: 040
Revises: 039
"""

import sqlalchemy as sa
from alembic import op

revision = "040"
down_revision = "039"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "bond_issuances",
        sa.Column("issuance_id", sa.UUID(), primary_key=True),
        sa.Column("issuer_entity_id", sa.UUID(), sa.ForeignKey("entities.entity_id"), nullable=False),
        sa.Column("bond_id", sa.UUID(), nullable=True),
        sa.Column("pricing_date", sa.Date()),
        sa.Column("settlement_date", sa.Date()),
        sa.Column("announcement_date", sa.Date()),
        sa.Column("coupon_rate", sa.Numeric(8, 6)),
        sa.Column("maturity_date", sa.Date()),
        sa.Column("seniority", sa.String(30)),
        sa.Column("issue_price", sa.Numeric(10, 6)),
        sa.Column("issue_yield", sa.Numeric(8, 6)),
        sa.Column("initial_talk_low_bps", sa.Integer()),
        sa.Column("initial_talk_high_bps", sa.Integer()),
        sa.Column("final_spread_bps", sa.Integer()),
        sa.Column("tightening_bps", sa.Integer()),
        sa.Column("announced_size_mm", sa.Numeric(12, 2)),
        sa.Column("issued_size_mm", sa.Numeric(12, 2)),
        sa.Column("lead_left_bookrunner", sa.String(200)),
        sa.Column("all_bookrunners", sa.JSON()),
        sa.Column("use_of_proceeds", sa.String(30)),
        sa.Column("currency", sa.String(3)),
        sa.Column("is_benchmark", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("is_144a", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("is_registered", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_issuance_entity", "bond_issuances", ["issuer_entity_id"])
    op.create_index("idx_issuance_pricing_date", "bond_issuances", ["pricing_date"])


def downgrade():
    op.drop_index("idx_issuance_pricing_date", table_name="bond_issuances")
    op.drop_index("idx_issuance_entity", table_name="bond_issuances")
    op.drop_table("bond_issuances")
