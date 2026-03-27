"""Pillar 3 Phase 4C: Scenario company impact analysis.

Revision ID: 069
Revises: 068
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "069"
down_revision = "068"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "scenario_company_impacts",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("scenario_id", sa.UUID(), sa.ForeignKey("macro_scenarios.id"), nullable=False),
        sa.Column("entity_id", sa.UUID(), sa.ForeignKey("entities.entity_id"), nullable=False),
        sa.Column("base_eps", sa.Numeric(10, 2)),
        sa.Column("scenario_eps", sa.Numeric(10, 2)),
        sa.Column("eps_change_pct", sa.Numeric(8, 2)),
        sa.Column("margin_impact_bps", sa.Numeric(8, 2)),
        sa.Column("rating_implication", sa.String(15)),
        sa.Column("price_target_scenario", sa.Numeric(10, 2)),
        sa.Column("narrative", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("scenario_id", "entity_id", name="uq_scenario_impact_scenario_entity"),
    )


def downgrade() -> None:
    op.drop_table("scenario_company_impacts")
