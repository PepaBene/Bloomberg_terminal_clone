"""Create macroeconomic data tables (indicators, values, central bank policies).

Revision ID: 006
Revises: 005
Create Date: 2026-03-17
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- macro_indicators ---
    op.create_table(
        "macro_indicators",
        sa.Column("indicator_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("indicator_code", sa.String(50), nullable=False, unique=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("short_name", sa.String(100)),
        sa.Column("description", sa.Text()),
        # Classification
        sa.Column("category", sa.String(30), nullable=False),
        sa.Column("subcategory", sa.String(50)),
        sa.Column("country_code", sa.String(2), sa.ForeignKey("countries.country_code_alpha2")),
        sa.Column("region", sa.String(50)),
        # Scheduling
        sa.Column("frequency", sa.String(20), nullable=False),
        sa.Column("release_lag", sa.Integer()),
        sa.Column("typical_release_day", sa.String(50)),
        # Measurement
        sa.Column("unit", sa.String(50)),
        sa.Column("seasonal_adjustment", sa.String(10)),
        sa.Column("source_agency", sa.String(100)),
        sa.Column("source_url", sa.String(500)),
        sa.Column("source_series_id", sa.String(100)),
        sa.Column("base_period", sa.String(50)),
        sa.Column("start_date", sa.Date()),
        sa.Column("end_date", sa.Date()),
        # Transformation flags
        sa.Column("has_yoy", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("has_mom", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("has_level", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("has_annualized", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("metadata_json", JSONB),
        # Timestamps
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_macro_indicators_code", "macro_indicators", ["indicator_code"])
    op.create_index("idx_macro_indicators_category", "macro_indicators", ["category"])
    op.create_index("idx_macro_indicators_country", "macro_indicators", ["country_code"])
    op.create_index("idx_macro_indicators_country_category", "macro_indicators", ["country_code", "category"])

    # --- macro_values ---
    op.create_table(
        "macro_values",
        sa.Column("indicator_id", UUID(as_uuid=True), sa.ForeignKey("macro_indicators.indicator_id"), primary_key=True),
        sa.Column("observation_date", sa.Date(), primary_key=True),
        sa.Column("vintage_date", sa.Date(), primary_key=True),
        # Core
        sa.Column("value", sa.Numeric(20, 6), nullable=False),
        sa.Column("period_type", sa.String(20)),
        sa.Column("revision_number", sa.Integer(), nullable=False, server_default=sa.text("0")),
        # Pre-computed transforms
        sa.Column("value_yoy", sa.Numeric(20, 6)),
        sa.Column("value_yoy_percent", sa.Numeric(20, 6)),
        sa.Column("value_mom", sa.Numeric(20, 6)),
        sa.Column("value_mom_percent", sa.Numeric(20, 6)),
        sa.Column("value_qoq_annualized", sa.Numeric(20, 6)),
        # Release context
        sa.Column("is_preliminary", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_revised", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("previous_value", sa.Numeric(20, 6)),
        sa.Column("consensus_estimate", sa.Numeric(20, 6)),
        sa.Column("surprise", sa.Numeric(20, 6)),
        sa.Column("surprise_percent", sa.Numeric(20, 6)),
        # Metadata
        sa.Column("release_date", sa.Date()),
        sa.Column("release_timestamp", sa.DateTime(timezone=True)),
        sa.Column("source", sa.String(50)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_macro_values_indicator_date", "macro_values", ["indicator_id", "observation_date"])
    op.create_index("idx_macro_values_indicator_vintage", "macro_values", ["indicator_id", "vintage_date"])

    # --- central_bank_policies ---
    op.create_table(
        "central_bank_policies",
        sa.Column("policy_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("bank_code", sa.String(10), nullable=False),
        sa.Column("meeting_date", sa.Date(), nullable=False),
        sa.Column("decision_date", sa.Date()),
        sa.Column("announcement_time", sa.DateTime(timezone=True)),
        # Rate
        sa.Column("policy_rate", sa.Numeric(6, 4)),
        sa.Column("rate_change", sa.Numeric(6, 4)),
        sa.Column("previous_rate", sa.Numeric(6, 4)),
        sa.Column("rate_direction", sa.String(10)),
        # Voting
        sa.Column("votes_for", sa.Integer()),
        sa.Column("votes_against", sa.Integer()),
        sa.Column("votes_abstain", sa.Integer()),
        sa.Column("dissenting_members", JSONB),
        sa.Column("guidance_tone", sa.String(20)),
        # Statements
        sa.Column("statement_summary", sa.Text()),
        sa.Column("statement_url", sa.String(500)),
        sa.Column("minutes_url", sa.String(500)),
        sa.Column("minutes_date", sa.Date()),
        # Next
        sa.Column("next_meeting_date", sa.Date()),
        sa.Column("source", sa.String(50)),
        # Timestamps
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_central_bank_code", "central_bank_policies", ["bank_code"])
    op.create_index("uq_central_bank_meeting", "central_bank_policies", ["bank_code", "meeting_date"], unique=True)


def downgrade() -> None:
    op.drop_table("central_bank_policies")
    op.drop_table("macro_values")
    op.drop_table("macro_indicators")
