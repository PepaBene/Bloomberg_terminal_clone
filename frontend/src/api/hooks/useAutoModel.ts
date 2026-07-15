// =============================================================================
// Automatic Model Builder — React Query Hooks
// Wraps /v1/models/* endpoints (src/api/routers/auto_model.py).
// =============================================================================

import { useQuery, useMutation } from '@tanstack/react-query';
import { api } from '../client';
import { AUTO_MODEL } from '../endpoints';

const STALE_1H = 60 * 60 * 1000;

export function useModelScopes() {
  return useQuery({
    queryKey: ['autoModel', 'scopes'],
    queryFn: () => api.get<{ scopes: string[] }>(AUTO_MODEL.scopes),
    staleTime: STALE_1H,
  });
}

// GET /v1/models/company/{entityId} -- auto-assembled from real fundamentals,
// DCF/comps, and Piotroski/Altman scores on file for the entity.
export function useCompanyModel(entityId: string | undefined, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['autoModel', 'company', entityId],
    queryFn: () => api.get(AUTO_MODEL.company(entityId as string)),
    enabled: options?.enabled ?? !!entityId,
    staleTime: STALE_1H,
  });
}

// POST /v1/models/build -- caller-supplied metrics for any scope.
export function useBuildModel() {
  return useMutation({
    mutationFn: (body: { scope: string; subject?: string; data: Record<string, unknown> }) =>
      api.post(AUTO_MODEL.build, body),
  });
}
