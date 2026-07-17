// =============================================================================
// Technical Backtester — React Query Hook
// Wraps POST /v1/analytics/technical-backtest (src/api/routers/
// technical_backtest.py) -- a real, working backend feature that previously
// had zero frontend consumers (P4-F-011).
// =============================================================================

import { useMutation } from '@tanstack/react-query';
import { api } from '../client';
import { TECHNICAL_BACKTEST } from '../endpoints';

export type TechnicalIndicator = 'MA_CROSSOVER' | 'RSI' | 'BOLLINGER' | 'COMBINED';

export interface TechnicalStrategyRequest {
  name?: string;
  indicator?: TechnicalIndicator;
  fast_period?: number;
  slow_period?: number;
  ma_type?: string;
  rsi_period?: number;
  rsi_overbought?: number;
  rsi_oversold?: number;
  bb_period?: number;
  bb_std?: number;
  initial_capital?: number;
  position_size?: number;
  transaction_cost_bps?: number;
  prices: number[];
}

export interface TechnicalBacktestResponse {
  backtest_id: string | null;
  name: string;
  indicator: string;
  total_trades: number;
  final_value: number;
  total_return: number;
  total_return_pct: number;
  annualized_return: number;
  annualized_volatility: number;
  sharpe_ratio: number | null;
  sortino_ratio: number | null;
  max_drawdown: number;
  win_rate: number;
  signals_generated: number;
}

/** Run a technical-indicator strategy backtest against a provided price series. */
export function useTechnicalBacktest() {
  return useMutation<TechnicalBacktestResponse, Error, TechnicalStrategyRequest>({
    mutationFn: (body) => api.post<TechnicalBacktestResponse>(TECHNICAL_BACKTEST.run, body),
  });
}
