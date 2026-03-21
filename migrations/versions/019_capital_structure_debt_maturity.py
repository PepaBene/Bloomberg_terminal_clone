"""019 – Capital structure & debt maturity tables (Pillar 1 Supplement §2-3).

Revision ID: 019
Revises: 018
"""

from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "019"
down_revision: Union[str, None] = "018"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    # -- Capital Structures --------------------------------------------------
    op.create_table(
        "capital_structures",
        sa.Column("capital_structure_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("entity_id", UUID(as_uuid=True), sa.ForeignKey("entities.entity_id"), nullable=False, index=True),
        sa.Column("as_of_date", sa.Date, nullable=False),
        sa.Column("filing_id", UUID(as_uuid=True), nullable=True),
        sa.Column("total_debt", sa.Numeric(20, 2), nullable=True),
        sa.Column("total_long_term_debt", sa.Numeric(20, 2), nullable=True),
        sa.Column("total_short_term_debt", sa.Numeric(20, 2), nullable=True),
        sa.Column("total_preferred_stock", sa.Numeric(20, 2), nullable=True),
        sa.Column("net_debt", sa.Numeric(20, 2), nullable=True),
        sa.Column("total_capitalization", sa.Numeric(20, 2), nullable=True),
        sa.Column("debt_to_capitalization", sa.Numeric(8, 4), nullable=True),
        sa.Column("source", sa.String(20), nullable=True),
        sa.Column("extraction_method", sa.String(30), nullable=True),
        sa.Column("confidence_score", sa.Numeric(4, 3), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_capstruct_entity_date", "capital_structures", ["entity_id", "as_of_date"])

    # -- Debt Tranches -------------------------------------------------------
    op.create_table(
        "debt_tranches",
        sa.Column("tranche_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("entity_id", UUID(as_uuid=True), sa.ForeignKey("entities.entity_id"), nullable=False, index=True),
        sa.Column("capital_structure_id", UUID(as_uuid=True), sa.ForeignKey("capital_structures.capital_structure_id"), nullable=False),
        sa.Column("instrument_name", sa.String(300), nullable=True),
        sa.Column("instrument_type", sa.String(40), nullable=True),
        sa.Column("principal_amount", sa.Numeric(20, 2), nullable=True),
        sa.Column("original_amount", sa.Numeric(20, 2), nullable=True),
        sa.Column("currency", sa.String(3), sa.ForeignKey("currencies.currency_code"), nullable=True),
        sa.Column("coupon_rate", sa.Numeric(8, 4), nullable=True),
        sa.Column("coupon_type", sa.String(10), nullable=True),
        sa.Column("floating_reference", sa.String(20), nullable=True),
        sa.Column("floating_spread", sa.Numeric(8, 2), nullable=True),
        sa.Column("issue_date", sa.Date, nullable=True),
        sa.Column("maturity_date", sa.Date, nullable=True),
        sa.Column("first_call_date", sa.Date, nullable=True),
        sa.Column("next_put_date", sa.Date, nullable=True),
        sa.Column("seniority_rank", sa.Integer, nullable=True),
        sa.Column("seniority_type", sa.String(30), nullable=True),
        sa.Column("collateral_description", sa.Text, nullable=True),
        sa.Column("has_financial_covenants", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("has_change_of_control", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("has_cross_default", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("security_id", UUID(as_uuid=True), sa.ForeignKey("securities.security_id"), nullable=True),
        sa.Column("source_filing_id", UUID(as_uuid=True), nullable=True),
        sa.Column("extracted_from", sa.String(30), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_tranche_entity_maturity", "debt_tranches", ["entity_id", "maturity_date"])
    op.create_index("idx_tranche_capstruct", "debt_tranches", ["capital_structure_id"])

    # -- Debt Maturity Profiles ----------------------------------------------
    op.create_table(
        "debt_maturity_profiles",
        sa.Column("profile_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("entity_id", UUID(as_uuid=True), sa.ForeignKey("entities.entity_id"), nullable=False, index=True),
        sa.Column("as_of_date", sa.Date, nullable=False),
        sa.Column("filing_id", UUID(as_uuid=True), nullable=True),
        sa.Column("debt_maturing_1yr", sa.Numeric(20, 2), nullable=True),
        sa.Column("debt_maturing_2yr", sa.Numeric(20, 2), nullable=True),
        sa.Column("debt_maturing_3yr", sa.Numeric(20, 2), nullable=True),
        sa.Column("pct_debt_maturing_1yr", sa.Numeric(8, 4), nullable=True),
        sa.Column("pct_debt_maturing_3yr", sa.Numeric(8, 4), nullable=True),
        sa.Column("weighted_avg_maturity_years", sa.Numeric(8, 2), nullable=True),
        sa.Column("weighted_avg_coupon", sa.Numeric(8, 4), nullable=True),
        sa.Column("cash_to_1yr_maturities", sa.Numeric(8, 4), nullable=True),
        sa.Column("fcf_to_1yr_maturities", sa.Numeric(8, 4), nullable=True),
        sa.Column("maturity_wall_alert", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("near_term_stress", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_maturity_entity_date", "debt_maturity_profiles", ["entity_id", "as_of_date"])

    # -- Maturity Buckets ----------------------------------------------------
    op.create_table(
        "maturity_buckets",
        sa.Column("bucket_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("profile_id", UUID(as_uuid=True), sa.ForeignKey("debt_maturity_profiles.profile_id"), nullable=False),
        sa.Column("year", sa.Integer, nullable=False),
        sa.Column("total_amount", sa.Numeric(20, 2), nullable=True),
        sa.Column("breakdown", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_bucket_profile_year", "maturity_buckets", ["profile_id", "year"])


def downgrade() -> None:
    op.drop_index("idx_bucket_profile_year", table_name="maturity_buckets")
    op.drop_table("maturity_buckets")
    op.drop_index("idx_maturity_entity_date", table_name="debt_maturity_profiles")
    op.drop_table("debt_maturity_profiles")
    op.drop_index("idx_tranche_capstruct", table_name="debt_tranches")
    op.drop_index("idx_tranche_entity_maturity", table_name="debt_tranches")
    op.drop_table("debt_tranches")
    op.drop_index("idx_capstruct_entity_date", table_name="capital_structures")
    op.drop_table("capital_structures")
