"""Technical studies, custom classifications, and ESG temperature scores.

Revision ID: 025
Revises: 024
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "025"
down_revision = "024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- technical_study_values ---
    op.create_table(
        "technical_study_values",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("security_id", UUID(as_uuid=True), sa.ForeignKey("securities.security_id"), nullable=False),
        sa.Column("study_date", sa.Date, nullable=False),
        sa.Column("indicator", sa.String(25), nullable=False),
        sa.Column("value", sa.Numeric(20, 6), nullable=False),
        sa.Column("category", sa.String(15)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "ix_tsv_security_date_indicator",
        "technical_study_values",
        ["security_id", "study_date", "indicator"],
        unique=True,
    )

    # --- custom_classifications ---
    op.create_table(
        "custom_classifications",
        sa.Column("classification_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.user_id"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("visibility", sa.String(10), server_default="PRIVATE"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_cc_user_id", "custom_classifications", ["user_id"])

    # --- classification_members ---
    op.create_table(
        "classification_members",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "classification_id",
            UUID(as_uuid=True),
            sa.ForeignKey("custom_classifications.classification_id"),
            nullable=False,
        ),
        sa.Column("entity_id", UUID(as_uuid=True), sa.ForeignKey("entities.entity_id"), nullable=False),
        sa.Column("added_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("tags", JSONB),
    )
    op.create_index(
        "ix_cm_classification_entity",
        "classification_members",
        ["classification_id", "entity_id"],
        unique=True,
    )

    # --- esg_temperature_scores ---
    op.create_table(
        "esg_temperature_scores",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("entity_id", UUID(as_uuid=True), sa.ForeignKey("entities.entity_id"), nullable=False),
        sa.Column("as_of_date", sa.Date, nullable=False),
        sa.Column("implied_temperature", sa.Numeric(4, 2), nullable=False),
        sa.Column("alignment", sa.String(25), nullable=False),
        sa.Column("scope1_emissions", sa.Numeric(20, 2)),
        sa.Column("scope2_emissions", sa.Numeric(20, 2)),
        sa.Column("scope3_emissions", sa.Numeric(20, 2)),
        sa.Column("emissions_trend_pct", sa.Numeric(8, 4)),
        sa.Column("data_quality_flag", sa.String(20), server_default="PARTIAL"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "ix_esg_temp_entity_date",
        "esg_temperature_scores",
        ["entity_id", "as_of_date"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_table("esg_temperature_scores")
    op.drop_table("classification_members")
    op.drop_table("custom_classifications")
    op.drop_table("technical_study_values")
