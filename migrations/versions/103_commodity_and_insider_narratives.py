"""Add commodity_narratives and insider_narratives tables (Layer 2 §4.7
Pillar-3 follow-through: commodity news/supply-demand narrative to
complement FRED prices, and narrative around Form 4 / congressional
disclosures).

Revision ID: 103
Revises: 102
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "103"
down_revision = "102"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "commodity_narratives",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        # Not a FK to commodity_profiles.commodity_code -- CommodityPrice/
        # CommodityInventory already reference commodity_code by plain
        # string convention, not a constrained FK; matches that.
        sa.Column("commodity_code", sa.String(20), nullable=False),
        sa.Column("as_of_date", sa.Date(), nullable=False),
        sa.Column("narrative", sa.Text(), nullable=False),
        sa.Column("price_summary", JSONB()),
        sa.Column("news_article_ids", JSONB()),
        sa.Column("model", sa.String(64)),
        sa.Column("prompt_id", sa.String(64)),
        sa.Column("prompt_version", sa.Integer()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        comment="AI narrative over commodity price/inventory data + related news (§4.7)",
    )
    op.create_index(
        "uq_commodity_narrative_code_date", "commodity_narratives",
        ["commodity_code", "as_of_date"], unique=True,
    )

    op.create_table(
        "insider_narratives",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("entity_id", UUID(as_uuid=True), sa.ForeignKey("entities.entity_id"), nullable=False),
        sa.Column("as_of_date", sa.Date(), nullable=False),
        sa.Column("narrative", sa.Text(), nullable=False),
        sa.Column("signal_summary", JSONB()),
        sa.Column("congressional_summary", JSONB()),
        sa.Column("model", sa.String(64)),
        sa.Column("prompt_id", sa.String(64)),
        sa.Column("prompt_version", sa.Integer()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        comment="AI narrative over Form 4 insider signals + congressional PTR disclosures (§4.7)",
    )
    op.create_index(
        "uq_insider_narrative_entity_date", "insider_narratives",
        ["entity_id", "as_of_date"], unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_insider_narrative_entity_date", table_name="insider_narratives")
    op.drop_table("insider_narratives")
    op.drop_index("uq_commodity_narrative_code_date", table_name="commodity_narratives")
    op.drop_table("commodity_narratives")
