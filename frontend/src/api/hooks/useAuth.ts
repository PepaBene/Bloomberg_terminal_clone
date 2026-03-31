// =============================================================================
// Auth — React Query Hooks
// =============================================================================

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../client';
import { AUTH } from '../endpoints';

const STALE_5M = 5 * 60 * 1000;

// ---------------------------------------------------------------------------
// Login / Logout / Refresh
// ---------------------------------------------------------------------------

export function useLogin() {
  return useMutation({
    mutationFn: (body: Record<string, unknown>) => api.post(AUTH.login, body),
  });
}

export function useLogout() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.post(AUTH.logout),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['auth'] });
    },
  });
}

export function useRefreshToken() {
  return useMutation({
    mutationFn: (body?: Record<string, unknown>) => api.post(AUTH.refresh, body),
  });
}

// ---------------------------------------------------------------------------
// Profile
// ---------------------------------------------------------------------------

export function useProfile(options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['auth', 'profile'],
    queryFn: () => api.get(AUTH.profile),
    enabled: options?.enabled ?? true,
    staleTime: STALE_5M,
  });
}

export function useUpdateProfile() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Record<string, unknown>) => api.put(AUTH.updateProfile, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['auth', 'profile'] });
    },
  });
}

export function useChangePassword() {
  return useMutation({
    mutationFn: (body: Record<string, unknown>) => api.post(AUTH.changePassword, body),
  });
}

// ---------------------------------------------------------------------------
// API Keys
// ---------------------------------------------------------------------------

export function useApiKeys(options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['auth', 'apiKeys'],
    queryFn: () => api.get(AUTH.apiKeys),
    enabled: options?.enabled ?? true,
    staleTime: 0,
  });
}

export function useCreateApiKey() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Record<string, unknown>) => api.post(AUTH.createApiKey, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['auth', 'apiKeys'] });
    },
  });
}

export function useRevokeApiKey() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (keyId: string) => api.delete(AUTH.revokeApiKey(keyId)),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['auth', 'apiKeys'] });
    },
  });
}
