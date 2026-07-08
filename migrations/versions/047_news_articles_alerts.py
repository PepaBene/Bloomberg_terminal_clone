"""Pillar 3 Phase 1: News articles, watchlists, and alert system.

Revision ID: 047
Revises: 046
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "047"
down_revision = "046"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- news_articles ---
    op.create_table(
        "news_articles",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("source_url", sa.String(1000), nullable=False, unique=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("summary", sa.Text()),
        sa.Column("body_text", sa.Text()),
        sa.Column("source_name", sa.String(100), nullable=False),
        sa.Column("publish_date", sa.Date(), nullable=False),
        sa.Column("ingest_date", sa.Date(), nullable=False),
        sa.Column("news_type", sa.String(30)),
        sa.Column("topics", JSONB),
        sa.Column("materiality", sa.String(10)),
        sa.Column("sentiment_score", sa.Numeric(4, 2)),
        sa.Column("sentiment_confidence", sa.Numeric(3, 2)),
        sa.Column("sentiment_label", sa.String(10)),
        sa.Column("content_hash", sa.String(64)),
        sa.Column("is_propagated", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("propagation_source", sa.String(30)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_news_source_url", "news_articles", ["source_url"])
    op.create_index("idx_news_publish_date", "news_articles", ["publish_date"])
    op.create_index("idx_news_ingest_date", "news_articles", ["ingest_date"])
    op.create_index("idx_news_type_date", "news_articles", ["news_type", "publish_date"])
    op.create_index("idx_news_materiality_date", "news_articles", ["materiality", "publish_date"])

    # --- article_entity_links ---
    op.create_table(
        "article_entity_links",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column(
            "article_id",
            sa.UUID(),
            sa.ForeignKey("news_articles.id"),
            nullable=False,
        ),
        sa.Column(
            "entity_id",
            sa.UUID(),
            sa.ForeignKey("entities.entity_id"),
            nullable=False,
        ),
        sa.Column("relevance_score", sa.Numeric(3, 2)),
        sa.Column("confidence", sa.Numeric(3, 2)),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("mention_text", sa.String(200)),
        sa.Column("mention_count", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index(
        "uq_article_entity",
        "article_entity_links",
        ["article_id", "entity_id"],
        unique=True,
    )
    op.create_index("idx_ael_article", "article_entity_links", ["article_id"])
    op.create_index("idx_ael_entity", "article_entity_links", ["entity_id"])

    # --- watchlists ---
    op.create_table(
        "watchlists",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("user_id", sa.String(100), nullable=False),
        sa.Column(
            "entity_id",
            sa.UUID(),
            sa.ForeignKey("entities.entity_id"),
            nullable=False,
        ),
        sa.Column("added_date", sa.Date(), nullable=False),
        sa.Column("notes", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index(
        "uq_watchlist_user_entity",
        "watchlists",
        ["user_id", "entity_id"],
        unique=True,
    )
    op.create_index("idx_watchlist_user", "watchlists", ["user_id"])

    # --- alert_rules ---
    op.create_table(
        "alert_rules",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("user_id", sa.String(100), nullable=False),
        sa.Column("alert_type", sa.String(50), nullable=False),
        sa.Column("entity_scope", JSONB),
        sa.Column("conditions", JSONB),
        sa.Column("priority_threshold", sa.String(10)),
        sa.Column("delivery_preference", sa.String(20), nullable=False, server_default=sa.text("'DAILY_DIGEST'")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("quiet_hours_start", sa.String(5)),
        sa.Column("quiet_hours_end", sa.String(5)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_alert_rule_user_type", "alert_rules", ["user_id", "alert_type"])

    # --- alert_events ---
    op.create_table(
        "alert_events",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column(
            "rule_id",
            sa.UUID(),
            sa.ForeignKey("alert_rules.id"),
            nullable=True,
        ),
        sa.Column("user_id", sa.String(100), nullable=False),
        sa.Column(
            "entity_id",
            sa.UUID(),
            sa.ForeignKey("entities.entity_id"),
            nullable=False,
        ),
        sa.Column("alert_type", sa.String(50), nullable=False),
        sa.Column("priority", sa.String(10), nullable=False, server_default=sa.text("'MEDIUM'")),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("detail", JSONB),
        sa.Column("is_acknowledged", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index(
        "idx_alert_user_ack",
        "alert_events",
        ["user_id", "is_acknowledged", "created_at"],
    )
    op.create_index(
        "idx_alert_entity_date",
        "alert_events",
        ["entity_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_table("alert_events")
    op.drop_table("alert_rules")
    op.drop_table("watchlists")
    op.drop_table("article_entity_links")
    op.drop_table("news_articles")
