// =============================================================================
// Complex Financial Structure Analysis — React Query Hooks
// Wraps /v1/complex-structure/* endpoints (src/api/routers/complex_structure.py).
// =============================================================================

import { useQuery, useMutation } from '@tanstack/react-query';
import { api } from '../client';
import { COMPLEX_STRUCTURE } from '../endpoints';

const STALE_1H = 60 * 60 * 1000;

// GET /v1/complex-structure/entity/{entityId} -- enriched with real stored
// data: latest capital-structure debt tranches, most-recent EX-21 subsidiary
// snapshot, and disclosed share classes (2+ required to surface a section).
export function useEntityStructure(entityId: string | undefined, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['complexStructure', 'entity', entityId],
    queryFn: () => api.get(COMPLEX_STRUCTURE.entity(entityId as string)),
    enabled: options?.enabled ?? !!entityId,
    staleTime: STALE_1H,
  });
}

// POST /v1/complex-structure/analyze -- caller-supplied payload.
export function useAnalyzeStructure() {
  return useMutation({
    mutationFn: (body: Record<string, unknown>) => api.post(COMPLEX_STRUCTURE.analyze, body),
  });
}
