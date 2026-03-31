// =============================================================================
// Industry Domain — React Query Hooks
// Wraps /v3/industry endpoints for industry-level analysis
// =============================================================================

import { useQuery, useMutation } from '@tanstack/react-query';
import { api } from '../client';
import { INDUSTRY } from '../endpoints';

const STALE_24H = 24 * 60 * 60 * 1000;

// ---------------------------------------------------------------------------
// Industry Overview & Economics
// ---------------------------------------------------------------------------

export function useIndustryOverview(gicsCode: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['industry', 'overview', gicsCode],
    queryFn: () => api.get(INDUSTRY.overview(gicsCode)),
    enabled: options?.enabled ?? !!gicsCode,
    staleTime: STALE_24H,
  });
}

export function useIndustryEconomics(gicsCode: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['industry', 'economics', gicsCode],
    queryFn: () => api.get(INDUSTRY.economics(gicsCode)),
    enabled: options?.enabled ?? !!gicsCode,
    staleTime: STALE_24H,
  });
}

export function useIndustryCycle(gicsCode: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['industry', 'cycle', gicsCode],
    queryFn: () => api.get(INDUSTRY.cycle(gicsCode)),
    enabled: options?.enabled ?? !!gicsCode,
    staleTime: STALE_24H,
  });
}

// ---------------------------------------------------------------------------
// Compare — POST mutation
// ---------------------------------------------------------------------------

export function useIndustryCompare() {
  return useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      api.post(INDUSTRY.compare, body),
  });
}

// ---------------------------------------------------------------------------
// Rankings & Leaders
// ---------------------------------------------------------------------------

export function useIndustryRankings() {
  return useQuery({
    queryKey: ['industry', 'rankings'],
    queryFn: () => api.get(INDUSTRY.rankings),
    staleTime: STALE_24H,
  });
}

export function useIndustryLeaders(gicsCode: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['industry', 'leaders', gicsCode],
    queryFn: () => api.get(INDUSTRY.leaders(gicsCode)),
    enabled: options?.enabled ?? !!gicsCode,
    staleTime: STALE_24H,
  });
}

// ---------------------------------------------------------------------------
// Trends & Valuation
// ---------------------------------------------------------------------------

export function useIndustryTrends(gicsCode: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['industry', 'trends', gicsCode],
    queryFn: () => api.get(INDUSTRY.trends(gicsCode)),
    enabled: options?.enabled ?? !!gicsCode,
    staleTime: STALE_24H,
  });
}

export function useIndustryValuationBands(gicsCode: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['industry', 'valuationBands', gicsCode],
    queryFn: () => api.get(INDUSTRY.valuationBands(gicsCode)),
    enabled: options?.enabled ?? !!gicsCode,
    staleTime: STALE_24H,
  });
}

// ---------------------------------------------------------------------------
// Constituents & Flows
// ---------------------------------------------------------------------------

export function useIndustryConstituents(gicsCode: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['industry', 'constituents', gicsCode],
    queryFn: () => api.get(INDUSTRY.constituents(gicsCode)),
    enabled: options?.enabled ?? !!gicsCode,
    staleTime: STALE_24H,
  });
}

export function useIndustryFlows(gicsCode: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['industry', 'flows', gicsCode],
    queryFn: () => api.get(INDUSTRY.flows(gicsCode)),
    enabled: options?.enabled ?? !!gicsCode,
    staleTime: STALE_24H,
  });
}

// ---------------------------------------------------------------------------
// List & GICS Tree
// ---------------------------------------------------------------------------

export function useIndustryList() {
  return useQuery({
    queryKey: ['industry', 'list'],
    queryFn: () => api.get(INDUSTRY.list),
    staleTime: STALE_24H,
  });
}

export function useGicsTree() {
  return useQuery({
    queryKey: ['industry', 'gicsTree'],
    queryFn: () => api.get(INDUSTRY.gicsTree),
    staleTime: STALE_24H,
  });
}
