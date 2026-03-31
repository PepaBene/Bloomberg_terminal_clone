// =============================================================================
// ESG — React Query Hooks
// =============================================================================

import { useQuery } from '@tanstack/react-query';
import { api } from '../client';
import { GOVERNANCE } from '../endpoints';

const STALE_24H = 24 * 60 * 60 * 1000;

export function useEsg(entityId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['esg', 'detail', entityId],
    queryFn: () => api.get(GOVERNANCE.esg(entityId)),
    enabled: options?.enabled ?? !!entityId,
    staleTime: STALE_24H,
  });
}

export function useEsgScores(entityId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['esg', 'scores', entityId],
    queryFn: () => api.get(GOVERNANCE.esgScores(entityId)),
    enabled: options?.enabled ?? !!entityId,
    staleTime: STALE_24H,
  });
}

export function useEsgHistory(entityId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['esg', 'history', entityId],
    queryFn: () => api.get(GOVERNANCE.esgHistory(entityId)),
    enabled: options?.enabled ?? !!entityId,
    staleTime: STALE_24H,
  });
}
