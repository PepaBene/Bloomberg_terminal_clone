// =============================================================================
// Risk Analytics Domain — React Query Hooks
// Wraps /v4/portfolios/:id/risk endpoints for portfolio risk management
// =============================================================================

import { useQuery, useMutation } from '@tanstack/react-query';
import { api } from '../client';
import { PORTFOLIO_RISK } from '../endpoints';

const STALE_1H = 60 * 60 * 1000;

// ---------------------------------------------------------------------------
// Risk Dashboard
// ---------------------------------------------------------------------------

export function useRiskDashboard(portfolioId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['risk', 'dashboard', portfolioId],
    queryFn: () => api.get(PORTFOLIO_RISK.dashboard(portfolioId)),
    enabled: options?.enabled ?? !!portfolioId,
    staleTime: STALE_1H,
  });
}

// ---------------------------------------------------------------------------
// Value at Risk
// ---------------------------------------------------------------------------

export function useVaR(portfolioId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['risk', 'var', portfolioId],
    queryFn: () => api.get(PORTFOLIO_RISK.var(portfolioId)),
    enabled: options?.enabled ?? !!portfolioId,
    staleTime: STALE_1H,
  });
}

export function useVaRDecomposition(portfolioId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['risk', 'varDecomposition', portfolioId],
    queryFn: () => api.get(PORTFOLIO_RISK.varDecomposition(portfolioId)),
    enabled: options?.enabled ?? !!portfolioId,
    staleTime: STALE_1H,
  });
}

export function useVaRBacktest(portfolioId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['risk', 'varBacktest', portfolioId],
    queryFn: () => api.get(PORTFOLIO_RISK.varBacktest(portfolioId)),
    enabled: options?.enabled ?? !!portfolioId,
    staleTime: STALE_1H,
  });
}

export function useCVaR(portfolioId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['risk', 'cvar', portfolioId],
    queryFn: () => api.get(PORTFOLIO_RISK.cvar(portfolioId)),
    enabled: options?.enabled ?? !!portfolioId,
    staleTime: STALE_1H,
  });
}

// ---------------------------------------------------------------------------
// Concentration & Factors
// ---------------------------------------------------------------------------

export function useConcentration(portfolioId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['risk', 'concentration', portfolioId],
    queryFn: () => api.get(PORTFOLIO_RISK.concentration(portfolioId)),
    enabled: options?.enabled ?? !!portfolioId,
    staleTime: STALE_1H,
  });
}

export function useRiskFactors(portfolioId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['risk', 'factors', portfolioId],
    queryFn: () => api.get(PORTFOLIO_RISK.factors(portfolioId)),
    enabled: options?.enabled ?? !!portfolioId,
    staleTime: STALE_1H,
  });
}

export function useRiskFactorExposure(portfolioId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['risk', 'factorExposure', portfolioId],
    queryFn: () => api.get(PORTFOLIO_RISK.factorExposure(portfolioId)),
    enabled: options?.enabled ?? !!portfolioId,
    staleTime: STALE_1H,
  });
}

// ---------------------------------------------------------------------------
// Stress Testing
// ---------------------------------------------------------------------------

export function useStressHistorical(portfolioId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['risk', 'stressHistorical', portfolioId],
    queryFn: () => api.get(PORTFOLIO_RISK.stressHistorical(portfolioId)),
    enabled: options?.enabled ?? !!portfolioId,
    staleTime: STALE_1H,
  });
}

export function useStressHypothetical(portfolioId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['risk', 'stressHypothetical', portfolioId],
    queryFn: () => api.get(PORTFOLIO_RISK.stressHypothetical(portfolioId)),
    enabled: options?.enabled ?? !!portfolioId,
    staleTime: STALE_1H,
  });
}

export function useStressCustom() {
  return useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      api.post(PORTFOLIO_RISK.scenarios, body),
  });
}

// ---------------------------------------------------------------------------
// Scenarios
// ---------------------------------------------------------------------------

export function useScenarios(options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['risk', 'scenarios'],
    queryFn: () => api.get(PORTFOLIO_RISK.scenarios),
    enabled: options?.enabled ?? true,
    staleTime: STALE_1H,
  });
}

export function useScenarioDetail(scenarioId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['risk', 'scenarioDetail', scenarioId],
    queryFn: () => api.get(PORTFOLIO_RISK.scenarioDetail(scenarioId)),
    enabled: options?.enabled ?? !!scenarioId,
    staleTime: STALE_1H,
  });
}

// ---------------------------------------------------------------------------
// Compliance
// ---------------------------------------------------------------------------

export function useCompliance(portfolioId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['risk', 'compliance', portfolioId],
    queryFn: () => api.get(PORTFOLIO_RISK.compliance(portfolioId)),
    enabled: options?.enabled ?? !!portfolioId,
    staleTime: STALE_1H,
  });
}

