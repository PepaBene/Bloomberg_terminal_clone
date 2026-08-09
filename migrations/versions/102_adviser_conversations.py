"""Add conversations + conversation_messages tables (Layer 3 — Financial
Adviser chat, §5.3).

Revision ID: 102
Revises: 101
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "102"
down_revision = "101"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "conversations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", sa.String(100), nullable=False),
        sa.Column("portfolio_id", UUID(as_uuid=True), sa.ForeignKey("portfolios.id", ondelete="CASCADE")),
        sa.Column("title", sa.String(500)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        comment="Layer 3 adviser chat conversations (§5.3)",
    )
    op.create_index("idx_conversations_user_id", "conversations", ["user_id"])

    op.create_table(
        "conversation_messages",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("conversation_id", UUID(as_uuid=True), sa.ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),  # user|assistant
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("tool_calls", JSONB()),
        sa.Column("citations", JSONB()),
        sa.Column("tokens", sa.Integer()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_conversation_messages_conversation_id", "conversation_messages", ["conversation_id", "created_at"])


def downgrade() -> None:
    op.drop_index("idx_conversation_messages_conversation_id", table_name="conversation_messages")
    op.drop_table("conversation_messages")
    op.drop_index("idx_conversations_user_id", table_name="conversations")
    op.drop_table("conversations")
