// =============================================================================
// Analytics Domain — React Query Hooks
// Wraps /v2/analytics endpoints for security-level analysis
// =============================================================================

import { useQuery, useMutation } from '@tanstack/react-query';
import { api } from '../client';
import { ANALYTICS } from '../endpoints';

const STALE_24H = 24 * 60 * 60 * 1000;

// ---------------------------------------------------------------------------
// Ratios & Scores
// ---------------------------------------------------------------------------

export function useAnalyticsRatios(secId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['analytics', 'ratios', secId],
    queryFn: () => api.get(ANALYTICS.ratios(secId)),
    enabled: options?.enabled ?? !!secId,
    staleTime: STALE_24H,
  });
}

export function useCompositeScores(secId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['analytics', 'compositeScores', secId],
    queryFn: () => api.get(ANALYTICS.compositeScores(secId)),
    enabled: options?.enabled ?? !!secId,
    staleTime: STALE_24H,
  });
}

export function useAllScores(secId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['analytics', 'allScores', secId],
    queryFn: () => api.get(ANALYTICS.allScores(secId)),
    enabled: options?.enabled ?? !!secId,
    staleTime: STALE_24H,
  });
}

export function useQualityScore(secId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['analytics', 'qualityScore', secId],
    queryFn: () => api.get(ANALYTICS.qualityScore(secId)),
    enabled: options?.enabled ?? !!secId,
    staleTime: STALE_24H,
  });
}

export function useValueScore(secId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['analytics', 'valueScore', secId],
    queryFn: () => api.get(ANALYTICS.valueScore(secId)),
    enabled: options?.enabled ?? !!secId,
    staleTime: STALE_24H,
  });
}

export function useGrowthScore(secId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['analytics', 'growthScore', secId],
    queryFn: () => api.get(ANALYTICS.growthScore(secId)),
    enabled: options?.enabled ?? !!secId,
    staleTime: STALE_24H,
  });
}

export function useMomentumScore(secId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['analytics', 'momentumScore', secId],
    queryFn: () => api.get(ANALYTICS.momentumScore(secId)),
    enabled: options?.enabled ?? !!secId,
    staleTime: STALE_24H,
  });
}

export function useVolatilityScore(secId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['analytics', 'volatilityScore', secId],
    queryFn: () => api.get(ANALYTICS.volatilityScore(secId)),
    enabled: options?.enabled ?? !!secId,
    staleTime: STALE_24H,
  });
}

// ---------------------------------------------------------------------------
// DuPont Analysis
// ---------------------------------------------------------------------------

export function useDupont(secId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['analytics', 'dupont', secId],
    queryFn: () => api.get(ANALYTICS.dupont(secId)),
    enabled: options?.enabled ?? !!secId,
    staleTime: STALE_24H,
  });
}

export function useDupontHistory(secId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['analytics', 'dupontHistory', secId],
    queryFn: () => api.get(ANALYTICS.dupontHistory(secId)),
    enabled: options?.enabled ?? !!secId,
    staleTime: STALE_24H,
  });
}

// ---------------------------------------------------------------------------
// Multiples & Valuation
// ---------------------------------------------------------------------------

export function useMultiplesHistory(secId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['analytics', 'multiplesHistory', secId],
    queryFn: () => api.get(ANALYTICS.multiplesHistory(secId)),
    enabled: options?.enabled ?? !!secId,
    staleTime: STALE_24H,
  });
}

export function useHistoricalMultiples(secId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['analytics', 'historicalMultiples', secId],
    queryFn: () => api.get(ANALYTICS.historicalMultiples(secId)),
    enabled: options?.enabled ?? !!secId,
    staleTime: STALE_24H,
  });
}

export function useFairValue(secId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['analytics', 'fairValue', secId],
    queryFn: () => api.get(ANALYTICS.fairValue(secId)),
    enabled: options?.enabled ?? !!secId,
    staleTime: STALE_24H,
  });
}

export function useFootballField(secId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['analytics', 'footballField', secId],
    queryFn: () => api.get(ANALYTICS.footballField(secId)),
    enabled: options?.enabled ?? !!secId,
    staleTime: STALE_24H,
  });
}

// ---------------------------------------------------------------------------
// Peer Analysis
// ---------------------------------------------------------------------------

export function usePeerGroup(secId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['analytics', 'peerGroup', secId],
    queryFn: () => api.get(ANALYTICS.peerGroup(secId)),
    enabled: options?.enabled ?? !!secId,
    staleTime: STALE_24H,
  });
}

export function usePeerComparison(secId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['analytics', 'peerComparison', secId],
    queryFn: () => api.get(ANALYTICS.peerComparison(secId)),
    enabled: options?.enabled ?? !!secId,
    staleTime: STALE_24H,
  });
}

export function usePeerRanking(secId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['analytics', 'peerRanking', secId],
    queryFn: () => api.get(ANALYTICS.peerRanking(secId)),
    enabled: options?.enabled ?? !!secId,
    staleTime: STALE_24H,
  });
}

// ---------------------------------------------------------------------------
// Sector & Relative
// ---------------------------------------------------------------------------

export function useSectorRelative(secId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['analytics', 'sectorRelative', secId],
    queryFn: () => api.get(ANALYTICS.sectorRelative(secId)),
    enabled: options?.enabled ?? !!secId,
    staleTime: STALE_24H,
  });
}

// ---------------------------------------------------------------------------
// DCF — staleTime: 0 (always fresh, on-demand computation)
// ---------------------------------------------------------------------------

export function useDcf(secId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['analytics', 'dcf', secId],
    queryFn: () => api.get(ANALYTICS.dcf(secId)),
    enabled: options?.enabled ?? !!secId,
    staleTime: 0,
  });
}

export function useDcfSensitivity(secId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['analytics', 'dcfSensitivity', secId],
    queryFn: () => api.get(ANALYTICS.dcfSensitivity(secId)),
    enabled: options?.enabled ?? !!secId,
    staleTime: 0,
  });
}

// ---------------------------------------------------------------------------
// Technical & Seasonality
// ---------------------------------------------------------------------------

export function useTechnicalSignals(secId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['analytics', 'technicalSignals', secId],
    queryFn: () => api.get(ANALYTICS.technicalSignals(secId)),
    enabled: options?.enabled ?? !!secId,
    staleTime: STALE_24H,
  });
}

export function useSeasonality(secId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['analytics', 'seasonality', secId],
    queryFn: () => api.get(ANALYTICS.seasonality(secId)),
    enabled: options?.enabled ?? !!secId,
    staleTime: STALE_24H,
  });
}

// ---------------------------------------------------------------------------
// Factor Exposure
// ---------------------------------------------------------------------------

export function useFactorExposure(secId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['analytics', 'factorExposure', secId],
    queryFn: () => api.get(ANALYTICS.factorExposure(secId)),
    enabled: options?.enabled ?? !!secId,
    staleTime: STALE_24H,
  });
}

// ---------------------------------------------------------------------------
// Correlation — POST mutation
// ---------------------------------------------------------------------------

export function useCorrelation() {
  return useMutation({
    mutationFn: (params: Record<string, unknown>) =>
      api.post(ANALYTICS.correlation, params),
  });
}
