"""084 - Pillar 1 model/migration reconciliation.

Reconciles a batch of Pillar 1 model-layer fixes (src/models/*.py) that were
never followed up with a matching Alembic migration, so a fresh database
built purely from `migrations/versions/` drifted out of sync with the ORM.

Covers:
  * P1-M-005/006/009: missing FKs on corporate_bonds (security_id ->
    securities, guarantor_entity_id -> entities, currency -> currencies)
  * P1-M-007/008: missing FKs on capital_structures.filing_id and
    debt_maturity_profiles.filing_id -> filings
  * P1-M-010: current_credit_ratings' single non-partial unique index let
    two rows with the same (entity_id, agency) and NULL rating_type both
    satisfy uniqueness (NULL != NULL in SQL); replaced with two partial
    unique indexes matching the model's current __table_args__.
  * P1-M-018/019/020/021: composite indexes present on the models only
    (short_interest, bond_trades, yield_curve_snapshots, kpi_values)
  * P1-M-028: financial_periods.data_version CHECK constraint
  * P1-M-029: eod_prices.volume — model uses BigInteger, table still had
    Numeric(20, 0)
  * P1-M-002: entities/entities_history/resolution_queue.confidence_score
    widened from Numeric(3,2) to Numeric(5,4) — src/resolution/matcher.py
    computes confidence to 4 decimal places, which silently truncated
    under the old precision (e.g. 0.8534 -> 0.85).
  * P1-M-030: zero_coupon_curves.tenor_years narrowed from Numeric(6,2) to
    Numeric(5,2) plus a CHECK constraint bounding it to [0, 100] years.

Revision ID: 084
Revises: 083
"""

from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "084"
down_revision: Union[str, None] = "083"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    # -- P1-M-005/006/009: corporate_bonds missing FKs -----------------------
    op.create_foreign_key(
        "fk_corporate_bonds_security_id",
        "corporate_bonds",
        "securities",
        ["security_id"],
        ["security_id"],
    )
    op.create_foreign_key(
        "fk_corporate_bonds_guarantor_entity_id",
        "corporate_bonds",
        "entities",
        ["guarantor_entity_id"],
        ["entity_id"],
    )
    op.create_foreign_key(
        "fk_corporate_bonds_currency",
        "corporate_bonds",
        "currencies",
        ["currency"],
        ["currency_code"],
    )

    # -- P1-M-007/008: capital_structures / debt_maturity_profiles filing_id -
    op.create_foreign_key(
        "fk_capital_structures_filing_id",
        "capital_structures",
        "filings",
        ["filing_id"],
        ["filing_id"],
    )
    op.create_foreign_key(
        "fk_debt_maturity_profiles_filing_id",
        "debt_maturity_profiles",
        "filings",
        ["filing_id"],
        ["filing_id"],
    )

    # -- P1-M-010: current_credit_ratings NULL-rating_type dedup gap --------
    op.drop_index("idx_current_rating_entity_agency", table_name="current_credit_ratings")
    op.create_index(
        "idx_current_rating_entity_agency_typed",
        "current_credit_ratings",
        ["entity_id", "agency", "rating_type"],
        unique=True,
        postgresql_where=sa.text("rating_type IS NOT NULL"),
    )
    op.create_index(
        "idx_current_rating_entity_agency_untyped",
        "current_credit_ratings",
        ["entity_id", "agency"],
        unique=True,
        postgresql_where=sa.text("rating_type IS NULL"),
    )

    # -- P1-M-018/019/020/021: composite indexes model-only ------------------
    op.create_index(
        "idx_short_interest_security_settle",
        "short_interest",
        ["security_id", "settlement_date"],
    )
    op.create_index(
        "idx_bond_trade_bond_settle",
        "bond_trades",
        ["bond_id", "settlement_date"],
    )
    op.create_index(
        "idx_yc_curve_type",
        "yield_curve_snapshots",
        ["curve_type"],
    )
    op.create_index(
        "idx_kpi_values_kpi_period",
        "kpi_values",
        ["kpi_id", "period_id"],
    )

    # -- P1-M-028: financial_periods.data_version CHECK ----------------------
    op.create_check_constraint(
        "ck_financial_period_data_version",
        "financial_periods",
        "data_version IN ('AS_REPORTED', 'RESTATED', 'PRELIMINARY')",
    )

    # -- P1-M-029: eod_prices.volume Numeric(20,0) -> BIGINT -----------------
    op.alter_column(
        "eod_prices",
        "volume",
        type_=sa.BigInteger(),
        postgresql_using="volume::bigint",
        existing_nullable=True,
    )

    # -- P1-M-002: widen confidence_score Numeric(3,2) -> Numeric(5,4) -------
    op.alter_column(
        "entities",
        "confidence_score",
        type_=sa.Numeric(5, 4),
        existing_nullable=True,
    )
    op.alter_column(
        "entities_history",
        "confidence_score",
        type_=sa.Numeric(5, 4),
        existing_nullable=True,
    )
    op.alter_column(
        "resolution_queue",
        "confidence_score",
        type_=sa.Numeric(5, 4),
        existing_nullable=False,
    )

    # -- P1-M-030: tenor_years Numeric(6,2) -> Numeric(5,2) + range CHECK ----
    op.alter_column(
        "zero_coupon_curves",
        "tenor_years",
        type_=sa.Numeric(5, 2),
        existing_nullable=False,
    )
    op.create_check_constraint(
        "ck_zc_tenor_years_range",
        "zero_coupon_curves",
        "tenor_years >= 0 AND tenor_years <= 100",
    )


