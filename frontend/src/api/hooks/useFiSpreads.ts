// =============================================================================
// Fixed Income — Spread Analytics — React Query Hooks
// =============================================================================

import { useQuery, useMutation } from '@tanstack/react-query';
import { api } from '../client';
import { FI } from '../endpoints';

const STALE_24H = 24 * 60 * 60 * 1000;

export function useSectorCreditSpreads(params?: Record<string, string | number | boolean | undefined>) {
  return useQuery({
    queryKey: ['fi', 'spreads', 'sectorSpreads', params],
    queryFn: () => api.get(FI.credit.sectorSpreads, params),
    staleTime: STALE_24H,
  });
}

export function useSpreadAnalysis() {
  return useMutation({
    mutationFn: (body: Record<string, unknown>) => api.post(FI.analytics.spread, body),
  });
}

export function useOasAnalysis() {
  return useMutation({
    mutationFn: (body: Record<string, unknown>) => api.post(FI.analytics.oas, body),
  });
}