export function useComplianceRules(portfolioId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['risk', 'complianceRules', portfolioId],
    queryFn: () => api.get(PORTFOLIO_RISK.complianceRules(portfolioId)),
    enabled: options?.enabled ?? !!portfolioId,
    staleTime: STALE_1H,
  });
}

export function useAddComplianceRule(portfolioId: string) {
  return useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      api.post(PORTFOLIO_RISK.complianceAddRule(portfolioId), body),
  });
}

export function useComplianceHistory(portfolioId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['risk', 'complianceHistory', portfolioId],
    queryFn: () => api.get(PORTFOLIO_RISK.complianceHistory(portfolioId)),
    enabled: options?.enabled ?? !!portfolioId,
    staleTime: STALE_1H,
  });
}

export function usePreTradeCheck(portfolioId: string) {
  return useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      api.post(PORTFOLIO_RISK.preTradeCheck(portfolioId), body),
  });
}

// ---------------------------------------------------------------------------
// Drift
// ---------------------------------------------------------------------------

export function useDrift(portfolioId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['risk', 'drift', portfolioId],
    queryFn: () => api.get(PORTFOLIO_RISK.drift(portfolioId)),
    enabled: options?.enabled ?? !!portfolioId,
    staleTime: STALE_1H,
  });
}

export function useDriftRebalance(portfolioId: string) {
  return useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      api.post(PORTFOLIO_RISK.driftRebalance(portfolioId), body),
  });
}

export function useDriftHistory(portfolioId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['risk', 'driftHistory', portfolioId],
    queryFn: () => api.get(PORTFOLIO_RISK.driftHistory(portfolioId)),
    enabled: options?.enabled ?? !!portfolioId,
    staleTime: STALE_1H,
  });
}

// ---------------------------------------------------------------------------
// Liquidity, Correlation & Tail Risk
// ---------------------------------------------------------------------------

export function useLiquidity(portfolioId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['risk', 'liquidity', portfolioId],
    queryFn: () => api.get(PORTFOLIO_RISK.liquidity(portfolioId)),
    enabled: options?.enabled ?? !!portfolioId,
    staleTime: STALE_1H,
  });
}

export function useRiskCorrelation(portfolioId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['risk', 'correlation', portfolioId],
    queryFn: () => api.get(PORTFOLIO_RISK.correlation(portfolioId)),
    enabled: options?.enabled ?? !!portfolioId,
    staleTime: STALE_1H,
  });
}

export function useTailRisk(portfolioId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['risk', 'tailRisk', portfolioId],
    queryFn: () => api.get(PORTFOLIO_RISK.tailRisk(portfolioId)),
    enabled: options?.enabled ?? !!portfolioId,
    staleTime: STALE_1H,
  });
}

// ---------------------------------------------------------------------------
// Beta & Volatility
// ---------------------------------------------------------------------------

export function useBeta(portfolioId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['risk', 'beta', portfolioId],
    queryFn: () => api.get(PORTFOLIO_RISK.beta(portfolioId)),
    enabled: options?.enabled ?? !!portfolioId,
    staleTime: STALE_1H,
  });
}

export function useRiskVolatility(portfolioId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['risk', 'volatility', portfolioId],
    queryFn: () => api.get(PORTFOLIO_RISK.volatility(portfolioId)),
    enabled: options?.enabled ?? !!portfolioId,
    staleTime: STALE_1H,
  });
}

// ---------------------------------------------------------------------------
// Credit, Interest Rate & Currency Risk
// ---------------------------------------------------------------------------

export function useCreditRisk(portfolioId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['risk', 'creditRisk', portfolioId],
    queryFn: () => api.get(PORTFOLIO_RISK.creditRisk(portfolioId)),
    enabled: options?.enabled ?? !!portfolioId,
    staleTime: STALE_1H,
  });
}

export function useInterestRateRisk(portfolioId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['risk', 'interestRateRisk', portfolioId],
    queryFn: () => api.get(PORTFOLIO_RISK.interestRateRisk(portfolioId)),
    enabled: options?.enabled ?? !!portfolioId,
    staleTime: STALE_1H,
  });
}

export function useCurrencyRisk(portfolioId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['risk', 'currencyRisk', portfolioId],
    queryFn: () => api.get(PORTFOLIO_RISK.currencyRisk(portfolioId)),
    enabled: options?.enabled ?? !!portfolioId,
    staleTime: STALE_1H,
  });
}

// ---------------------------------------------------------------------------
// Margin Requirements
// ---------------------------------------------------------------------------

export function useMarginRequirements(portfolioId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['risk', 'marginRequirements', portfolioId],
    queryFn: () => api.get(PORTFOLIO_RISK.marginRequirements(portfolioId)),
    enabled: options?.enabled ?? !!portfolioId,
    staleTime: STALE_1H,
  });
}
