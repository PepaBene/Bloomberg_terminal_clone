"""Custom data environment tables.

Revision ID: 031
Revises: 030
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "031"
down_revision = "030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "custom_field_definitions",
        sa.Column("field_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("expression", sa.Text, nullable=False),
        sa.Column("field_type", sa.String(20), nullable=False, server_default="NUMERIC"),
        sa.Column("scope", sa.String(20), nullable=False, server_default="PRIVATE"),
        sa.Column("created_by", sa.String(100)),
        sa.Column("depends_on", JSONB),
        sa.Column("is_valid", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("validation_error", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_cfd_name", "custom_field_definitions", ["name"])

    op.create_table(
        "custom_field_values",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("field_id", UUID(as_uuid=True), sa.ForeignKey("custom_field_definitions.field_id"), nullable=False),
        sa.Column("security_id", UUID(as_uuid=True), sa.ForeignKey("securities.security_id")),
        sa.Column("entity_id", UUID(as_uuid=True), sa.ForeignKey("entities.entity_id")),
        sa.Column("value_numeric", sa.Numeric(20, 6)),
        sa.Column("value_string", sa.String(500)),
        sa.Column("value_boolean", sa.Boolean),
        sa.Column("period", sa.String(20)),
        sa.Column("calculated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_cfv_field_id", "custom_field_values", ["field_id"])
    op.create_index("idx_cfv_security_id", "custom_field_values", ["security_id"])
    op.create_index("idx_cfv_entity_id", "custom_field_values", ["entity_id"])
    op.create_index("idx_cfv_field_security", "custom_field_values", ["field_id", "security_id"])
    op.create_index("idx_cfv_field_entity", "custom_field_values", ["field_id", "entity_id"])


def downgrade() -> None:
    op.drop_table("custom_field_values")
    op.drop_table("custom_field_definitions")
