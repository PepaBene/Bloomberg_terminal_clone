"""Pillar 3 Phase 2: News propagation rules, events, and preferences.

Revision ID: 051
Revises: 050
"""

import sqlalchemy as sa
from alembic import op

revision = "051"
down_revision = "050"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- propagation_rules ---
    op.create_table(
        "propagation_rules",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("rule_type", sa.String(30), nullable=False),
        sa.Column("event_category", sa.String(30)),
        sa.Column("severity", sa.String(10)),
        sa.Column("relevance_decay_hop1", sa.Numeric(4, 3), server_default=sa.text("0.3")),
        sa.Column("relevance_decay_hop2", sa.Numeric(4, 3), server_default=sa.text("0.1")),
        sa.Column("max_hops", sa.Integer(), server_default=sa.text("2")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # --- propagation_events ---
    op.create_table(
        "propagation_events",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column(
            "source_article_id",
            sa.UUID(),
            sa.ForeignKey("news_articles.id"),
            nullable=True,
        ),
        sa.Column(
            "source_entity_id",
            sa.UUID(),
            sa.ForeignKey("entities.entity_id"),
            nullable=False,
        ),
        sa.Column(
            "target_entity_id",
            sa.UUID(),
            sa.ForeignKey("entities.entity_id"),
            nullable=False,
        ),
        sa.Column(
            "rule_id",
            sa.UUID(),
            sa.ForeignKey("propagation_rules.id"),
            nullable=True,
        ),
        sa.Column("propagation_type", sa.String(30), nullable=False),
        sa.Column("hop_number", sa.Integer(), nullable=False),
        sa.Column("relevance_score", sa.Numeric(4, 3)),
        sa.Column("event_summary", sa.String(500)),
        sa.Column("severity", sa.String(10)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_prop_event_target", "propagation_events", ["target_entity_id"])
    op.create_index(
        "idx_prop_event_target_created",
        "propagation_events",
        ["target_entity_id", "created_at"],
    )
    op.create_index(
        "idx_prop_event_source_created",
        "propagation_events",
        ["source_entity_id", "created_at"],
    )

    # --- propagation_preferences ---
    op.create_table(
        "propagation_preferences",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("user_id", sa.String(100), nullable=False),
        sa.Column("propagation_type", sa.String(30), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index(
        "uq_prop_pref_user_type",
        "propagation_preferences",
        ["user_id", "propagation_type"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_table("propagation_preferences")
    op.drop_table("propagation_events")
    op.drop_table("propagation_rules")
