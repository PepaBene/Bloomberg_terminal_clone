"""Benchmarks table (Pillar 2 Frontend Bugs 93-95).

``GET/POST /v1/benchmarks`` had no backing table anywhere -- a permanent
404 for CustomIndexBuilder.tsx and the quant benchmark hooks. Adds a
minimal `benchmarks` table covering standard ETF-proxy-tracked indices
(S&P 500 / NASDAQ 100 / Russell 1000 / Russell 2000 / Dow).

User-created custom indices are handled by the pre-existing
`custom_indices`/`index_constituents` tables (migration 029 --
see `src/models/custom_index.py`) instead of a second row-type here; see
`src/api/routers/benchmarks.py` for how the two are unified behind one
`/v1/benchmarks` API.

Revision ID: 086
Revises: 085
"""

from typing import Union

import sqlalchemy as sa
from alembic import op

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
        sa.Column("ticker", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("code", name="uq_benchmarks_code"),
    )


def downgrade() -> None:
    op.drop_table("benchmarks")
