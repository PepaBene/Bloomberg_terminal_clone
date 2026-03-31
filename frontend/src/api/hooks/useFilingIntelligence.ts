// =============================================================================
// Filing Intelligence Domain — React Query Hooks
// Wraps /v3/filings endpoints for SEC filing analysis
// =============================================================================

import { useQuery, useMutation } from '@tanstack/react-query';
import { api } from '../client';
import { FILING_INTELLIGENCE } from '../endpoints';

const STALE_24H = 24 * 60 * 60 * 1000;

// ---------------------------------------------------------------------------
// Filing Events
// ---------------------------------------------------------------------------

export function useFilingEvents(entityId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['filings', 'events', entityId],
    queryFn: () => api.get(FILING_INTELLIGENCE.events(entityId)),
    enabled: options?.enabled ?? !!entityId,
    staleTime: STALE_24H,
  });
}

export function useFilingEventsToday() {
  return useQuery({
    queryKey: ['filings', 'eventsToday'],
    queryFn: () => api.get(FILING_INTELLIGENCE.eventsToday),
    staleTime: STALE_24H,
  });
}

// ---------------------------------------------------------------------------
// Filing Diff & Insiders
// ---------------------------------------------------------------------------

export function useFilingDiff(entityId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['filings', 'diff', entityId],
    queryFn: () => api.get(FILING_INTELLIGENCE.diff(entityId)),
    enabled: options?.enabled ?? !!entityId,
    staleTime: STALE_24H,
  });
}

export function useInsiderFilings(entityId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['filings', 'insiders', entityId],
    queryFn: () => api.get(FILING_INTELLIGENCE.insiders(entityId)),
    enabled: options?.enabled ?? !!entityId,
    staleTime: STALE_24H,
  });
}

// ---------------------------------------------------------------------------
// Filing Detail & Summary
// ---------------------------------------------------------------------------

export function useFilingDetail(entityId: string, filingId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['filings', 'detail', entityId, filingId],
    queryFn: () => api.get(FILING_INTELLIGENCE.detail(entityId, filingId)),
    enabled: options?.enabled ?? !!(entityId && filingId),
    staleTime: STALE_24H,
  });
}

export function useFilingSummary(entityId: string, filingId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['filings', 'summary', entityId, filingId],
    queryFn: () => api.get(FILING_INTELLIGENCE.summary(entityId, filingId)),
    enabled: options?.enabled ?? !!(entityId && filingId),
    staleTime: STALE_24H,
  });
}

// ---------------------------------------------------------------------------
// Risk Factors & MD&A
// ---------------------------------------------------------------------------

export function useFilingRiskFactors(entityId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['filings', 'riskFactors', entityId],
    queryFn: () => api.get(FILING_INTELLIGENCE.riskFactors(entityId)),
    enabled: options?.enabled ?? !!entityId,
    staleTime: STALE_24H,
  });
}

export function useMdna(entityId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['filings', 'mdna', entityId],
    queryFn: () => api.get(FILING_INTELLIGENCE.mdna(entityId)),
    enabled: options?.enabled ?? !!entityId,
    staleTime: STALE_24H,
  });
}

// ---------------------------------------------------------------------------
// Search — POST mutation
// ---------------------------------------------------------------------------

export function useFilingSearch() {
  return useMutation({
    mutationFn: (query: Record<string, unknown>) =>
      api.post(FILING_INTELLIGENCE.search, query),
  });
}
