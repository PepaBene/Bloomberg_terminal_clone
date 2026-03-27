"""Pillar 3 Phase 4C: Consolidated alerts and earnings surprise intelligence.

Revision ID: 070
Revises: 069
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "070"
down_revision = "069"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "consolidated_alerts",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("entity_id", sa.UUID(), sa.ForeignKey("entities.entity_id"), nullable=False, index=True),
        sa.Column("alert_priority", sa.Integer()),
        sa.Column("alert_categories", JSONB),
        sa.Column("primary_headline", sa.String(500)),
        sa.Column("primary_type", sa.String(30)),
        sa.Column("source_alert_ids", JSONB),
        sa.Column("secondary_alerts", JSONB),
        sa.Column("ai_synthesis", sa.Text()),
        sa.Column("recommended_action", sa.String(20)),
        sa.Column("related_catalysts", JSONB),
        sa.Column("is_acknowledged", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("acknowledged_by", sa.String(100)),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "earnings_surprise_intelligence",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("entity_id", sa.UUID(), sa.ForeignKey("entities.entity_id"), nullable=False, index=True),
        sa.Column("report_date", sa.Date(), nullable=False),
        sa.Column("fiscal_period", sa.String(20)),
        sa.Column("eps_consensus", sa.Numeric(10, 4)),
        sa.Column("eps_actual", sa.Numeric(10, 4)),
        sa.Column("eps_surprise_pct", sa.Numeric(8, 4)),
        sa.Column("revenue_consensus", sa.Numeric(15, 2)),
        sa.Column("revenue_actual", sa.Numeric(15, 2)),
        sa.Column("revenue_surprise_pct", sa.Numeric(8, 4)),
        sa.Column("margin_analysis", JSONB),
        sa.Column("guidance_implications", JSONB),
        sa.Column("stock_reaction", JSONB),
        sa.Column("ai_narrative", sa.Text()),
        sa.Column("key_takeaways", JSONB),
        sa.Column("revision_implications", JSONB),
        sa.Column("recommendation", sa.String(30)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), onupdate=sa.func.now()),
        sa.UniqueConstraint("entity_id", "report_date", name="uq_earnings_surprise_entity_date"),
    )


def downgrade() -> None:
    op.drop_table("earnings_surprise_intelligence")
    op.drop_table("consolidated_alerts")
