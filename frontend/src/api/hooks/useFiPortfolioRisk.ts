// =============================================================================
// Fixed Income — Portfolio-Level Risk — React Query Hooks
// Wraps src/api/routers/fi_risk.py (portfolio DV01/credit-distribution/
// expected-loss, rate & spread scenario P&L, single-bond risk metrics) --
// real, working backend routes that previously had zero frontend consumers
// (P4-F-012). Distinct from useFiRisk.ts, which wraps the single-instrument
// duration/convexity/scenario calculators in fi_bond_analytics.py.
// =============================================================================

import { useMutation, useQuery } from '@tanstack/react-query';
import { api } from '../client';
import { FI_RISK } from '../endpoints';

export interface FiRiskPosition {
  cusip?: string | null;
  market_value: number;
  modified_duration: number;
  convexity?: number;
  spread_duration?: number | null;
  rating_numeric?: number | null;
  seniority?: string;
  is_investment_grade?: boolean | null;
}

export interface PositionPnl {
  cusip: string | null;
  pnl: number;
  pnl_pct: number;
}

export interface PortfolioRiskResponse {
  portfolio_dv01: number;
  total_market_value: number;
  credit_distribution: Record<string, unknown>;
  expected_loss: number;
  expected_loss_pct: number;
  position_count: number;
}

export interface ScenarioPnlResponse {
  total_pnl: number;
  total_pnl_pct: number;
  shift_bps: number;
  by_position: PositionPnl[];
}

export interface BondRiskMetricsResponse {
  cusip: string;
  dv01: number;
  rate_pnl_100bps: number;
  spread_pnl_100bps: number;
  expected_loss: number | null;
  pd_1y: number | null;
  lgd: number | null;
  rating_numeric: number | null;
}

/** Portfolio-level DV01, credit distribution, and expected loss for a basket of bond positions. */
export function useFiPortfolioRisk() {
  return useMutation<PortfolioRiskResponse, Error, { positions: FiRiskPosition[] }>({
    mutationFn: (body) => api.post<PortfolioRiskResponse>(FI_RISK.portfolioRisk, body),
  });
}

/** P&L from a parallel interest-rate shift (duration-convexity approximation). */
export function useFiRateScenario() {
  return useMutation<ScenarioPnlResponse, Error, { positions: FiRiskPosition[]; rate_shift_bps: number }>({
    mutationFn: (body) => api.post<ScenarioPnlResponse>(FI_RISK.rateScenario, body),
  });
}

/** P&L from a credit-spread widening/tightening shock. */
export function useFiSpreadScenario() {
  return useMutation<ScenarioPnlResponse, Error, { positions: FiRiskPosition[]; spread_shift_bps: number }>({
    mutationFn: (body) => api.post<ScenarioPnlResponse>(FI_RISK.spreadScenario, body),
  });
}

/** Full risk metrics (DV01, rate/spread P&L, credit risk) for a single bond by CUSIP. */
export function useBondRiskMetrics(cusip: string | undefined, options?: { enabled?: boolean }) {
  return useQuery<BondRiskMetricsResponse>({
    queryKey: ['fiRisk', 'bondRiskMetrics', cusip],
    queryFn: () => api.get<BondRiskMetricsResponse>(FI_RISK.bondRiskMetrics(cusip!)),
    enabled: options?.enabled ?? !!cusip,
  });
}
