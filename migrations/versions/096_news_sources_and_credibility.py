"""Add news_sources table + trust/credibility columns on news_articles.

AI_THREE_LAYER_REBUILD_PLAN.md §4.2 (Layer 2 — News/Information).

Revision ID: 096
Revises: 095
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "096"
down_revision = "095"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "news_sources",
        sa.Column("source_name", sa.String(100), primary_key=True),
        sa.Column("domain", sa.String(255), unique=True),
        sa.Column("tier", sa.String(10), nullable=False),
        sa.Column("reliability_weight", sa.Numeric(3, 2), nullable=False),
        sa.Column("region", sa.String(50)),
        sa.Column("is_paywalled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("notes", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        comment="Trust/credibility registry for news sources (Layer 2 §4.2)",
    )
    op.create_index("idx_news_sources_domain", "news_sources", ["domain"])

    op.add_column("news_articles", sa.Column("source_trust", sa.Numeric(3, 2)))
    op.add_column("news_articles", sa.Column("credibility_score", sa.Numeric(4, 3)))
    op.add_column(
        "news_articles",
        sa.Column("cluster_id", UUID(as_uuid=True), sa.ForeignKey("news_articles.id")),
    )
    op.add_column(
        "news_articles",
        sa.Column("is_non_consensus", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "news_articles",
        sa.Column("corroboration_count", sa.Integer(), nullable=False, server_default="1"),
    )
    op.create_index("idx_news_articles_cluster_id", "news_articles", ["cluster_id"])


def downgrade() -> None:
    op.drop_index("idx_news_articles_cluster_id", table_name="news_articles")
    op.drop_column("news_articles", "corroboration_count")
    op.drop_column("news_articles", "is_non_consensus")
    op.drop_column("news_articles", "cluster_id")
    op.drop_column("news_articles", "credibility_score")
    op.drop_column("news_articles", "source_trust")

    op.drop_index("idx_news_sources_domain", table_name="news_sources")
    op.drop_table("news_sources")