def downgrade() -> None:
    op.drop_constraint("ck_zc_tenor_years_range", "zero_coupon_curves", type_="check")
    op.alter_column(
        "zero_coupon_curves",
        "tenor_years",
        type_=sa.Numeric(6, 2),
        existing_nullable=False,
    )

    op.alter_column(
        "resolution_queue",
        "confidence_score",
        type_=sa.Numeric(3, 2),
        existing_nullable=False,
    )
    op.alter_column(
        "entities_history",
        "confidence_score",
        type_=sa.Numeric(3, 2),
        existing_nullable=True,
    )
    op.alter_column(
        "entities",
        "confidence_score",
        type_=sa.Numeric(3, 2),
        existing_nullable=True,
    )

    op.alter_column(
        "eod_prices",
        "volume",
        type_=sa.Numeric(20, 0),
        postgresql_using="volume::numeric(20,0)",
        existing_nullable=True,
    )

    op.drop_constraint("ck_financial_period_data_version", "financial_periods", type_="check")

    op.drop_index("idx_kpi_values_kpi_period", table_name="kpi_values")
    op.drop_index("idx_yc_curve_type", table_name="yield_curve_snapshots")
    op.drop_index("idx_bond_trade_bond_settle", table_name="bond_trades")
    op.drop_index("idx_short_interest_security_settle", table_name="short_interest")

    op.drop_index("idx_current_rating_entity_agency_untyped", table_name="current_credit_ratings")
    op.drop_index("idx_current_rating_entity_agency_typed", table_name="current_credit_ratings")
    op.create_index(
        "idx_current_rating_entity_agency",
        "current_credit_ratings",
        ["entity_id", "agency", "rating_type"],
        unique=True,
    )

    op.drop_constraint("fk_debt_maturity_profiles_filing_id", "debt_maturity_profiles", type_="foreignkey")
    op.drop_constraint("fk_capital_structures_filing_id", "capital_structures", type_="foreignkey")

    op.drop_constraint("fk_corporate_bonds_currency", "corporate_bonds", type_="foreignkey")
    op.drop_constraint("fk_corporate_bonds_guarantor_entity_id", "corporate_bonds", type_="foreignkey")
    op.drop_constraint("fk_corporate_bonds_security_id", "corporate_bonds", type_="foreignkey")
