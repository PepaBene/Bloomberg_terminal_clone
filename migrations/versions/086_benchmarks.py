"""Benchmarks table (Pillar 2 Frontend Bugs 93-95).

``GET/POST /v1/benchmarks`` had no backing table anywhere -- a permanent
404 for CustomIndexBuilder.tsx and the quant benchmark hooks. Adds a
minimal `benchmarks` table covering both standard ETF-proxy-tracked
indices (S&P 500 / NASDAQ 100 / Russell 1000 / Russell 2000 / Dow) and
user-created custom weighted indices.

Revision ID: 086
Revises: 085
"""

from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "086"
down_revision: Union[str, None] = "085"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.create_table(
        "benchmarks",
        sa.Column("benchmark_id", sa.UUID(), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("code", sa.String(60), nullable=False),
        sa.Column("ticker", sa.String(20)),
        sa.Column("benchmark_type", sa.String(20), nullable=False, server_default="INDEX"),
        sa.Column("created_by", sa.UUID(), sa.ForeignKey("users.user_id"), nullable=True),
        sa.Column("constituents", postgresql.JSONB()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("code", name="uq_benchmarks_code"),
        sa.CheckConstraint("benchmark_type IN ('INDEX', 'CUSTOM')", name="ck_benchmark_type"),
    )
    op.create_index("idx_benchmarks_type", "benchmarks", ["benchmark_type"])


def downgrade() -> None:
    op.drop_index("idx_benchmarks_type", table_name="benchmarks")
    op.drop_table("benchmarks")
