// =============================================================================
// Deals (M&A) — React Query Hooks
// =============================================================================

import { useQuery, useMutation } from '@tanstack/react-query';
import { api } from '../client';
import { DEALS } from '../endpoints';

const STALE_1H = 60 * 60 * 1000;

// ---------------------------------------------------------------------------
// List / Detail
// ---------------------------------------------------------------------------

export function useDeals(params?: Record<string, string | number | boolean | undefined>) {
  return useQuery({
    queryKey: ['deals', 'list', params],
    queryFn: () => api.get(DEALS.list, params),
    staleTime: STALE_1H,
  });
}

export function useDealDetail(dealId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['deals', 'detail', dealId],
    queryFn: () => api.get(DEALS.detail(dealId)),
    enabled: options?.enabled ?? !!dealId,
    staleTime: STALE_1H,
  });
}

// ---------------------------------------------------------------------------
// Search — mutation (POST)
// ---------------------------------------------------------------------------

export function useDealSearch() {
  return useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      api.post(DEALS.search, body),
  });
}

// ---------------------------------------------------------------------------
// By Entity
// ---------------------------------------------------------------------------

export function useEntityDeals(entityId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['deals', 'entity', entityId],
    queryFn: () => api.get(DEALS.byEntity(entityId)),
    enabled: options?.enabled ?? !!entityId,
    staleTime: STALE_1H,
  });
}

// ---------------------------------------------------------------------------
// Pipeline / Completed / Rumored / Statistics
// ---------------------------------------------------------------------------

export function useDealPipeline(options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['deals', 'pipeline'],
    queryFn: () => api.get(DEALS.pipeline),
    enabled: options?.enabled ?? true,
    staleTime: STALE_1H,
  });
}

export function useCompletedDeals(options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['deals', 'completed'],
    queryFn: () => api.get(DEALS.completed),
    enabled: options?.enabled ?? true,
    staleTime: STALE_1H,
  });
}

export function useRumoredDeals(options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['deals', 'rumored'],
    queryFn: () => api.get(DEALS.rumored),
    enabled: options?.enabled ?? true,
    staleTime: STALE_1H,
  });
}

export function useDealStatistics(options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['deals', 'statistics'],
    queryFn: () => api.get(DEALS.statistics),
    enabled: options?.enabled ?? true,
    staleTime: STALE_1H,
  });
}

// ---------------------------------------------------------------------------
// Advisors / Timeline
// ---------------------------------------------------------------------------

export function useDealAdvisors(dealId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['deals', dealId, 'advisors'],
    queryFn: () => api.get(DEALS.advisors(dealId)),
    enabled: options?.enabled ?? !!dealId,
    staleTime: STALE_1H,
  });
}

export function useDealTimeline(dealId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['deals', dealId, 'timeline'],
    queryFn: () => api.get(DEALS.timeline(dealId)),
    enabled: options?.enabled ?? !!dealId,
    staleTime: STALE_1H,
  });
}
