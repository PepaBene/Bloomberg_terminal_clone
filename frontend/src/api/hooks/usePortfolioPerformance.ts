// =============================================================================
// Portfolio Performance — React Query Hooks
// =============================================================================

import { useQuery, useMutation } from '@tanstack/react-query';
import { api } from '../client';
import { PORTFOLIO_PERFORMANCE } from '../endpoints';

const STALE_1H = 60 * 60 * 1000;

// ---------------------------------------------------------------------------
// Summary / Returns
// ---------------------------------------------------------------------------

export function usePerformanceSummary(portfolioId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['portfolio-performance', portfolioId, 'summary'],
    queryFn: () => api.get(PORTFOLIO_PERFORMANCE.summary(portfolioId)),
    enabled: options?.enabled ?? !!portfolioId,
    staleTime: STALE_1H,
  });
}

export function useReturns(portfolioId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['portfolio-performance', portfolioId, 'returns'],
    queryFn: () => api.get(PORTFOLIO_PERFORMANCE.returns(portfolioId)),
    enabled: options?.enabled ?? !!portfolioId,
    staleTime: STALE_1H,
  });
}

export function useCalendarReturns(portfolioId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['portfolio-performance', portfolioId, 'calendarReturns'],
    queryFn: () => api.get(PORTFOLIO_PERFORMANCE.calendarReturns(portfolioId)),
    enabled: options?.enabled ?? !!portfolioId,
    staleTime: STALE_1H,
  });
}

// ---------------------------------------------------------------------------
// Attribution
// ---------------------------------------------------------------------------

export function useAttribution(portfolioId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['portfolio-performance', portfolioId, 'attribution'],
    queryFn: () => api.get(PORTFOLIO_PERFORMANCE.attribution(portfolioId)),
    enabled: options?.enabled ?? !!portfolioId,
    staleTime: STALE_1H,
  });
}

export function useAttributionBySector(portfolioId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['portfolio-performance', portfolioId, 'attribution', 'sector'],
    queryFn: () => api.get(PORTFOLIO_PERFORMANCE.attributionBySector(portfolioId)),
    enabled: options?.enabled ?? !!portfolioId,
    staleTime: STALE_1H,
  });
}

export function useAttributionByFactor(portfolioId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['portfolio-performance', portfolioId, 'attribution', 'factor'],
    queryFn: () => api.get(PORTFOLIO_PERFORMANCE.attributionByFactor(portfolioId)),
    enabled: options?.enabled ?? !!portfolioId,
    staleTime: STALE_1H,
  });
}

export function useAttributionByCountry(portfolioId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['portfolio-performance', portfolioId, 'attribution', 'country'],
    queryFn: () => api.get(PORTFOLIO_PERFORMANCE.attributionByCountry(portfolioId)),
    enabled: options?.enabled ?? !!portfolioId,
    staleTime: STALE_1H,
  });
}

// ---------------------------------------------------------------------------
// Benchmark / Risk Metrics
// ---------------------------------------------------------------------------

export function useBenchmarkComparison(portfolioId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['portfolio-performance', portfolioId, 'benchmark'],
    queryFn: () => api.get(PORTFOLIO_PERFORMANCE.benchmark(portfolioId)),
    enabled: options?.enabled ?? !!portfolioId,
    staleTime: STALE_1H,
  });
}

export function usePerformanceRiskMetrics(portfolioId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['portfolio-performance', portfolioId, 'riskMetrics'],
    queryFn: () => api.get(PORTFOLIO_PERFORMANCE.riskMetrics(portfolioId)),
    enabled: options?.enabled ?? !!portfolioId,
    staleTime: STALE_1H,
  });
}

// ---------------------------------------------------------------------------
// Compare — mutation (POST)
// ---------------------------------------------------------------------------

export function usePerformanceCompare() {
  return useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      api.post(PORTFOLIO_PERFORMANCE.compare, body),
  });
}

// ---------------------------------------------------------------------------
// Advanced Metrics
// ---------------------------------------------------------------------------

export function useDrawdown(portfolioId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['portfolio-performance', portfolioId, 'drawdown'],
    queryFn: () => api.get(PORTFOLIO_PERFORMANCE.drawdown(portfolioId)),
    enabled: options?.enabled ?? !!portfolioId,
    staleTime: STALE_1H,
  });
}

export function useRollingReturns(portfolioId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['portfolio-performance', portfolioId, 'rollingReturns'],
    queryFn: () => api.get(PORTFOLIO_PERFORMANCE.rollingReturns(portfolioId)),
    enabled: options?.enabled ?? !!portfolioId,
    staleTime: STALE_1H,
  });
}

export function useAlpha(portfolioId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['portfolio-performance', portfolioId, 'alpha'],
    queryFn: () => api.get(PORTFOLIO_PERFORMANCE.alpha(portfolioId)),
    enabled: options?.enabled ?? !!portfolioId,
    staleTime: STALE_1H,
  });
}

export function useSharpeHistory(portfolioId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['portfolio-performance', portfolioId, 'sharpeHistory'],
    queryFn: () => api.get(PORTFOLIO_PERFORMANCE.sharpeHistory(portfolioId)),
    enabled: options?.enabled ?? !!portfolioId,
    staleTime: STALE_1H,
  });
}

export function useTrackingError(portfolioId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['portfolio-performance', portfolioId, 'trackingError'],
    queryFn: () => api.get(PORTFOLIO_PERFORMANCE.trackingError(portfolioId)),
    enabled: options?.enabled ?? !!portfolioId,
    staleTime: STALE_1H,
  });
}

export function useInformationRatio(portfolioId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['portfolio-performance', portfolioId, 'informationRatio'],
    queryFn: () => api.get(PORTFOLIO_PERFORMANCE.informationRatio(portfolioId)),
    enabled: options?.enabled ?? !!portfolioId,
    staleTime: STALE_1H,
  });
}

export function useUpDownCapture(portfolioId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['portfolio-performance', portfolioId, 'upDownCapture'],
    queryFn: () => api.get(PORTFOLIO_PERFORMANCE.upDownCapture(portfolioId)),
    enabled: options?.enabled ?? !!portfolioId,
    staleTime: STALE_1H,
  });
}

export function useHoldingPeriodReturns(portfolioId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['portfolio-performance', portfolioId, 'holdingPeriodReturns'],
    queryFn: () => api.get(PORTFOLIO_PERFORMANCE.holdingPeriodReturns(portfolioId)),
    enabled: options?.enabled ?? !!portfolioId,
    staleTime: STALE_1H,
  });
}
