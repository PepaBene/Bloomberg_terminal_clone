"""Technical Backtester API endpoints (Pillar 2 Supplement – Part 6)."""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_session
from src.engines.technical_backtester import (
    generate_ma_crossover_signals,
    generate_rsi_signals,
    generate_bollinger_signals,
    run_technical_backtest,
)
from src.schemas.technical_backtest import (
    TechnicalBacktestResponse,
    TechnicalStrategyRequest,
)

router = APIRouter(tags=["Technical Backtest"])


@router.post(
    "/analytics/technical-backtest",
    response_model=TechnicalBacktestResponse,
)
async def submit_technical_backtest(
    body: TechnicalStrategyRequest,
    session: AsyncSession = Depends(get_session),
):
    """Run a technical strategy backtest on provided price data."""
    prices = body.prices
    if len(prices) < 2:
        return TechnicalBacktestResponse(
            backtest_id=uuid.uuid4(),
            name=body.name,
            indicator=body.indicator,
            total_trades=0,
            final_value=body.initial_capital,
            total_return=0.0,
            total_return_pct=0.0,
            signals_generated=0,
        )

    # Generate signals based on indicator type
    indicator = body.indicator.upper()
    signals = []

    if indicator == "MA_CROSSOVER":
        signals = generate_ma_crossover_signals(
            prices, body.fast_period, body.slow_period, body.ma_type,
        )
    elif indicator == "RSI":
        signals = generate_rsi_signals(
            prices, body.rsi_period, body.rsi_overbought, body.rsi_oversold,
        )
    elif indicator == "BOLLINGER":
        signals = generate_bollinger_signals(
            prices, body.bb_period, body.bb_std,
        )
    elif indicator == "COMBINED":
        signals.extend(generate_ma_crossover_signals(
            prices, body.fast_period, body.slow_period, body.ma_type,
        ))
        signals.extend(generate_rsi_signals(
            prices, body.rsi_period, body.rsi_overbought, body.rsi_oversold,
        ))
        signals.sort(key=lambda s: s.index)

    # Run backtest
    result = run_technical_backtest(
        prices, signals,
        initial_capital=body.initial_capital,
        position_size=body.position_size,
        transaction_cost_bps=body.transaction_cost_bps,
    )

    perf = result["performance"]

    return TechnicalBacktestResponse(
        backtest_id=uuid.uuid4(),
        name=body.name,
        indicator=indicator,
        total_trades=result["total_trades"],
        final_value=result["final_value"],
        total_return=result["total_return"],
        total_return_pct=perf.total_return * 100,
        annualized_return=perf.annualized_return * 100,
        annualized_volatility=perf.annualized_volatility * 100,
        sharpe_ratio=perf.sharpe_ratio,
        sortino_ratio=perf.sortino_ratio,
        max_drawdown=perf.max_drawdown * 100,
        win_rate=perf.win_rate,
        signals_generated=len(signals),
    )
