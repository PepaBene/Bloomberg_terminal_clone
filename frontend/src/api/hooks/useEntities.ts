// =============================================================================
// Entities — React Query Hooks
// =============================================================================

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../client';
import { ENTITIES } from '../endpoints';

export function useEntities(params?: Record<string, string | number | boolean | undefined>) {
  return useQuery({
    queryKey: ['entities', 'list', params],
    queryFn: () => api.get(ENTITIES.list, params),
    staleTime: 24 * 60 * 60 * 1000,
  });
}

export function useEntity(id: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['entities', 'detail', id],
    queryFn: () => api.get(ENTITIES.detail(id)),
    enabled: options?.enabled ?? !!id,
    staleTime: 24 * 60 * 60 * 1000,
  });
}

export function useEntitySearch(query: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['entities', 'search', query],
    queryFn: () => api.get(ENTITIES.search, { q: query }),
    enabled: options?.enabled ?? !!query,
    staleTime: 24 * 60 * 60 * 1000,
  });
}

export function useCreateEntity() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Record<string, unknown>) => api.post(ENTITIES.create, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['entities', 'list'] });
      qc.invalidateQueries({ queryKey: ['entities', 'detail'] });
    },
  });
}

export function useUpdateEntity() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...body }: Record<string, unknown> & { id: string }) =>
      api.put(ENTITIES.update(id), body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['entities', 'list'] });
      qc.invalidateQueries({ queryKey: ['entities', 'detail'] });
    },
  });
}

export function useDeleteEntity() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.delete(ENTITIES.delete(id)),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['entities', 'list'] });
    },
  });
}

export function useEntityRelationships(id: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['entities', 'relationships', id],
    queryFn: () => api.get(ENTITIES.relationships(id)),
    enabled: options?.enabled ?? !!id,
    staleTime: 24 * 60 * 60 * 1000,
  });
}

export function useEntitySubsidiaries(id: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['entities', 'subsidiaries', id],
    queryFn: () => api.get(ENTITIES.subsidiaries(id)),
    enabled: options?.enabled ?? !!id,
    staleTime: 24 * 60 * 60 * 1000,
  });
}

export function useEntityParentChain(id: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['entities', 'parentChain', id],
    queryFn: () => api.get(ENTITIES.parentChain(id)),
    enabled: options?.enabled ?? !!id,
    staleTime: 24 * 60 * 60 * 1000,
  });
}

export function useEntityOfficers(id: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['entities', 'officers', id],
    queryFn: () => api.get(ENTITIES.officers(id)),
    enabled: options?.enabled ?? !!id,
    staleTime: 24 * 60 * 60 * 1000,
  });
}

export function useEntityBoardMembers(id: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['entities', 'boardMembers', id],
    queryFn: () => api.get(ENTITIES.boardMembers(id)),
    enabled: options?.enabled ?? !!id,
    staleTime: 24 * 60 * 60 * 1000,
  });
}

export function useEntityHistory(id: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['entities', 'history', id],
    queryFn: () => api.get(ENTITIES.history(id)),
    enabled: options?.enabled ?? !!id,
    staleTime: 24 * 60 * 60 * 1000,
  });
}

export function useEntityIdentifiers(id: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['entities', 'identifiers', id],
    queryFn: () => api.get(ENTITIES.identifiers(id)),
    enabled: options?.enabled ?? !!id,
    staleTime: 24 * 60 * 60 * 1000,
  });
}

export function useEntityClassifications(id: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['entities', 'classifications', id],
    queryFn: () => api.get(ENTITIES.classifications(id)),
    enabled: options?.enabled ?? !!id,
    staleTime: 24 * 60 * 60 * 1000,
  });
}
