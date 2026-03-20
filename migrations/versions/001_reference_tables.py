"""Create reference and classification tables (D8).

Revision ID: 001
Revises: None
Create Date: 2026-03-17
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- currencies (must come before countries due to FK) ---
    op.create_table(
        "currencies",
        sa.Column("currency_code", sa.String(3), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("numeric_code", sa.String(3)),
        sa.Column("minor_unit", sa.Integer()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )

    # --- countries ---
    op.create_table(
        "countries",
        sa.Column("country_code_alpha2", sa.String(2), primary_key=True),
        sa.Column("country_code_alpha3", sa.String(3), unique=True, nullable=False),
        sa.Column("country_code_numeric", sa.String(3)),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("official_name", sa.String(200)),
        sa.Column("capital", sa.String(100)),
        sa.Column("continent", sa.String(20)),
        sa.Column("region", sa.String(50)),
        sa.Column("subregion", sa.String(80)),
        sa.Column(
            "currency_code",
            sa.String(3),
            sa.ForeignKey("currencies.currency_code"),
        ),
        sa.Column("languages", JSONB),
        sa.Column("development_status", sa.String(20)),
        sa.Column("income_group", sa.String(50)),
        sa.Column("primary_exchange_mic", sa.String(4)),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )

    # --- exchanges ---
    op.create_table(
        "exchanges",
        sa.Column("mic", sa.String(4), primary_key=True),
        sa.Column("operating_mic", sa.String(4)),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("acronym", sa.String(20)),
        sa.Column(
            "country",
            sa.String(2),
            sa.ForeignKey("countries.country_code_alpha2"),
        ),
        sa.Column("city", sa.String(100)),
        sa.Column("timezone", sa.String(50)),
        sa.Column("market_type", sa.String(20)),
        sa.Column("asset_class", sa.String(20)),
        sa.Column("status", sa.String(20)),
        sa.Column("trading_hours", JSONB),
    )

    # --- gics_classifications ---
    op.create_table(
        "gics_classifications",
        sa.Column("sub_industry_code", sa.String(8), primary_key=True),
        sa.Column("sector_code", sa.String(2), nullable=False, index=True),
        sa.Column("sector_name", sa.String(100), nullable=False),
        sa.Column("industry_group_code", sa.String(4), nullable=False, index=True),
        sa.Column("industry_group_name", sa.String(100), nullable=False),
        sa.Column("industry_code", sa.String(6), nullable=False, index=True),
        sa.Column("industry_name", sa.String(100), nullable=False),
        sa.Column("sub_industry_name", sa.String(100), nullable=False),
        sa.Column("sector_description", sa.Text()),
        sa.Column("sub_industry_description", sa.Text()),
        sa.Column("effective_date", sa.Date()),
        sa.Column("version", sa.String(10)),
    )

    # --- sic_codes ---
    op.create_table(
        "sic_codes",
        sa.Column("sic_code", sa.String(4), primary_key=True),
        sa.Column("description", sa.String(200)),
        sa.Column("division", sa.String(1)),
        sa.Column("major_group", sa.String(2)),
    )

    # --- naics_codes ---
    op.create_table(
        "naics_codes",
        sa.Column("naics_code", sa.String(6), primary_key=True),
        sa.Column("description", sa.String(200)),
        sa.Column("sector_code", sa.String(2)),
    )

    # --- sic_to_gics_mapping ---
    op.create_table(
        "sic_to_gics_mapping",
        sa.Column(
            "sic_code",
            sa.String(4),
            sa.ForeignKey("sic_codes.sic_code"),
            primary_key=True,
        ),
        sa.Column(
            "gics_sub_industry_code",
            sa.String(8),
            sa.ForeignKey("gics_classifications.sub_industry_code"),
        ),
    )

    # --- trading_calendars ---
    op.create_table(
        "trading_calendars",
        sa.Column("calendar_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("calendar_code", sa.String(20), unique=True, nullable=False),
        sa.Column("name", sa.String(100)),
        sa.Column(
            "exchange_mic",
            sa.String(4),
            sa.ForeignKey("exchanges.mic"),
        ),
        sa.Column(
            "country",
            sa.String(2),
            sa.ForeignKey("countries.country_code_alpha2"),
        ),
    )

    # --- trading_days ---
    op.create_table(
        "trading_days",
        sa.Column(
            "calendar_id",
            UUID(as_uuid=True),
            sa.ForeignKey("trading_calendars.calendar_id"),
            primary_key=True,
        ),
        sa.Column("date", sa.Date(), primary_key=True),
        sa.Column("is_trading_day", sa.Boolean(), nullable=False),
        sa.Column("is_half_day", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("open_time", sa.Time()),
        sa.Column("close_time", sa.Time()),
        sa.Column("holiday_name", sa.String(100)),
        sa.Column("notes", sa.String(200)),
    )


def downgrade() -> None:
    op.drop_table("trading_days")
    op.drop_table("trading_calendars")
    op.drop_table("sic_to_gics_mapping")
    op.drop_table("naics_codes")
    op.drop_table("sic_codes")
    op.drop_table("gics_classifications")
    op.drop_table("exchanges")
    op.drop_table("countries")
    op.drop_table("currencies")
