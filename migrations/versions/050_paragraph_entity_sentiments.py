"""Pillar 3 Phase 2: Paragraph & entity sentiments + sentiment aggregate extensions.

Revision ID: 050
Revises: 049
"""

import sqlalchemy as sa
from alembic import op

revision = "050"
down_revision = "049"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- paragraph_sentiments ---
    op.create_table(
        "paragraph_sentiments",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column(
            "article_id",
            sa.UUID(),
            sa.ForeignKey("news_articles.id"),
            nullable=False,
        ),
        sa.Column("paragraph_index", sa.Integer(), nullable=False),
        sa.Column("text_snippet", sa.String(500)),
        sa.Column("sentiment", sa.String(10)),
        sa.Column("positive_prob", sa.Numeric(5, 4)),
        sa.Column("negative_prob", sa.Numeric(5, 4)),
        sa.Column("neutral_prob", sa.Numeric(5, 4)),
        sa.Column("composite_score", sa.Numeric(5, 4)),
        sa.Column("confidence", sa.Numeric(5, 4)),
        sa.Column("method", sa.String(15)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_para_sent_article", "paragraph_sentiments", ["article_id"])
    op.create_index(
        "uq_paragraph_article_idx",
        "paragraph_sentiments",
        ["article_id", "paragraph_index"],
        unique=True,
    )

    # --- entity_sentiments ---
    op.create_table(
        "entity_sentiments",
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
        sa.Column("sentence_count", sa.Integer()),
        sa.Column("avg_sentiment", sa.Numeric(5, 4)),
        sa.Column("confidence", sa.Numeric(5, 4)),
        sa.Column("method", sa.String(15)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index(
        "uq_entity_sent_article_entity",
        "entity_sentiments",
        ["article_id", "entity_id"],
        unique=True,
    )

    # --- ALTER sentiment_aggregates: add Phase 2 columns ---
    op.add_column(
        "sentiment_aggregates",
        sa.Column("sentiment_momentum_class", sa.String(25), nullable=True),
    )
    op.add_column(
        "sentiment_aggregates",
        sa.Column("peer_z_score", sa.Numeric(6, 3), nullable=True),
    )
    op.add_column(
        "sentiment_aggregates",
        sa.Column("volume_anomaly", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "sentiment_aggregates",
        sa.Column("sentiment_shift_anomaly", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "sentiment_aggregates",
        sa.Column("price_divergence_anomaly", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "sentiment_aggregates",
        sa.Column("combined_anomaly_score", sa.Numeric(5, 2), nullable=True),
    )


def downgrade() -> None:
    # --- Revert sentiment_aggregates columns ---
    op.drop_column("sentiment_aggregates", "combined_anomaly_score")
    op.drop_column("sentiment_aggregates", "price_divergence_anomaly")
    op.drop_column("sentiment_aggregates", "sentiment_shift_anomaly")
    op.drop_column("sentiment_aggregates", "volume_anomaly")
    op.drop_column("sentiment_aggregates", "peer_z_score")
    op.drop_column("sentiment_aggregates", "sentiment_momentum_class")

    # --- Drop tables ---
    op.drop_table("entity_sentiments")
    op.drop_table("paragraph_sentiments")
