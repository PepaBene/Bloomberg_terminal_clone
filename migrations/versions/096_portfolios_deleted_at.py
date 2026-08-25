"""096 - Add portfolios.deleted_at (soft-delete column present on the model
but never created by migration 071).

The Portfolio model (src/models/portfolio.py) declares `deleted_at` for
soft-deletes, but 071_portfolios.py's create_table never included it --
every query that selects the full ORM row (e.g. GET /v4/portfolios)
500s with `UndefinedColumnError: column portfolios.deleted_at does not
exist`.

Revision ID: 096
Revises: 095
"""

from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "096"
down_revision: Union[str, None] = "095"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.add_column("portfolios", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("portfolios", "deleted_at")
