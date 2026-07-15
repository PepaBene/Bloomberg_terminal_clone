"""Add subsidiaries table (EX-21 org-tree data for complex_structure engine).

Revision ID: 089
Revises: 088
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "089"
down_revision = "088"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "subsidiaries",
        sa.Column("subsidiary_id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "parent_entity_id", UUID(as_uuid=True),
            sa.ForeignKey("entities.entity_id", ondelete="CASCADE"),
            nullable=False, index=True,
        ),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("jurisdiction", sa.String(100)),
        sa.Column("parent_subsidiary_name", sa.String(300)),
        sa.Column("ownership_pct", sa.Numeric(5, 2)),
        sa.Column("is_vie", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("source_filing_accession", sa.String(25)),
        sa.Column("as_of_date", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index(
        "uq_subsidiary_parent_name_asof", "subsidiaries",
        ["parent_entity_id", "name", "as_of_date"], unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_subsidiary_parent_name_asof", table_name="subsidiaries")
    op.drop_table("subsidiaries")
