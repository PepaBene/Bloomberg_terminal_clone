"""Pillar 3 Phase 3B Part 8: Country risk and geopolitical event tables.

Revision ID: 056
Revises: 055
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "056"
down_revision = "055"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- country_profiles ---
    op.create_table(
        "country_profiles",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("country_code", sa.String(3), nullable=False, unique=True),
        sa.Column("country_name", sa.String(100), nullable=False),
        sa.Column("region", sa.String(30)),
        sa.Column("income_group", sa.String(30)),
        sa.Column("is_g20", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("is_eu", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("population", sa.Numeric(15, 0)),
        sa.Column("gdp_usd", sa.Numeric(20, 2)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # --- country_risk_scores ---
    op.create_table(
        "country_risk_scores",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("country_code", sa.String(3), nullable=False),
        sa.Column("as_of_date", sa.Date(), nullable=False),
        sa.Column("political_risk_score", sa.Numeric(5, 2)),
        sa.Column("economic_risk_score", sa.Numeric(5, 2)),
        sa.Column("sanctions_risk_score", sa.Numeric(5, 2)),
        sa.Column("composite_risk_score", sa.Numeric(5, 2)),
        sa.Column("risk_classification", sa.String(15)),
        sa.Column("risk_trend", sa.String(15)),
        sa.Column("political_components", JSONB),
        sa.Column("economic_components", JSONB),
        sa.Column("sanctions_components", JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("country_code", "as_of_date", name="uq_crs_country_date"),
    )
    op.create_index("idx_crs_country", "country_risk_scores", ["country_code"])

    # --- company_country_exposures ---
    op.create_table(
        "company_country_exposures",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column(
            "entity_id",
            sa.UUID(),
            sa.ForeignKey("entities.entity_id"),
            nullable=False,
        ),
        sa.Column("country_code", sa.String(3), nullable=False),
        sa.Column("exposure_type", sa.String(20)),
        sa.Column("exposure_pct", sa.Numeric(8, 4)),
        sa.Column("source", sa.String(20)),
        sa.Column("as_of_date", sa.Date()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # --- geopolitical_events ---
    op.create_table(
        "geopolitical_events",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("event_type", sa.String(30)),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("countries_involved", JSONB),
        sa.Column("severity", sa.String(10)),
        sa.Column("status", sa.String(20)),
        sa.Column("start_date", sa.Date()),
        sa.Column("commodity_impact", JSONB),
        sa.Column("sector_impact", JSONB),
        sa.Column("affected_entity_ids", JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("geopolitical_events")
    op.drop_table("company_country_exposures")
    op.drop_table("country_risk_scores")
    op.drop_table("country_profiles")
