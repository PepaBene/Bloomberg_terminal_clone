"""Create risk and quantitative analytics tables.

Revision ID: 017
Revises: 016
Create Date: 2026-03-20
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "017"
down_revision: Union[str, None] = "016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── VaR Results ────────────────────────────────────────────────────
    op.create_table(
        "var_results",
        sa.Column("var_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("security_id", UUID(as_uuid=True), sa.ForeignKey("securities.security_id"), nullable=False, index=True),
        sa.Column("calculation_date", sa.Date, nullable=False),
        sa.Column("method", sa.String(20), nullable=False),
        sa.Column("confidence_level", sa.Numeric(4, 2), nullable=False),
        sa.Column("holding_period_days", sa.Integer, nullable=False),
        sa.Column("var_value", sa.Numeric(18, 6)),
        sa.Column("var_dollar", sa.Numeric(20, 2)),
        sa.Column("expected_shortfall", sa.Numeric(18, 6)),
        sa.Column("lookback_days", sa.Integer, nullable=False, server_default="252"),
        sa.Column("annualized_volatility", sa.Numeric(10, 6)),
        sa.Column("daily_mean_return", sa.Numeric(10, 8)),
        sa.Column("daily_std_return", sa.Numeric(10, 8)),
        sa.Column("skewness", sa.Numeric(8, 4)),
        sa.Column("kurtosis", sa.Numeric(8, 4)),
        sa.Column("data_quality", sa.String(20), nullable=False, server_default="COMPLETE"),
        sa.Column("inputs", JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "idx_var_security_date_method",
        "var_results",
        ["security_id", "calculation_date", "method", "confidence_level"],
    )

    # ── Stress Test Results ────────────────────────────────────────────
    op.create_table(
        "stress_test_results",
        sa.Column("stress_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("security_id", UUID(as_uuid=True), sa.ForeignKey("securities.security_id"), nullable=False, index=True),
        sa.Column("calculation_date", sa.Date, nullable=False),
        sa.Column("scenario_type", sa.String(20), nullable=False),
        sa.Column("scenario_name", sa.String(100), nullable=False),
        sa.Column("scenario_params", JSONB, nullable=False),
        sa.Column("pnl_percent", sa.Numeric(10, 6)),
        sa.Column("max_drawdown", sa.Numeric(10, 6)),
        sa.Column("recovery_days", sa.Integer),
        sa.Column("worst_day", sa.Numeric(10, 6)),
        sa.Column("best_day", sa.Numeric(10, 6)),
        sa.Column("data_quality", sa.String(20), nullable=False, server_default="COMPLETE"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "idx_stress_security_scenario",
        "stress_test_results",
        ["security_id", "scenario_name", "calculation_date"],
    )

    # ── Factor Exposures ───────────────────────────────────────────────
    op.create_table(
        "factor_exposures",
        sa.Column("exposure_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("security_id", UUID(as_uuid=True), sa.ForeignKey("securities.security_id"), nullable=False, index=True),
        sa.Column("calculation_date", sa.Date, nullable=False),
        sa.Column("factor_name", sa.String(30), nullable=False),
        sa.Column("z_score", sa.Numeric(8, 4)),
        sa.Column("raw_value", sa.Numeric(20, 6)),
        sa.Column("percentile_rank", sa.Numeric(6, 2)),
        sa.Column("data_quality", sa.String(20), nullable=False, server_default="COMPLETE"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_factor_security_date", "factor_exposures", ["security_id", "calculation_date"])
    op.create_index("idx_factor_name_date", "factor_exposures", ["factor_name", "calculation_date"])

    # ── Regression Results ─────────────────────────────────────────────
    op.create_table(
        "regression_results",
        sa.Column("regression_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("security_id", UUID(as_uuid=True), sa.ForeignKey("securities.security_id"), index=True),
        sa.Column("calculation_date", sa.Date, nullable=False),
        sa.Column("method", sa.String(20), nullable=False),
        sa.Column("dependent_var", sa.String(100), nullable=False),
        sa.Column("independent_vars", JSONB, nullable=False),
        sa.Column("coefficients", JSONB, nullable=False),
        sa.Column("std_errors", JSONB),
        sa.Column("r_squared", sa.Numeric(8, 6)),
        sa.Column("adj_r_squared", sa.Numeric(8, 6)),
        sa.Column("f_statistic", sa.Numeric(12, 4)),
        sa.Column("f_p_value", sa.Numeric(10, 8)),
        sa.Column("n_observations", sa.Integer, nullable=False),
        sa.Column("period_start", sa.Date),
        sa.Column("period_end", sa.Date),
        sa.Column("residuals_summary", JSONB),
        sa.Column("confidence_intervals", JSONB),
        sa.Column("data_quality", sa.String(20), nullable=False, server_default="COMPLETE"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "idx_reg_security_dep_date",
        "regression_results",
        ["security_id", "dependent_var", "calculation_date"],
    )

    # ── Correlation Results ────────────────────────────────────────────
    op.create_table(
        "correlation_results",
        sa.Column("correlation_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("calculation_date", sa.Date, nullable=False),
        sa.Column("method", sa.String(20), nullable=False),
        sa.Column("series_x_id", sa.String(100), nullable=False),
        sa.Column("series_y_id", sa.String(100), nullable=False),
        sa.Column("series_x_label", sa.String(100)),
        sa.Column("series_y_label", sa.String(100)),
        sa.Column("coefficient", sa.Numeric(8, 6)),
        sa.Column("p_value", sa.Numeric(10, 8)),
        sa.Column("n_observations", sa.Integer, nullable=False),
        sa.Column("period_start", sa.Date),
        sa.Column("period_end", sa.Date),
        sa.Column("data_quality", sa.String(20), nullable=False, server_default="COMPLETE"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "idx_corr_xy_date",
        "correlation_results",
        ["series_x_id", "series_y_id", "calculation_date"],
    )

    # ── Time Series Test Results ───────────────────────────────────────
    op.create_table(
        "time_series_test_results",
        sa.Column("test_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("security_id", UUID(as_uuid=True), sa.ForeignKey("securities.security_id"), index=True),
        sa.Column("calculation_date", sa.Date, nullable=False),
        sa.Column("test_type", sa.String(30), nullable=False),
        sa.Column("series_name", sa.String(100), nullable=False),
        sa.Column("test_statistic", sa.Numeric(12, 6)),
        sa.Column("p_value", sa.Numeric(10, 8)),
        sa.Column("critical_values", JSONB),
        sa.Column("is_significant", sa.Boolean),
        sa.Column("lags_used", sa.Integer),
        sa.Column("extra_params", JSONB),
        sa.Column("data_quality", sa.String(20), nullable=False, server_default="COMPLETE"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "idx_ts_security_test_date",
        "time_series_test_results",
        ["security_id", "test_type", "calculation_date"],
    )


def downgrade() -> None:
    op.drop_table("time_series_test_results")
    op.drop_table("correlation_results")
    op.drop_table("regression_results")
    op.drop_table("factor_exposures")
    op.drop_table("stress_test_results")
    op.drop_table("var_results")
