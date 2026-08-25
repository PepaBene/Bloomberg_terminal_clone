"""094 - Add voting authority / investment discretion / put-call to institutional_holdings.

The 13F connector (src/ingestion/edgar_13f.py) parses these fields from the
infoTable XML but previously discarded them before persisting -- and the
voting-authority parse itself was reading the wrong XML depth (Sole/Shared/
None are nested under a <votingAuthority> parent, not direct children of
<infoTable>). Both are fixed in the same change as this migration.

Revision ID: 105
Revises: 104
"""

from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "105"
down_revision: Union[str, None] = "104"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.add_column("institutional_holdings", sa.Column("voting_sole", sa.Numeric(20, 2)))
    op.add_column("institutional_holdings", sa.Column("voting_shared", sa.Numeric(20, 2)))
    op.add_column("institutional_holdings", sa.Column("voting_none", sa.Numeric(20, 2)))
    op.add_column("institutional_holdings", sa.Column("investment_discretion", sa.String(10)))
    op.add_column("institutional_holdings", sa.Column("put_call", sa.String(10)))


def downgrade() -> None:
    op.drop_column("institutional_holdings", "put_call")
    op.drop_column("institutional_holdings", "investment_discretion")
    op.drop_column("institutional_holdings", "voting_none")
    op.drop_column("institutional_holdings", "voting_shared")
    op.drop_column("institutional_holdings", "voting_sole")
