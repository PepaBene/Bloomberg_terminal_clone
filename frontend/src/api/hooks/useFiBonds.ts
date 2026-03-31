// =============================================================================
// Fixed Income — Bonds, Analytics, Indices, Screening — React Query Hooks
// =============================================================================

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../client';
import { FI } from '../endpoints';

const STALE_24H = 24 * 60 * 60 * 1000;
const STALE_1H = 60 * 60 * 1000;

// ---------------------------------------------------------------------------
// Bonds
// ---------------------------------------------------------------------------

export function useBonds(params?: Record<string, string | number | boolean | undefined>) {
  return useQuery({
    queryKey: ['fi', 'bonds', 'list', params],
    queryFn: () => api.get(FI.bonds.list, params),
    staleTime: STALE_24H,
  });
}

export function useBondDetail(cusip: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['fi', 'bonds', 'detail', cusip],
    queryFn: () => api.get(FI.bonds.detail(cusip)),
    enabled: options?.enabled ?? !!cusip,
    staleTime: STALE_24H,
  });
}

export function useBondPrices(cusip: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['fi', 'bonds', 'prices', cusip],
    queryFn: () => api.get(FI.bonds.prices(cusip)),
    enabled: options?.enabled ?? !!cusip,
    staleTime: STALE_24H,
  });
}

export function useBondSpreads(cusip: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['fi', 'bonds', 'spreads', cusip],
    queryFn: () => api.get(FI.bonds.spreads(cusip)),
    enabled: options?.enabled ?? !!cusip,
    staleTime: STALE_24H,
  });
}

export function useBondsByIssuer(entityId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['fi', 'bonds', 'byIssuer', entityId],
    queryFn: () => api.get(FI.bonds.byIssuer(entityId)),
    enabled: options?.enabled ?? !!entityId,
    staleTime: STALE_24H,
  });
}

export function useBondSearch() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Record<string, unknown>) => api.post(FI.bonds.search, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['fi', 'bonds'] });
    },
  });
}

export function useBondCashFlows(cusip: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['fi', 'bonds', 'cashFlows', cusip],
    queryFn: () => api.get(FI.bonds.cashFlows(cusip)),
    enabled: options?.enabled ?? !!cusip,
    staleTime: STALE_24H,
  });
}

export function useBondCallSchedule(cusip: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['fi', 'bonds', 'callSchedule', cusip],
    queryFn: () => api.get(FI.bonds.callSchedule(cusip)),
    enabled: options?.enabled ?? !!cusip,
    staleTime: STALE_24H,
  });
}

export function useBondCovenants(cusip: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['fi', 'bonds', 'covenants', cusip],
    queryFn: () => api.get(FI.bonds.covenants(cusip)),
    enabled: options?.enabled ?? !!cusip,
    staleTime: STALE_24H,
  });
}

export function useBondComparables(cusip: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['fi', 'bonds', 'comparables', cusip],
    queryFn: () => api.get(FI.bonds.comparables(cusip)),
    enabled: options?.enabled ?? !!cusip,
    staleTime: STALE_24H,
  });
}

// ---------------------------------------------------------------------------
// FI Analytics (mutations — POST)
// ---------------------------------------------------------------------------

export function useFiAnalyticsPrice() {
  return useMutation({
    mutationFn: (body: Record<string, unknown>) => api.post(FI.analytics.price, body),
  });
}

export function useFiAnalyticsYield() {
  return useMutation({
    mutationFn: (body: Record<string, unknown>) => api.post(FI.analytics.yield, body),
  });
}

export function useFiAnalyticsDuration() {
  return useMutation({
    mutationFn: (body: Record<string, unknown>) => api.post(FI.analytics.duration, body),
  });
}

export function useFiAnalyticsOas() {
  return useMutation({
    mutationFn: (body: Record<string, unknown>) => api.post(FI.analytics.oas, body),
  });
}

export function useFiAnalyticsSpread() {
  return useMutation({
    mutationFn: (body: Record<string, unknown>) => api.post(FI.analytics.spread, body),
  });
}

export function useFiAnalyticsConvexity() {
  return useMutation({
    mutationFn: (body: Record<string, unknown>) => api.post(FI.analytics.convexity, body),
  });
}

export function useFiAnalyticsKeyRate() {
  return useMutation({
    mutationFn: (body: Record<string, unknown>) => api.post(FI.analytics.keyRate, body),
  });
}

export function useFiAnalyticsTotalReturn() {
  return useMutation({
    mutationFn: (body: Record<string, unknown>) => api.post(FI.analytics.totalReturn, body),
  });
}

export function useFiAnalyticsScenario() {
  return useMutation({
    mutationFn: (body: Record<string, unknown>) => api.post(FI.analytics.scenario, body),
  });
}

export function useFiAnalyticsRollDown() {
  return useMutation({
    mutationFn: (body: Record<string, unknown>) => api.post(FI.analytics.rollDown, body),
  });
}

// ---------------------------------------------------------------------------
// Screening & New Issues
// ---------------------------------------------------------------------------

export function useFiScreen() {
  return useMutation({
    mutationFn: (body: Record<string, unknown>) => api.post(FI.screen, body),
  });
}

export function useNewIssues(params?: Record<string, string | number | boolean | undefined>) {
  return useQuery({
    queryKey: ['fi', 'newIssues', params],
    queryFn: () => api.get(FI.newIssues, params),
    staleTime: STALE_24H,
  });
}

export function useNewIssuesPipeline(params?: Record<string, string | number | boolean | undefined>) {
  return useQuery({
    queryKey: ['fi', 'newIssuesPipeline', params],
    queryFn: () => api.get(FI.newIssuesPipeline, params),
    staleTime: STALE_24H,
  });
}

// ---------------------------------------------------------------------------
// FI Indices
// ---------------------------------------------------------------------------

export function useFiIndices(params?: Record<string, string | number | boolean | undefined>) {
  return useQuery({
    queryKey: ['fi', 'indices', 'list', params],
    queryFn: () => api.get(FI.indices.list, params),
    staleTime: STALE_24H,
  });
}

export function useFiIndexDetail(id: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['fi', 'indices', 'detail', id],
    queryFn: () => api.get(FI.indices.detail(id)),
    enabled: options?.enabled ?? !!id,
    staleTime: STALE_24H,
  });
}

export function useFiIndexConstituents(id: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['fi', 'indices', 'constituents', id],
    queryFn: () => api.get(FI.indices.constituents(id)),
    enabled: options?.enabled ?? !!id,
    staleTime: STALE_1H,
  });
}

export function useFiIndexReturns(id: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['fi', 'indices', 'returns', id],
    queryFn: () => api.get(FI.indices.returns(id)),
    enabled: options?.enabled ?? !!id,
    staleTime: STALE_1H,
  });
}
