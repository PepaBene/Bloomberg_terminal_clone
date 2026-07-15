// =============================================================================
// Auth — React Query Hooks
// =============================================================================

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../client';
import { AUTH } from '../endpoints';
import { useAuthStore } from '@/stores/authStore';

const STALE_5M = 5 * 60 * 1000;

// ---------------------------------------------------------------------------
// Register / Login / Logout / Me
//
// Real backend surface (src/api/routers/auth.py) is JWT-only: POST
// /auth/register, POST /auth/token (OAuth2 password flow, form-encoded),
// GET /auth/me. There is no session to refresh and no server-side logout
// (a JWT can't be revoked without a blocklist this backend doesn't have)
// -- "logout" is purely local: drop the token.
// ---------------------------------------------------------------------------

interface TokenResponse {
  access_token: string;
  token_type: string;
}

interface MeResponse {
  sub: string;
  role: string;
}

export function useLogin() {
  const setSession = useAuthStore((s) => s.setSession);
  return useMutation({
    mutationFn: async (body: { username: string; password: string }) => {
      const token = await api.postForm<TokenResponse>(AUTH.login, body);
      // /auth/token's response has no role -- api.setToken() here (before
      // the /auth/me call) so that request actually carries the new
      // Bearer token; fetch the real role rather than guessing one.
      api.setToken(token.access_token);
      const me = await api.get<MeResponse>(AUTH.me);
      return { token, me };
    },
    onSuccess: ({ token, me }) => {
      setSession(token.access_token, me.sub, me.role);
    },
    onError: () => {
      api.setToken(null);
    },
  });
}

export function useRegister() {
  return useMutation({
    mutationFn: (body: { username: string; email: string; password: string; full_name?: string }) =>
      api.post<{ user_id: string; username: string; email: string; role: string }>(AUTH.register, body),
  });
}

export function useMe(options?: { enabled?: boolean }) {
  const token = useAuthStore((s) => s.token);
  return useQuery({
    queryKey: ['auth', 'me'],
    queryFn: () => api.get<MeResponse>(AUTH.me),
    enabled: (options?.enabled ?? true) && !!token,
    staleTime: STALE_5M,
    retry: false,
  });
}

export function useLogout() {
  const qc = useQueryClient();
  const clearSession = useAuthStore((s) => s.clearSession);
  return () => {
    api.setToken(null);
    clearSession();
    qc.invalidateQueries({ queryKey: ['auth'] });
  };
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
