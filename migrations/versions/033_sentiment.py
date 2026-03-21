"""Sentiment analysis tables.

Revision ID: 033
Revises: 032
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "033"
down_revision = "032"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sentiment_scores",
        sa.Column("score_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("entity_id", UUID(as_uuid=True), sa.ForeignKey("entities.entity_id"), nullable=False),
        sa.Column("source_type", sa.String(20), nullable=False),
        sa.Column("source_reference", sa.String(500)),
        sa.Column("source_date", sa.DateTime(timezone=True)),
        sa.Column("sentiment", sa.String(10), nullable=False),
        sa.Column("sentiment_score", sa.Numeric(5, 4), nullable=False),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=False, server_default=sa.text("0.5")),
        sa.Column("relevance", sa.Numeric(5, 4)),
        sa.Column("topics", JSONB),
        sa.Column("ai_enabled", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_sentiment_scores_entity_id", "sentiment_scores", ["entity_id"])
    op.create_index("idx_sentiment_entity_date", "sentiment_scores", ["entity_id", "source_date"])

    op.create_table(
        "sentiment_aggregates",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("entity_id", UUID(as_uuid=True), sa.ForeignKey("entities.entity_id"), nullable=False),
        sa.Column("as_of_date", sa.Date, nullable=False),
        sa.Column("timeframe", sa.String(15), nullable=False),
        sa.Column("avg_sentiment", sa.Numeric(5, 4), nullable=False),
        sa.Column("sentiment_momentum", sa.Numeric(5, 4)),
        sa.Column("article_count", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("positive_pct", sa.Numeric(5, 4)),
        sa.Column("negative_pct", sa.Numeric(5, 4)),
        sa.Column("anomaly_flag", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("peer_rank_pct", sa.Numeric(5, 4)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_sentiment_aggregates_entity_id", "sentiment_aggregates", ["entity_id"])
    op.create_index(
        "idx_sent_agg_entity_date_tf",
        "sentiment_aggregates",
        ["entity_id", "as_of_date", "timeframe"],
        unique=True,
    )

    op.create_table(
        "earnings_call_sentiment",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("entity_id", UUID(as_uuid=True), sa.ForeignKey("entities.entity_id"), nullable=False),
        sa.Column("call_date", sa.Date, nullable=False),
        sa.Column("fiscal_year", sa.Integer, nullable=False),
        sa.Column("fiscal_quarter", sa.Integer, nullable=False),
        sa.Column("overall_tone", sa.Numeric(5, 4), nullable=False),
        sa.Column("management_tone", sa.Numeric(5, 4)),
        sa.Column("qa_tone", sa.Numeric(5, 4)),
        sa.Column("tone_vs_prior", sa.Numeric(5, 4)),
        sa.Column("hedging_count", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("confidence_count", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("topic_sentiments", JSONB),
        sa.Column("ai_enabled", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_earnings_call_sentiment_entity_id", "earnings_call_sentiment", ["entity_id"])
    op.create_index(
        "idx_ecall_entity_fy_fq",
        "earnings_call_sentiment",
        ["entity_id", "fiscal_year", "fiscal_quarter"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_table("earnings_call_sentiment")
    op.drop_table("sentiment_aggregates")
    op.drop_table("sentiment_scores")
