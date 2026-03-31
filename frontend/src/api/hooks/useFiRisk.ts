// =============================================================================
// Fixed Income — Risk Analytics — React Query Hooks
// =============================================================================

import { useMutation } from '@tanstack/react-query';
import { api } from '../client';
import { FI } from '../endpoints';

export function useDurationAnalysis() {
  return useMutation({
    mutationFn: (body: Record<string, unknown>) => api.post(FI.analytics.duration, body),
  });
}

export function useKeyRateDuration() {
  return useMutation({
    mutationFn: (body: Record<string, unknown>) => api.post(FI.analytics.keyRate, body),
  });
}

export function useConvexityAnalysis() {
  return useMutation({
    mutationFn: (body: Record<string, unknown>) => api.post(FI.analytics.convexity, body),
  });
}

export function useRollDownAnalysis() {
  return useMutation({
    mutationFn: (body: Record<string, unknown>) => api.post(FI.analytics.rollDown, body),
  });
}

export function useTotalReturnScenario() {
  return useMutation({
    mutationFn: (body: Record<string, unknown>) => api.post(FI.analytics.scenario, body),
  });
}
