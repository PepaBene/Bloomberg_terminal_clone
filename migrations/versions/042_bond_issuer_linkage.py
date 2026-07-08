"""D11 FI Supplement P9: Bond issuer linkage.

Revision ID: 042
Revises: 041
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "042"
down_revision = "041"


def upgrade() -> None:
    op.add_column("entities", sa.Column("is_financing_subsidiary", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.add_column("entities", sa.Column("financing_parent_id", UUID(as_uuid=True), nullable=True))


def downgrade() -> None:
    op.drop_column("entities", "financing_parent_id")
    op.drop_column("entities", "is_financing_subsidiary")
