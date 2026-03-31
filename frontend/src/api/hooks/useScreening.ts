// =============================================================================
// Screening Domain — React Query Hooks
// Wraps /v2/analytics/screen endpoints for equity screening
// =============================================================================

import { useQuery, useMutation } from '@tanstack/react-query';
import { api } from '../client';
import { ANALYTICS } from '../endpoints';

const STALE_1H = 60 * 60 * 1000;

// ---------------------------------------------------------------------------
// Screen Execution — POST mutation
// ---------------------------------------------------------------------------

export function useRunScreen() {
  return useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      api.post(ANALYTICS.screen, body),
  });
}

// ---------------------------------------------------------------------------
// Screen Metadata
// ---------------------------------------------------------------------------

export function useScreenFields(options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['screening', 'fields'],
    queryFn: () => api.get(ANALYTICS.screenFields),
    enabled: options?.enabled ?? true,
    staleTime: STALE_1H,
  });
}

export function usePrebuiltScreens(options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['screening', 'prebuilt'],
    queryFn: () => api.get(ANALYTICS.screenPrebuilt),
    enabled: options?.enabled ?? true,
    staleTime: STALE_1H,
  });
}

// ---------------------------------------------------------------------------
// Screen Persistence — Save mutation
// ---------------------------------------------------------------------------

export function useSaveScreen() {
  return useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      api.post(ANALYTICS.screenSave, body),
  });
}

// ---------------------------------------------------------------------------
// Screen History
// ---------------------------------------------------------------------------

export function useScreenHistory(options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['screening', 'history'],
    queryFn: () => api.get(ANALYTICS.screenHistory),
    enabled: options?.enabled ?? true,
    staleTime: STALE_1H,
  });
}
