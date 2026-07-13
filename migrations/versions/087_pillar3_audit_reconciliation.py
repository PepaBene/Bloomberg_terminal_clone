"""Pillar 3 audit reconciliation.

Revision ID: 087
Revises: 086
"""

from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "087"
down_revision: Union[str, None] = "086"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.alter_column("search_documents", "source_type", type_=sa.String(50), existing_nullable=False)
    op.alter_column("search_documents", "embedding_vector", type_=sa.Text(), postgresql_using="embedding_vector::text")
    op.execute("ALTER TABLE search_documents ALTER COLUMN embedding_vector TYPE vector(1536) USING embedding_vector::vector")
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_search_documents_embedding_hnsw "
        "ON search_documents USING hnsw (embedding_vector vector_cosine_ops)"
    )
    op.add_column("search_documents", sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()))
    op.create_index("idx_search_documents_source", "search_documents", ["source_type", "source_id"])
    op.add_column("search_queries", sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()))
    op.alter_column("search_queries", "user_id", nullable=True, existing_type=sa.String(100))

    op.alter_column("sentiment_scores", "source_type", type_=sa.String(50), existing_nullable=False)
    op.alter_column("filing_sections", "section_key", type_=sa.String(60), existing_nullable=False)
    op.alter_column("filing_diffs", "section_key", type_=sa.String(60), existing_nullable=False)
    op.alter_column("detected_anomalies", "anomaly_type", type_=sa.String(60), existing_nullable=False)
    op.create_index("idx_sentiment_aggregates_as_of_desc", "sentiment_aggregates", [sa.text("as_of_date DESC")])
    op.create_index("uq_sentiment_scores_source", "sentiment_scores", ["entity_id", "source_type", "source_reference"], unique=True)

    op.add_column("consolidated_alerts", sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()))
    op.create_index("uq_consolidated_alert_dedup", "consolidated_alerts", ["entity_id", "primary_type", "primary_headline"], unique=True)

    op.add_column("thesis_versions", sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()))
    op.drop_constraint("thesis_versions_thesis_id_fkey", "thesis_versions", type_="foreignkey")
    op.create_foreign_key("thesis_versions_thesis_id_fkey", "thesis_versions", "investment_theses", ["thesis_id"], ["id"], ondelete="CASCADE")
    op.create_foreign_key("investment_theses_analyst_id_fkey", "investment_theses", "users", ["analyst_id"], ["username"])
    op.create_foreign_key("morning_briefings_user_id_fkey", "morning_briefings", "users", ["user_id"], ["username"])
    op.create_foreign_key("briefing_preferences_user_id_fkey", "briefing_preferences", "users", ["user_id"], ["username"])
    op.execute("UPDATE search_queries SET user_id = NULL WHERE user_id NOT IN (SELECT username FROM users)")
    op.create_foreign_key("search_queries_user_id_fkey", "search_queries", "users", ["user_id"], ["username"])


    op.create_table(
        "commodity_supply_demand_balances",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("commodity_code", sa.String(20), nullable=False),
        sa.Column("as_of_date", sa.Date(), nullable=False),
        sa.Column("supply_value", sa.Numeric(20, 4)),
        sa.Column("demand_value", sa.Numeric(20, 4)),
        sa.Column("inventory_value", sa.Numeric(20, 4)),
        sa.Column("unit", sa.String(30)),
        sa.Column("source", sa.String(50)),
        sa.Column("balance_classification", sa.String(20)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_commodity_supply_demand_balances_commodity_code", "commodity_supply_demand_balances", ["commodity_code"])
    op.create_index("ix_commodity_supply_demand_balances_as_of_date", "commodity_supply_demand_balances", ["as_of_date"])
    op.create_index("idx_commodity_supply_demand_code_date", "commodity_supply_demand_balances", ["commodity_code", "as_of_date"])

    op.alter_column("news_articles", "summary", nullable=False, existing_type=sa.Text())
    op.alter_column("news_articles", "body_text", nullable=False, existing_type=sa.Text())

    for table in ("sentiment_scores", "sentiment_aggregates", "filing_sections", "filing_diffs", "article_entity_links"):
        constraint_name = f"{table}_entity_id_fkey"
        op.drop_constraint(constraint_name, table, type_="foreignkey")
        op.create_foreign_key(constraint_name, table, "entities", ["entity_id"], ["entity_id"], ondelete="CASCADE")


def downgrade() -> None:

    for table in ("article_entity_links", "filing_diffs", "filing_sections", "sentiment_aggregates", "sentiment_scores"):
        constraint_name = f"{table}_entity_id_fkey"
        op.drop_constraint(constraint_name, table, type_="foreignkey")
        op.create_foreign_key(constraint_name, table, "entities", ["entity_id"], ["entity_id"])

    op.alter_column("news_articles", "body_text", nullable=True, existing_type=sa.Text())
    op.alter_column("news_articles", "summary", nullable=True, existing_type=sa.Text())
    op.drop_constraint("search_queries_user_id_fkey", "search_queries", type_="foreignkey")
    op.drop_constraint("briefing_preferences_user_id_fkey", "briefing_preferences", type_="foreignkey")
    op.drop_constraint("morning_briefings_user_id_fkey", "morning_briefings", type_="foreignkey")
    op.drop_constraint("investment_theses_analyst_id_fkey", "investment_theses", type_="foreignkey")
    op.drop_constraint("thesis_versions_thesis_id_fkey", "thesis_versions", type_="foreignkey")
    op.create_foreign_key("thesis_versions_thesis_id_fkey", "thesis_versions", "investment_theses", ["thesis_id"], ["id"])
    op.drop_column("thesis_versions", "updated_at")
    op.drop_index("uq_consolidated_alert_dedup", table_name="consolidated_alerts")
    op.drop_column("consolidated_alerts", "updated_at")
    op.drop_index("uq_sentiment_scores_source", table_name="sentiment_scores")
    op.drop_index("idx_sentiment_aggregates_as_of_desc", table_name="sentiment_aggregates")
    op.drop_index("idx_commodity_supply_demand_code_date", table_name="commodity_supply_demand_balances")
    op.drop_index("ix_commodity_supply_demand_balances_as_of_date", table_name="commodity_supply_demand_balances")
    op.drop_index("ix_commodity_supply_demand_balances_commodity_code", table_name="commodity_supply_demand_balances")
    op.drop_table("commodity_supply_demand_balances")
    op.alter_column("detected_anomalies", "anomaly_type", type_=sa.String(30), existing_nullable=False)
    op.alter_column("filing_diffs", "section_key", type_=sa.String(20), existing_nullable=False)
    op.alter_column("filing_sections", "section_key", type_=sa.String(20), existing_nullable=False)
    op.alter_column("sentiment_scores", "source_type", type_=sa.String(20), existing_nullable=False)
    op.alter_column("search_queries", "user_id", nullable=False, existing_type=sa.String(100))
    op.drop_column("search_queries", "updated_at")
    op.drop_index("idx_search_documents_source", table_name="search_documents")
    op.drop_column("search_documents", "updated_at")
    op.execute("DROP INDEX IF EXISTS idx_search_documents_embedding_hnsw")
    op.alter_column("search_documents", "embedding_vector", type_=sa.JSON())
    op.alter_column("search_documents", "source_type", type_=sa.String(25), existing_nullable=False)
