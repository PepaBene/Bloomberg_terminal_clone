"""Create business relationships tables.

Revision ID: 012
Revises: 011
Create Date: 2026-03-17
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "012"
down_revision: Union[str, None] = "011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- business_relationships ---
    op.create_table(
        "business_relationships",
        sa.Column("relationship_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("source_entity_id", UUID(as_uuid=True), sa.ForeignKey("entities.entity_id"), nullable=False),
        sa.Column("target_entity_id", UUID(as_uuid=True), sa.ForeignKey("entities.entity_id"), nullable=False),
        sa.Column("relationship_type", sa.String(30), nullable=False),
        sa.Column("direction", sa.String(20)),
        sa.Column("revenue_percentage", sa.Numeric(6, 4)),
        sa.Column("cost_percentage", sa.Numeric(6, 4)),
        sa.Column("contract_value", sa.Numeric(20, 2)),
        sa.Column("contract_currency", sa.String(3), sa.ForeignKey("currencies.currency_code")),
        sa.Column("contract_start_date", sa.Date()),
        sa.Column("contract_end_date", sa.Date()),
        sa.Column("is_single_source", sa.Boolean()),
        sa.Column("materiality_score", sa.Numeric(5, 2)),
        sa.Column("confidence_score", sa.Numeric(3, 2)),
        sa.Column("extraction_method", sa.String(30)),
        sa.Column("source_document", sa.String(500)),
        sa.Column("source_text", sa.Text()),
        sa.Column("effective_date", sa.Date()),
        sa.Column("termination_date", sa.Date()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("metadata_json", JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_brel_source", "business_relationships", ["source_entity_id"])
    op.create_index("idx_brel_target", "business_relationships", ["target_entity_id"])
    op.create_index("idx_brel_type", "business_relationships", ["relationship_type"])
    op.create_index("idx_brel_source_type", "business_relationships", ["source_entity_id", "relationship_type"])
    op.create_index("idx_brel_target_type", "business_relationships", ["target_entity_id", "relationship_type"])

    # --- relationship_history ---
    op.create_table(
        "relationship_history",
        sa.Column("history_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("relationship_id", UUID(as_uuid=True), sa.ForeignKey("business_relationships.relationship_id"), nullable=False),
        sa.Column("change_type", sa.String(20), nullable=False),
        sa.Column("change_date", sa.Date()),
        sa.Column("previous_revenue_percentage", sa.Numeric(6, 4)),
        sa.Column("new_revenue_percentage", sa.Numeric(6, 4)),
        sa.Column("previous_materiality_score", sa.Numeric(5, 2)),
        sa.Column("new_materiality_score", sa.Numeric(5, 2)),
        sa.Column("change_details", JSONB),
        sa.Column("source", sa.String(50)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_relhist_relationship", "relationship_history", ["relationship_id"])


def downgrade() -> None:
    op.drop_table("relationship_history")
    op.drop_table("business_relationships")
