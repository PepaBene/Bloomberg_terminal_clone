// =============================================================================
// Fixed Income — Ratings & Credit — React Query Hooks
// =============================================================================

import { useQuery } from '@tanstack/react-query';
import { api } from '../client';
import { FI } from '../endpoints';

const STALE_24H = 24 * 60 * 60 * 1000;

// ---------------------------------------------------------------------------
// Ratings
// ---------------------------------------------------------------------------

export function useRatings(entityId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['fi', 'ratings', 'byEntity', entityId],
    queryFn: () => api.get(FI.ratings.byEntity(entityId)),
    enabled: options?.enabled ?? !!entityId,
    staleTime: STALE_24H,
  });
}

export function useRatingHistory(entityId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['fi', 'ratings', 'history', entityId],
    queryFn: () => api.get(FI.ratings.history(entityId)),
    enabled: options?.enabled ?? !!entityId,
    staleTime: STALE_24H,
  });
}

export function useRecentRatingChanges(params?: Record<string, string | number | boolean | undefined>) {
  return useQuery({
    queryKey: ['fi', 'ratings', 'recentChanges', params],
    queryFn: () => api.get(FI.ratings.recentChanges, params),
    staleTime: STALE_24H,
  });
}

export function useRatingDistribution(params?: Record<string, string | number | boolean | undefined>) {
  return useQuery({
    queryKey: ['fi', 'ratings', 'distribution', params],
    queryFn: () => api.get(FI.ratings.distribution, params),
    staleTime: STALE_24H,
  });
}

export function useRatingTransitionMatrix(params?: Record<string, string | number | boolean | undefined>) {
  return useQuery({
    queryKey: ['fi', 'ratings', 'transitionMatrix', params],
    queryFn: () => api.get(FI.ratings.transitionMatrix, params),
    staleTime: STALE_24H,
  });
}

export function useRatingOutlook(entityId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['fi', 'ratings', 'outlook', entityId],
    queryFn: () => api.get(FI.ratings.outlook(entityId)),
    enabled: options?.enabled ?? !!entityId,
    staleTime: STALE_24H,
  });
}

// ---------------------------------------------------------------------------
// Credit
// ---------------------------------------------------------------------------

export function useCreditScore(entityId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['fi', 'credit', 'score', entityId],
    queryFn: () => api.get(FI.credit.score(entityId)),
    enabled: options?.enabled ?? !!entityId,
    staleTime: STALE_24H,
  });
}

export function useCreditRatios(entityId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['fi', 'credit', 'ratios', entityId],
    queryFn: () => api.get(FI.credit.ratios(entityId)),
    enabled: options?.enabled ?? !!entityId,
    staleTime: STALE_24H,
  });
}

export function useCreditPeers(entityId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['fi', 'credit', 'peers', entityId],
    queryFn: () => api.get(FI.credit.peers(entityId)),
    enabled: options?.enabled ?? !!entityId,
    staleTime: STALE_24H,
  });
}

export function useCreditTrend(entityId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['fi', 'credit', 'trend', entityId],
    queryFn: () => api.get(FI.credit.trend(entityId)),
    enabled: options?.enabled ?? !!entityId,
    staleTime: STALE_24H,
  });
}

export function useSectorSpreads(params?: Record<string, string | number | boolean | undefined>) {
  return useQuery({
    queryKey: ['fi', 'credit', 'sectorSpreads', params],
    queryFn: () => api.get(FI.credit.sectorSpreads, params),
    staleTime: STALE_24H,
  });
}

export function useDistressedIssuers(params?: Record<string, string | number | boolean | undefined>) {
  return useQuery({
    queryKey: ['fi', 'credit', 'distressed', params],
    queryFn: () => api.get(FI.credit.distressed, params),
    staleTime: STALE_24H,
  });
}

export function useDefaultProbability(entityId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['fi', 'credit', 'defaultProbability', entityId],
    queryFn: () => api.get(FI.credit.defaultProbability(entityId)),
    enabled: options?.enabled ?? !!entityId,
    staleTime: STALE_24H,
  });
}

export function useRecoveryRate(entityId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['fi', 'credit', 'recoveryRate', entityId],
    queryFn: () => api.get(FI.credit.recoveryRate(entityId)),
    enabled: options?.enabled ?? !!entityId,
    staleTime: STALE_24H,
  });
}

export function useCds(entityId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['fi', 'credit', 'cds', entityId],
    queryFn: () => api.get(FI.credit.cds(entityId)),
    enabled: options?.enabled ?? !!entityId,
    staleTime: STALE_24H,
  });
}

export function useCdsCurve(entityId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['fi', 'credit', 'cdsCurve', entityId],
    queryFn: () => api.get(FI.credit.cdsCurve(entityId)),
    enabled: options?.enabled ?? !!entityId,
    staleTime: STALE_24H,
  });
}
