"""D11 FI Supplement: Extend YieldCurveSnapshot with zero/df/fwd/NSV columns."""
revision = "036"
down_revision = "035"

from alembic import op
import sqlalchemy as sa

def upgrade():
    # Zero rates
    for tenor in ["1m","3m","6m","1y","2y","3y","5y","7y","10y","20y","30y"]:
        op.add_column("yield_curve_snapshots", sa.Column(f"zero_{tenor}", sa.Numeric(8,6)))
    # Discount factors
    for tenor in ["1y","2y","5y","10y","20y","30y"]:
        op.add_column("yield_curve_snapshots", sa.Column(f"df_{tenor}", sa.Numeric(12,8)))
    # Forward rates
    for fwd in ["0to1y","1to2y","2to5y","5to10y","10to30y"]:
        op.add_column("yield_curve_snapshots", sa.Column(f"fwd_{fwd}", sa.Numeric(8,6)))
    # NSV params
    for p in ["beta0","beta1","beta2","beta3","lambda1","lambda2"]:
        op.add_column("yield_curve_snapshots", sa.Column(f"nsv_{p}", sa.Numeric(10,6)))
    op.add_column("yield_curve_snapshots", sa.Column("nsv_fit_error", sa.Numeric(10,8)))
    # Spreads
    op.add_column("yield_curve_snapshots", sa.Column("butterfly_spread", sa.Numeric(8,4)))
    op.add_column("yield_curve_snapshots", sa.Column("spread_5s30s", sa.Numeric(8,4)))

def downgrade():
    op.drop_column("yield_curve_snapshots", "spread_5s30s")
    op.drop_column("yield_curve_snapshots", "butterfly_spread")
    op.drop_column("yield_curve_snapshots", "nsv_fit_error")
    for p in reversed(["beta0","beta1","beta2","beta3","lambda1","lambda2"]):
        op.drop_column("yield_curve_snapshots", f"nsv_{p}")
    for fwd in reversed(["0to1y","1to2y","2to5y","5to10y","10to30y"]):
        op.drop_column("yield_curve_snapshots", f"fwd_{fwd}")
    for tenor in reversed(["1y","2y","5y","10y","20y","30y"]):
        op.drop_column("yield_curve_snapshots", f"df_{tenor}")
    for tenor in reversed(["1m","3m","6m","1y","2y","3y","5y","7y","10y","20y","30y"]):
        op.drop_column("yield_curve_snapshots", f"zero_{tenor}")
