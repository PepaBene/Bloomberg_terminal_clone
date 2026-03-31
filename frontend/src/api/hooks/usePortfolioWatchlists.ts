// =============================================================================
// Portfolio Watchlists — React Query Hooks
// =============================================================================

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../client';
import { WATCHLISTS } from '../endpoints';

const STALE_5M = 5 * 60 * 1000;

// ---------------------------------------------------------------------------
// List / CRUD
// ---------------------------------------------------------------------------

export function useWatchlists(params?: Record<string, string | number | boolean | undefined>) {
  return useQuery({
    queryKey: ['watchlists', 'list', params],
    queryFn: () => api.get(WATCHLISTS.list, params),
    staleTime: STALE_5M,
  });
}

export function useCreateWatchlist() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Record<string, unknown>) => api.post(WATCHLISTS.create, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['watchlists'] });
    },
  });
}

export function useWatchlist(id: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['watchlists', 'detail', id],
    queryFn: () => api.get(WATCHLISTS.detail(id)),
    enabled: options?.enabled ?? !!id,
    staleTime: STALE_5M,
  });
}

export function useUpdateWatchlist() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...body }: Record<string, unknown> & { id: string }) =>
      api.put(WATCHLISTS.update(id), body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['watchlists'] });
    },
  });
}

export function useDeleteWatchlist() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.delete(WATCHLISTS.delete(id)),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['watchlists'] });
    },
  });
}

// ---------------------------------------------------------------------------
// Items
// ---------------------------------------------------------------------------

export function useAddWatchlistItem(watchlistId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      api.post(WATCHLISTS.addItem(watchlistId), body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['watchlists', watchlistId] });
    },
  });
}

export function useRemoveWatchlistItem(watchlistId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (itemId: string) =>
      api.delete(WATCHLISTS.removeItem(watchlistId, itemId)),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['watchlists', watchlistId] });
    },
  });
}

// ---------------------------------------------------------------------------
// Alerts / Digest / Performance / Heatmap
// ---------------------------------------------------------------------------

export function useWatchlistAlerts(watchlistId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['watchlists', watchlistId, 'alerts'],
    queryFn: () => api.get(WATCHLISTS.alerts(watchlistId)),
    enabled: options?.enabled ?? !!watchlistId,
    staleTime: STALE_5M,
  });
}

export function useWatchlistDigest(watchlistId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['watchlists', watchlistId, 'digest'],
    queryFn: () => api.get(WATCHLISTS.digest(watchlistId)),
    enabled: options?.enabled ?? !!watchlistId,
    staleTime: STALE_5M,
  });
}

export function useWatchlistPerformance(watchlistId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['watchlists', watchlistId, 'performance'],
    queryFn: () => api.get(WATCHLISTS.performance(watchlistId)),
    enabled: options?.enabled ?? !!watchlistId,
    staleTime: STALE_5M,
  });
}

export function useWatchlistHeatmap(watchlistId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['watchlists', watchlistId, 'heatmap'],
    queryFn: () => api.get(WATCHLISTS.heatmap(watchlistId)),
    enabled: options?.enabled ?? !!watchlistId,
    staleTime: STALE_5M,
  });
}
