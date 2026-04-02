// =============================================================================
// Fundamentals — React Query Hooks
// =============================================================================

import { useQuery } from '@tanstack/react-query';
import { api } from '../client';
import { FUNDAMENTALS } from '../endpoints';

const STALE_24H = 24 * 60 * 60 * 1000;

export function useIncomeStatements(
  entityId: string,
  params?: Record<string, string | number | boolean | undefined>,
  options?: { enabled?: boolean },
) {
  return useQuery({
    queryKey: ['fundamentals', 'incomeStatements', entityId, params],
    queryFn: () => api.get(FUNDAMENTALS.incomeStatements(entityId), params),
    enabled: options?.enabled ?? !!entityId,
    staleTime: STALE_24H,
  });
}

export function useBalanceSheets(
  entityId: string,
  params?: Record<string, string | number | boolean | undefined>,
  options?: { enabled?: boolean },
) {
  return useQuery({
    queryKey: ['fundamentals', 'balanceSheets', entityId, params],
    queryFn: () => api.get(FUNDAMENTALS.balanceSheets(entityId), params),
    enabled: options?.enabled ?? !!entityId,
    staleTime: STALE_24H,
  });
}

export function useCashFlows(
  entityId: string,
  params?: Record<string, string | number | boolean | undefined>,
  options?: { enabled?: boolean },
) {
  return useQuery({
    queryKey: ['fundamentals', 'cashFlows', entityId, params],
    queryFn: () => api.get(FUNDAMENTALS.cashFlows(entityId), params),
    enabled: options?.enabled ?? !!entityId,
    staleTime: STALE_24H,
  });
}

export function useFilings(entityId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['fundamentals', 'filings', entityId],
    queryFn: () => api.get(FUNDAMENTALS.filings(entityId)),
    enabled: options?.enabled ?? !!entityId,
    staleTime: STALE_24H,
  });
}

export function useSegments(entityId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['fundamentals', 'segments', entityId],
    queryFn: () => api.get(FUNDAMENTALS.segments(entityId)),
    enabled: options?.enabled ?? !!entityId,
    staleTime: STALE_24H,
  });
}

export function useRatios(entityId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['fundamentals', 'ratios', entityId],
    queryFn: () => api.get(FUNDAMENTALS.ratios(entityId)),
    enabled: options?.enabled ?? !!entityId,
    staleTime: STALE_24H,
  });
}

export function useRevenueBreakdown(entityId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['fundamentals', 'revenueBreakdown', entityId],
    queryFn: () => api.get(FUNDAMENTALS.revenueBreakdown(entityId)),
    enabled: options?.enabled ?? !!entityId,
    staleTime: STALE_24H,
  });
}

export function useGeographicBreakdown(entityId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['fundamentals', 'geographicBreakdown', entityId],
    queryFn: () => api.get(FUNDAMENTALS.geographicBreakdown(entityId)),
    enabled: options?.enabled ?? !!entityId,
    staleTime: STALE_24H,
  });
}

export function useQuarterlyTrends(entityId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['fundamentals', 'quarterlyTrends', entityId],
    queryFn: () => api.get(FUNDAMENTALS.quarterlyTrends(entityId)),
    enabled: options?.enabled ?? !!entityId,
    staleTime: STALE_24H,
  });
}

export function useAnnualSummary(entityId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['fundamentals', 'annualSummary', entityId],
    queryFn: () => api.get(FUNDAMENTALS.annualSummary(entityId)),
    enabled: options?.enabled ?? !!entityId,
    staleTime: STALE_24H,
  });
}

export function useKpis(entityId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['fundamentals', 'kpis', entityId],
    queryFn: () => api.get(FUNDAMENTALS.kpis(entityId)),
    enabled: options?.enabled ?? !!entityId,
    staleTime: STALE_24H,
  });
}
