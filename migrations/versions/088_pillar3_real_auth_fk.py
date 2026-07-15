"""M-004/M-005: real auth wiring for morning_briefings/briefing_preferences/
investment_theses -- user_id/analyst_id become real UUID FKs to users.user_id.

`research_briefings.py` and `research_thesis.py` previously accepted
`user_id`/`analyst_id` as caller-supplied free text (`Query(default=
"default_user")`, a POST-body field) with no relationship to the `users`
login table at all -- callers could tag content under any string. Both
routers now require a real Bearer token (`Depends(get_current_active_user)`)
and derive `user_id`/`analyst_id` from the resolved `User.user_id`.

These 3 columns are converted from `String(100)` to a real `UUID` FK. There
is no way to preserve old arbitrary-string values as real user references
(they were never tied to a real account), so this drops and recreates the
columns rather than casting -- acceptable only because this is a pre-launch
schema with no real deployed data (same reasoning as migration 087).

Dropping each column also drops constraints that reference it (Postgres
cascades column-dependent constraints/indexes), so this migration explicitly
recreates: `uq_briefing_user_date` (morning_briefings), the unique
`briefing_preferences.user_id`, and `uq_thesis_entity_analyst_version`
(investment_theses) -- the last one previously had no explicit name
(migration 066's bare `sa.UniqueConstraint(...)`); it gets one here.

Revision ID: 088
Revises: 087
"""

import sqlalchemy as sa
from alembic import op

revision = "088"
down_revision = "087"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── morning_briefings.user_id ───────────────────────────────────
    op.drop_column("morning_briefings", "user_id")
    op.add_column("morning_briefings", sa.Column("user_id", sa.UUID(), nullable=False))
    op.create_foreign_key(
        "morning_briefings_user_id_fkey", "morning_briefings", "users", ["user_id"], ["user_id"],
    )
    op.create_index("ix_morning_briefings_user_id", "morning_briefings", ["user_id"])
    op.create_unique_constraint(
        "uq_briefing_user_date", "morning_briefings", ["user_id", "briefing_date"],
    )

    # ── briefing_preferences.user_id ────────────────────────────────
    op.drop_column("briefing_preferences", "user_id")
    op.add_column("briefing_preferences", sa.Column("user_id", sa.UUID(), nullable=False))
    op.create_foreign_key(
        "briefing_preferences_user_id_fkey", "briefing_preferences", "users", ["user_id"], ["user_id"],
    )
    op.create_unique_constraint("uq_briefing_preferences_user_id", "briefing_preferences", ["user_id"])

    # ── investment_theses.analyst_id ────────────────────────────────
    op.drop_column("investment_theses", "analyst_id")
    op.add_column("investment_theses", sa.Column("analyst_id", sa.UUID(), nullable=False))
    op.create_foreign_key(
        "investment_theses_analyst_id_fkey", "investment_theses", "users", ["analyst_id"], ["user_id"],
    )
    op.create_index("ix_investment_theses_analyst_id", "investment_theses", ["analyst_id"])
    op.create_unique_constraint(
        "uq_thesis_entity_analyst_version", "investment_theses", ["entity_id", "analyst_id", "version"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_thesis_entity_analyst_version", "investment_theses", type_="unique")
    op.drop_index("ix_investment_theses_analyst_id", table_name="investment_theses")
    op.drop_column("investment_theses", "analyst_id")
    op.add_column("investment_theses", sa.Column("analyst_id", sa.String(100), nullable=False))
    op.create_unique_constraint(
        "uq_thesis_entity_analyst_version_str", "investment_theses", ["entity_id", "analyst_id", "version"],
    )

    op.drop_constraint("uq_briefing_preferences_user_id", "briefing_preferences", type_="unique")
    op.drop_column("briefing_preferences", "user_id")
    op.add_column("briefing_preferences", sa.Column("user_id", sa.String(100), nullable=False, unique=True))

    op.drop_constraint("uq_briefing_user_date", "morning_briefings", type_="unique")
    op.drop_index("ix_morning_briefings_user_id", table_name="morning_briefings")
    op.drop_column("morning_briefings", "user_id")
    op.add_column("morning_briefings", sa.Column("user_id", sa.String(100), nullable=False))
    op.create_index("ix_morning_briefings_user_id", "morning_briefings", ["user_id"])
    op.create_unique_constraint(
        "uq_briefing_user_date_str", "morning_briefings", ["user_id", "briefing_date"],
    )
