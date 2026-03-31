// =============================================================================
// Earnings Domain — React Query Hooks
// Wraps /v3/earnings endpoints for earnings analysis
// =============================================================================

import { useQuery } from '@tanstack/react-query';
import { api } from '../client';
import { EARNINGS } from '../endpoints';

const STALE_24H = 24 * 60 * 60 * 1000;

// ---------------------------------------------------------------------------
// Transcripts
// ---------------------------------------------------------------------------

export function useTranscripts(entityId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['earnings', 'transcripts', entityId],
    queryFn: () => api.get(EARNINGS.transcripts(entityId)),
    enabled: options?.enabled ?? !!entityId,
    staleTime: STALE_24H,
  });
}

export function useTranscriptDetail(entityId: string, transcriptId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['earnings', 'transcriptDetail', entityId, transcriptId],
    queryFn: () => api.get(EARNINGS.transcriptDetail(entityId, transcriptId)),
    enabled: options?.enabled ?? !!(entityId && transcriptId),
    staleTime: STALE_24H,
  });
}

// ---------------------------------------------------------------------------
// Surprises & Guidance
// ---------------------------------------------------------------------------

export function useEarningsSurprises(entityId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['earnings', 'surprises', entityId],
    queryFn: () => api.get(EARNINGS.surprises(entityId)),
    enabled: options?.enabled ?? !!entityId,
    staleTime: STALE_24H,
  });
}

export function useEarningsGuidance(entityId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['earnings', 'guidance', entityId],
    queryFn: () => api.get(EARNINGS.guidance(entityId)),
    enabled: options?.enabled ?? !!entityId,
    staleTime: STALE_24H,
  });
}

// ---------------------------------------------------------------------------
// Calendar
// ---------------------------------------------------------------------------

export function useEarningsCalendar() {
  return useQuery({
    queryKey: ['earnings', 'calendar'],
    queryFn: () => api.get(EARNINGS.calendar),
    staleTime: STALE_24H,
  });
}

export function useEarningsCalendarByDate(date: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['earnings', 'calendarByDate', date],
    queryFn: () => api.get(EARNINGS.calendarByDate(date)),
    enabled: options?.enabled ?? !!date,
    staleTime: STALE_24H,
  });
}

// ---------------------------------------------------------------------------
// Estimates & Revisions
// ---------------------------------------------------------------------------

export function useEarningsEstimates(entityId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['earnings', 'estimates', entityId],
    queryFn: () => api.get(EARNINGS.estimates(entityId)),
    enabled: options?.enabled ?? !!entityId,
    staleTime: STALE_24H,
  });
}

export function useEarningsRevisions(entityId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['earnings', 'revisions', entityId],
    queryFn: () => api.get(EARNINGS.revisions(entityId)),
    enabled: options?.enabled ?? !!entityId,
    staleTime: STALE_24H,
  });
}

// ---------------------------------------------------------------------------
// Quality & Seasonality
// ---------------------------------------------------------------------------

export function useEarningsQuality(entityId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['earnings', 'quality', entityId],
    queryFn: () => api.get(EARNINGS.quality(entityId)),
    enabled: options?.enabled ?? !!entityId,
    staleTime: STALE_24H,
  });
}

export function useEarningsSeasonality(entityId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['earnings', 'seasonality', entityId],
    queryFn: () => api.get(EARNINGS.seasonality(entityId)),
    enabled: options?.enabled ?? !!entityId,
    staleTime: STALE_24H,
  });
}
