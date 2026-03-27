"""Pillar 3 Phase 4C: Macro theme scores and scenario definitions.

Revision ID: 068
Revises: 067
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "068"
down_revision = "067"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "macro_theme_scores",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("entity_id", sa.UUID(), sa.ForeignKey("entities.entity_id"), nullable=False, index=True),
        sa.Column("theme", sa.String(25), nullable=False),
        sa.Column("exposure_score", sa.Numeric(5, 2)),
        sa.Column("sensitivity_direction", sa.String(10)),
        sa.Column("evidence", JSONB),
        sa.Column("quantified_exposure", sa.String(500)),
        sa.Column("as_of_date", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), onupdate=sa.func.now()),
        sa.UniqueConstraint("entity_id", "theme", "as_of_date", name="uq_macro_theme_entity_theme_date"),
    )

    op.create_table(
        "macro_scenarios",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("scenario_name", sa.String(50), nullable=False),
        sa.Column("scenario_type", sa.String(20)),
        sa.Column("description", sa.Text()),
        sa.Column("assumptions", JSONB),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("created_by", sa.String(100)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), onupdate=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("macro_scenarios")
    op.drop_table("macro_theme_scores")
