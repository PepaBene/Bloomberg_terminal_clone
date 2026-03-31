// =============================================================================
// Sentiment Domain — React Query Hooks
// Wraps /v3/sentiment endpoints for sentiment analysis
// =============================================================================

import { useQuery } from '@tanstack/react-query';
import { api } from '../client';
import { SENTIMENT } from '../endpoints';

const STALE_1H = 60 * 60 * 1000;

// ---------------------------------------------------------------------------
// Entity Sentiment
// ---------------------------------------------------------------------------

export function useSentiment(entityId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['sentiment', 'byEntity', entityId],
    queryFn: () => api.get(SENTIMENT.byEntity(entityId)),
    enabled: options?.enabled ?? !!entityId,
    staleTime: STALE_1H,
  });
}

export function useSentimentHistory(entityId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['sentiment', 'history', entityId],
    queryFn: () => api.get(SENTIMENT.history(entityId)),
    enabled: options?.enabled ?? !!entityId,
    staleTime: STALE_1H,
  });
}

export function useSentimentPeers(entityId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['sentiment', 'peers', entityId],
    queryFn: () => api.get(SENTIMENT.peers(entityId)),
    enabled: options?.enabled ?? !!entityId,
    staleTime: STALE_1H,
  });
}

export function useSentimentAnomalies(entityId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['sentiment', 'anomalies', entityId],
    queryFn: () => api.get(SENTIMENT.anomalies(entityId)),
    enabled: options?.enabled ?? !!entityId,
    staleTime: STALE_1H,
  });
}

// ---------------------------------------------------------------------------
// Social & Analyst
// ---------------------------------------------------------------------------

export function useSocialSentiment(entityId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['sentiment', 'social', entityId],
    queryFn: () => api.get(SENTIMENT.social(entityId)),
    enabled: options?.enabled ?? !!entityId,
    staleTime: STALE_1H,
  });
}

export function useAnalystConsensus(entityId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['sentiment', 'analystConsensus', entityId],
    queryFn: () => api.get(SENTIMENT.analystConsensus(entityId)),
    enabled: options?.enabled ?? !!entityId,
    staleTime: STALE_1H,
  });
}

export function usePriceTargets(entityId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['sentiment', 'priceTargets', entityId],
    queryFn: () => api.get(SENTIMENT.priceTargets(entityId)),
    enabled: options?.enabled ?? !!entityId,
    staleTime: STALE_1H,
  });
}

export function useShortInterestSentiment(entityId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['sentiment', 'shortInterestSentiment', entityId],
    queryFn: () => api.get(SENTIMENT.shortInterestSentiment(entityId)),
    enabled: options?.enabled ?? !!entityId,
    staleTime: STALE_1H,
  });
}

export function useOptionsFlowSentiment(entityId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['sentiment', 'optionsFlow', entityId],
    queryFn: () => api.get(SENTIMENT.optionsFlow(entityId)),
    enabled: options?.enabled ?? !!entityId,
    staleTime: STALE_1H,
  });
}

// ---------------------------------------------------------------------------
// Market-wide Sentiment
// ---------------------------------------------------------------------------

export function useSectorSentiment() {
  return useQuery({
    queryKey: ['sentiment', 'sectorSentiment'],
    queryFn: () => api.get(SENTIMENT.sectorSentiment),
    staleTime: STALE_1H,
  });
}

export function useMarketSentiment() {
  return useQuery({
    queryKey: ['sentiment', 'marketSentiment'],
    queryFn: () => api.get(SENTIMENT.marketSentiment),
    staleTime: STALE_1H,
  });
}
