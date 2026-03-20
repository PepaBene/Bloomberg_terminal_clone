"""Create authentication and authorization tables.

Revision ID: 013
Revises: 012
Create Date: 2026-03-17
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers
revision: str = "013"
down_revision: Union[str, None] = "012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Users ──────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("user_id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("username", sa.String(100), nullable=False, unique=True),
        sa.Column("email", sa.String(200), nullable=False, unique=True),
        sa.Column("hashed_password", sa.String(200), nullable=False),
        sa.Column("full_name", sa.String(200)),
        sa.Column("role", sa.String(20), nullable=False, server_default="VIEWER"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("is_service_account", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("api_key", sa.String(64), unique=True),
        sa.Column("rate_limit_override", sa.Integer()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True)),
    )

    # ── API Audit Log ──────────────────────────────────────────────────
    op.create_table(
        "api_audit_log",
        sa.Column("log_id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("users.user_id")),
        sa.Column("endpoint", sa.String(500), nullable=False),
        sa.Column("method", sa.String(10), nullable=False),
        sa.Column("request_params", sa.dialects.postgresql.JSONB()),
        sa.Column("response_status", sa.Integer()),
        sa.Column("response_time_ms", sa.Integer()),
        sa.Column("ip_address", sa.String(45)),
        sa.Column("user_agent", sa.String(500)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_audit_user_id", "api_audit_log", ["user_id"])
    op.create_index("idx_audit_created_at", "api_audit_log", ["created_at"])
    op.create_index("idx_audit_endpoint", "api_audit_log", ["endpoint"])


def downgrade() -> None:
    op.drop_table("api_audit_log")
    op.drop_table("users")
