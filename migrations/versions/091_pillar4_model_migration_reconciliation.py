"""Pillar 4 models/schemas reconciliation (P4-M-009, P4-M-013, P4-M-015,
P4-M-019, P4-M-020, P4-M-021-024, P4-M-025, P4-M-026, P4-M-027, P4-M-028).

`src/models/*.py` had been edited to address most of the Pillar-4 "Models &
schemas" audit section, but (per the audit's own "Cross-cutting themes"
note #1) none of those edits were ever backed by a migration -- migrations
071-090 still create the original, narrower/uncascaded/unconstrained
schema. This migration reconciles the two.

While reconciling, two additional pre-existing gaps were found and fixed
here too (same failure class, just not individually itemized in the audit):

- `portfolio_watchlists` / `portfolio_watchlist_entries` (src/models/
  portfolio_watchlist.py) have **no migration at all** anywhere in
  migrations/versions/ -- a database built from `alembic upgrade head`
  never had these tables to begin with. They're created here from
  scratch (with P4-M-020's unique constraint and P4-M-027's created_by
  column already applied, since there's no prior version to alter).
- `positions.portfolio_id` / `transactions.portfolio_id` already declare
  `ondelete="CASCADE"` in the model (the audit's "partially fixed" P4-M-009
  note treats these as done), but migrations 072/073 never got the
  matching `ON DELETE CASCADE` -- so even the "already fixed" half of
  P4-M-009 was migration-dead until now. Included below for a complete fix.

Item-by-item:

- P4-M-009: `ON DELETE CASCADE` on every portfolio_id FK to `portfolios.id`
  (nav_snapshots, corporate_action_queue, performance_snapshots,
  attribution_results, report_requests, portfolio_var_snapshots,
  concentration_analyses, factor_exposure_snapshots,
  portfolio_stress_test_results -- plus positions/transactions, see above).
  BacktestRun/BacktestResult have no portfolio_id FK at all, so nothing to
  do there (per the audit's own correction).
- P4-M-013: `corporate_action_queue.position_id` gets a real FK to
  `positions.id` (ON DELETE SET NULL) so the new `Position.corporate_
  actions` / `CorporateActionQueue.position` relationship() has something
  to join on. It previously had no FK constraint at all.
- P4-M-015: `attribution_results`'s unique constraint moves from
  (portfolio_id, attribution_type, period_end) to (portfolio_id,
  period_start, period_end) -- the period is the natural key, not the
  attribution method used to compute it.
- P4-M-019: `portfolio_uploads.user_id` column added.
- P4-M-020: `portfolio_watchlists` unique (user_id, name) -- applied at
  CREATE TABLE time, see above.
- P4-M-021/022/023/024: date-order CHECK constraints -- corporate_action_
  queue (ex_date <= payment_date, the meaningful date pair in that module
  since NAVSnapshot itself only has one date column), performance_
  snapshots / attribution_results (period_start <= period_end),
  report_requests (period_start <= period_end, nullable-guarded),
  backtest_runs (start_date <= end_date).
- P4-M-025: `regression_results.r_squared` CHECK [0, 1]; `adj_r_squared`
  CHECK [-1, 1] (adjusted R² can go slightly negative for a poor fit with
  few observations relative to predictors; plain R² cannot).
- P4-M-026: CHECK constraints on the clearest fixed-domain status/type
  columns -- `positions.status`, `corporate_action_queue.status`,
  `backtest_runs.status`, `transactions.transaction_type`.
  `portfolios.status` / `portfolio_type` are deliberately NOT constrained:
  both are exercised with values outside any 2-3-value guess in real
  code paths (`PUT /portfolios/{id}` accepts arbitrary status strings,
  e.g. "PAUSED"; the CSV-upload commit path sets portfolio_type="EQUITY"
  alongside REAL/PAPER) -- locking either down would break real behavior.
  `corporate_action_queue.action_type` is left unconstrained too: the
  table has no production writer yet, so the real universe of action
  types isn't established.
- P4-M-027: `created_by` added to `positions`, `portfolio_watchlist_
  entries` (at CREATE TABLE time), and `backtest_runs`, matching
  `transactions.created_by`'s existing free-form (no FK) pattern.
- P4-M-028: `backtest_runs.user_id` added (free-form identity string,
  same non-FK pattern as `portfolios.user_id` -- see that model for why
  a hard FK to `users` isn't used here) so backtest reads-by-ID can be
  authorized against an owner.

Revision ID: 091
Revises: 090
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "091"
down_revision = "090"
branch_labels = None
depends_on = None


# Tables whose portfolio_id -> portfolios.id FK needs ON DELETE CASCADE.
# (table_name, existing_fk_constraint_name)
_PORTFOLIO_CASCADE_TARGETS = [
    ("positions", "positions_portfolio_id_fkey"),
    ("transactions", "transactions_portfolio_id_fkey"),
    ("nav_snapshots", "nav_snapshots_portfolio_id_fkey"),
    ("corporate_action_queue", "corporate_action_queue_portfolio_id_fkey"),
    ("performance_snapshots", "performance_snapshots_portfolio_id_fkey"),
    ("attribution_results", "attribution_results_portfolio_id_fkey"),
    ("report_requests", "report_requests_portfolio_id_fkey"),
    ("portfolio_var_snapshots", "portfolio_var_snapshots_portfolio_id_fkey"),
    ("concentration_analyses", "concentration_analyses_portfolio_id_fkey"),
    ("factor_exposure_snapshots", "factor_exposure_snapshots_portfolio_id_fkey"),
    ("portfolio_stress_test_results", "portfolio_stress_test_results_portfolio_id_fkey"),
]


def upgrade() -> None:
    # ── P4-M-009: ON DELETE CASCADE on every portfolio_id FK ────────────
    for table_name, fk_name in _PORTFOLIO_CASCADE_TARGETS:
        op.drop_constraint(fk_name, table_name, type_="foreignkey")
        op.create_foreign_key(
            fk_name, table_name, "portfolios", ["portfolio_id"], ["id"],
            ondelete="CASCADE",
        )

    # ── P4-M-013: real FK for corporate_action_queue.position_id ────────
    op.create_foreign_key(
        "corporate_action_queue_position_id_fkey",
        "corporate_action_queue", "positions",
        ["position_id"], ["id"],
        ondelete="SET NULL",
    )

    # ── P4-M-015: fix attribution_results unique constraint ─────────────
    op.drop_constraint("uq_attr_portfolio_type_end", "attribution_results", type_="unique")
    op.create_unique_constraint(
        "uq_attr_portfolio_period", "attribution_results",
        ["portfolio_id", "period_start", "period_end"],
    )

    # ── P4-M-019: portfolio_uploads.user_id ──────────────────────────────
    op.add_column("portfolio_uploads", sa.Column("user_id", sa.String(100), nullable=True))
    op.create_index("ix_portfolio_uploads_user_id", "portfolio_uploads", ["user_id"])

    # ── P4-M-021/022/023/024: date-order CHECK constraints ───────────────
    op.create_check_constraint(
        "ck_corp_action_ex_before_payment", "corporate_action_queue",
        "ex_date IS NULL OR payment_date IS NULL OR ex_date <= payment_date",
    )
    op.create_check_constraint(
        "ck_perf_period_order", "performance_snapshots",
        "period_start <= period_end",
    )
    op.create_check_constraint(
        "ck_attr_period_order", "attribution_results",
        "period_start <= period_end",
    )
    op.create_check_constraint(
        "ck_report_period_order", "report_requests",
        "period_start IS NULL OR period_end IS NULL OR period_start <= period_end",
    )
    op.create_check_constraint(
        "ck_backtest_date_order", "backtest_runs",
        "start_date <= end_date",
    )

    # ── P4-M-025: regression_results r_squared / adj_r_squared range ─────
    op.create_check_constraint(
        "ck_regression_r_squared_range", "regression_results",
        "r_squared IS NULL OR (r_squared >= 0 AND r_squared <= 1)",
    )
    op.create_check_constraint(
        "ck_regression_adj_r_squared_range", "regression_results",
        "adj_r_squared IS NULL OR (adj_r_squared >= -1 AND adj_r_squared <= 1)",
    )

    # ── P4-M-026: status/type CHECK constraints ──────────────────────────
    op.create_check_constraint(
        "ck_position_status", "positions", "status IN ('OPEN', 'CLOSED')",
    )
    op.create_check_constraint(
        "ck_corp_action_status", "corporate_action_queue",
        "status IN ('PENDING', 'APPLIED', 'DISMISSED')",
    )
    op.create_check_constraint(
        "ck_backtest_status", "backtest_runs",
        "status IN ('PENDING', 'RUNNING', 'COMPLETED', 'FAILED', 'CANCELLED')",
    )
    op.create_check_constraint(
        "ck_transaction_type", "transactions",
        "transaction_type IN ("
        "'BUY', 'SELL', 'DIVIDEND', 'SPLIT', 'TRANSFER_IN', 'TRANSFER_OUT', "
        "'DEPOSIT', 'WITHDRAWAL', 'FEE', 'INTEREST'"
        ")",
    )

    # ── P4-M-027: created_by audit-trail columns ─────────────────────────
    op.add_column("positions", sa.Column("created_by", sa.String(100), nullable=True))
    op.add_column("backtest_runs", sa.Column("created_by", sa.String(100), nullable=True))

    # ── P4-M-028: backtest_runs.user_id (ownership) ──────────────────────
    op.add_column(
        "backtest_runs",
        sa.Column(
            "user_id", sa.String(100), nullable=False,
            server_default="default_user",
        ),
    )
    op.create_index("ix_backtest_runs_user_id", "backtest_runs", ["user_id"])

    # ── portfolio_watchlists / portfolio_watchlist_entries: no prior
    # migration created these tables at all (see module docstring) --
    # created here with P4-M-020 (unique constraint) and P4-M-027
    # (created_by) already applied.
    op.create_table(
        "portfolio_watchlists",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("user_id", sa.String(100), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("alert_config", JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("user_id", "name", name="uq_watchlist_user_name"),
    )
    op.create_index("ix_portfolio_watchlists_user_id", "portfolio_watchlists", ["user_id"])

    op.create_table(
        "portfolio_watchlist_entries",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column(
            "watchlist_id", sa.UUID(),
            sa.ForeignKey("portfolio_watchlists.id"), nullable=False,
        ),
        sa.Column(
            "entity_id", sa.UUID(),
            sa.ForeignKey("entities.entity_id"), nullable=False,
        ),
        sa.Column("added_date", sa.Date(), nullable=False),
        sa.Column("created_by", sa.String(100)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Index(
            "uq_pwl_entry_wl_entity", "watchlist_id", "entity_id", unique=True,
        ),
    )
    op.create_index(
        "ix_portfolio_watchlist_entries_watchlist_id",
        "portfolio_watchlist_entries", ["watchlist_id"],
    )
    op.create_index(
        "ix_portfolio_watchlist_entries_entity_id",
        "portfolio_watchlist_entries", ["entity_id"],
    )


def downgrade() -> None:
    op.drop_table("portfolio_watchlist_entries")
    op.drop_table("portfolio_watchlists")

    op.drop_index("ix_backtest_runs_user_id", table_name="backtest_runs")
    op.drop_column("backtest_runs", "user_id")
    op.drop_column("backtest_runs", "created_by")
    op.drop_column("positions", "created_by")

    op.drop_constraint("ck_transaction_type", "transactions", type_="check")
    op.drop_constraint("ck_backtest_status", "backtest_runs", type_="check")
    op.drop_constraint("ck_corp_action_status", "corporate_action_queue", type_="check")
    op.drop_constraint("ck_position_status", "positions", type_="check")

    op.drop_constraint("ck_regression_adj_r_squared_range", "regression_results", type_="check")
    op.drop_constraint("ck_regression_r_squared_range", "regression_results", type_="check")

    op.drop_constraint("ck_backtest_date_order", "backtest_runs", type_="check")
    op.drop_constraint("ck_report_period_order", "report_requests", type_="check")
    op.drop_constraint("ck_attr_period_order", "attribution_results", type_="check")
    op.drop_constraint("ck_perf_period_order", "performance_snapshots", type_="check")
    op.drop_constraint("ck_corp_action_ex_before_payment", "corporate_action_queue", type_="check")

    op.drop_index("ix_portfolio_uploads_user_id", table_name="portfolio_uploads")
    op.drop_column("portfolio_uploads", "user_id")

    op.drop_constraint("uq_attr_portfolio_period", "attribution_results", type_="unique")
    op.create_unique_constraint(
        "uq_attr_portfolio_type_end", "attribution_results",
        ["portfolio_id", "attribution_type", "period_end"],
    )

    op.drop_constraint("corporate_action_queue_position_id_fkey", "corporate_action_queue", type_="foreignkey")

    for table_name, fk_name in _PORTFOLIO_CASCADE_TARGETS:
        op.drop_constraint(fk_name, table_name, type_="foreignkey")
        op.create_foreign_key(
            fk_name, table_name, "portfolios", ["portfolio_id"], ["id"],
        )
