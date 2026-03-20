"""Create security master tables (D2).

Revision ID: 003
Revises: 002
Create Date: 2026-03-17
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- securities ---
    op.create_table(
        "securities",
        sa.Column("security_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("security_type", sa.String(30), nullable=False, index=True),
        sa.Column("security_subtype", sa.String(50)),
        sa.Column(
            "issuer_entity_id",
            UUID(as_uuid=True),
            sa.ForeignKey("entities.entity_id"),
            index=True,
        ),
        # Names
        sa.Column("name", sa.String(500), nullable=False, index=True),
        sa.Column("short_name", sa.String(200)),
        sa.Column("description", sa.Text()),
        # Status
        sa.Column("status", sa.String(20), nullable=False, index=True),
        sa.Column("status_date", sa.Date()),
        sa.Column("status_reason", sa.String(500)),
        # Issuance
        sa.Column("issue_date", sa.Date()),
        sa.Column("maturity_date", sa.Date()),
        sa.Column("issue_amount", sa.Numeric(20, 2)),
        sa.Column(
            "issue_currency",
            sa.String(3),
            sa.ForeignKey("currencies.currency_code"),
        ),
        # Classification
        sa.Column("asset_class", sa.String(20), nullable=False, index=True),
        sa.Column("cfi_code", sa.String(6)),
        # Primary exchange
        sa.Column(
            "primary_exchange_mic",
            sa.String(4),
            sa.ForeignKey("exchanges.mic"),
            index=True,
        ),
        sa.Column(
            "primary_currency",
            sa.String(3),
            sa.ForeignKey("currencies.currency_code"),
        ),
        # Timestamps
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # --- security_identifiers ---
    op.create_table(
        "security_identifiers",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "security_id",
            UUID(as_uuid=True),
            sa.ForeignKey("securities.security_id"),
            nullable=False,
            index=True,
        ),
        sa.Column("identifier_type", sa.String(30), nullable=False),
        sa.Column("identifier_value", sa.String(50), nullable=False),
        sa.Column("source", sa.String(50)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "uq_security_identifier",
        "security_identifiers",
        ["identifier_type", "identifier_value"],
        unique=True,
    )

    # --- equity_details ---
    op.create_table(
        "equity_details",
        sa.Column(
            "security_id",
            UUID(as_uuid=True),
            sa.ForeignKey("securities.security_id"),
            primary_key=True,
        ),
        sa.Column("shares_outstanding", sa.Numeric(20, 2)),
        sa.Column("shares_authorized", sa.Numeric(20, 2)),
        sa.Column("float_shares", sa.Numeric(20, 2)),
        sa.Column("par_value", sa.Numeric(10, 4)),
        sa.Column(
            "par_value_currency",
            sa.String(3),
            sa.ForeignKey("currencies.currency_code"),
        ),
        sa.Column("voting_rights", sa.Boolean()),
        sa.Column("votes_per_share", sa.Numeric(5, 2)),
        sa.Column("dividend_frequency", sa.String(20)),
        sa.Column(
            "dividend_currency",
            sa.String(3),
            sa.ForeignKey("currencies.currency_code"),
        ),
        sa.Column("share_class", sa.String(5)),
        sa.Column("share_class_description", sa.String(200)),
        sa.Column("conversion_ratio", sa.Numeric(10, 4)),
    )

    # --- fixed_income_details ---
    op.create_table(
        "fixed_income_details",
        sa.Column(
            "security_id",
            UUID(as_uuid=True),
            sa.ForeignKey("securities.security_id"),
            primary_key=True,
        ),
        # Principal
        sa.Column("face_value", sa.Numeric(20, 4)),
        sa.Column(
            "face_currency",
            sa.String(3),
            sa.ForeignKey("currencies.currency_code"),
        ),
        sa.Column("minimum_denomination", sa.Numeric(20, 2)),
        # Coupon
        sa.Column("coupon_rate", sa.Numeric(10, 6)),
        sa.Column("coupon_type", sa.String(20)),
        sa.Column("coupon_frequency", sa.String(20)),
        sa.Column("day_count_convention", sa.String(20)),
        # Floating rate
        sa.Column("spread", sa.Numeric(10, 4)),
        sa.Column("reference_rate", sa.String(50)),
        sa.Column("reset_frequency", sa.String(20)),
        sa.Column("floor", sa.Numeric(10, 6)),
        sa.Column("cap", sa.Numeric(10, 6)),
        # Dates
        sa.Column("first_coupon_date", sa.Date()),
        sa.Column("last_coupon_date", sa.Date()),
        sa.Column("first_settlement_date", sa.Date()),
        # Seniority & security
        sa.Column("seniority", sa.String(30)),
        sa.Column("collateral_type", sa.String(200)),
        # Call/put
        sa.Column("callable", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("puttable", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        # Covenants
        sa.Column(
            "has_financial_covenants",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "has_negative_pledge",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "has_cross_default",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        # Credit
        sa.Column("rated", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )

    # --- credit_ratings ---
    op.create_table(
        "credit_ratings",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "security_id",
            UUID(as_uuid=True),
            sa.ForeignKey("securities.security_id"),
            nullable=False,
            index=True,
        ),
        sa.Column("agency", sa.String(50), nullable=False),
        sa.Column("rating", sa.String(10), nullable=False),
        sa.Column("outlook", sa.String(20)),
        sa.Column("rating_date", sa.Date()),
        sa.Column("source", sa.String(50)),
    )

    # --- call_put_schedule ---
    op.create_table(
        "call_put_schedule",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "security_id",
            UUID(as_uuid=True),
            sa.ForeignKey("securities.security_id"),
            nullable=False,
            index=True,
        ),
        sa.Column("schedule_type", sa.String(4), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("price", sa.Numeric(10, 4)),
        sa.Column("notes", sa.String(200)),
    )

    # --- eod_prices ---
    op.create_table(
        "eod_prices",
        sa.Column(
            "security_id",
            UUID(as_uuid=True),
            sa.ForeignKey("securities.security_id"),
            primary_key=True,
        ),
        sa.Column("price_date", sa.Date(), primary_key=True),
        sa.Column("open", sa.Numeric(18, 6)),
        sa.Column("high", sa.Numeric(18, 6)),
        sa.Column("low", sa.Numeric(18, 6)),
        sa.Column("close", sa.Numeric(18, 6)),
        sa.Column("close_adjusted", sa.Numeric(18, 6)),
        sa.Column("volume", sa.Numeric(20, 0)),
        sa.Column(
            "currency",
            sa.String(3),
            sa.ForeignKey("currencies.currency_code"),
        ),
        sa.Column("adjustment_factor", sa.Numeric(18, 10)),
        sa.Column("source", sa.String(50)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("eod_prices")
    op.drop_table("call_put_schedule")
    op.drop_table("credit_ratings")
    op.drop_table("fixed_income_details")
    op.drop_table("equity_details")
    op.drop_table("security_identifiers")
    op.drop_table("securities")
