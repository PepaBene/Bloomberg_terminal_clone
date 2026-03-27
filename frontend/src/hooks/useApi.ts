import { useQuery, useMutation, useQueryClient, type UseQueryOptions } from '@tanstack/react-query';
import api from '@/api/client';

// Generic GET hook with fallback to mock data
export function useApiQuery<T>(
  key: (string | number | undefined)[],
  path: string,
  params?: Record<string, string | number | boolean | undefined>,
  options?: Partial<UseQueryOptions<T>>
) {
  return useQuery<T>({
    queryKey: key,
    queryFn: () => api.get<T>(path, params),
    retry: 1,
    ...options,
  });
}

// Generic POST mutation
export function useApiMutation<TData, TBody = unknown>(
  path: string,
  invalidateKeys?: string[][]
) {
  const queryClient = useQueryClient();
  return useMutation<TData, Error, TBody>({
    mutationFn: (body) => api.post<TData>(path, body),
    onSuccess: () => {
      invalidateKeys?.forEach(key => queryClient.invalidateQueries({ queryKey: key }));
    },
  });
}

// Generic PUT mutation
export function useApiUpdate<TData, TBody = unknown>(
  pathFn: (id: string) => string,
  invalidateKeys?: string[][]
) {
  const queryClient = useQueryClient();
  return useMutation<TData, Error, { id: string; body: TBody }>({
    mutationFn: ({ id, body }) => api.put<TData>(pathFn(id), body),
    onSuccess: () => {
      invalidateKeys?.forEach(key => queryClient.invalidateQueries({ queryKey: key }));
    },
  });
}

// Generic DELETE mutation
export function useApiDelete(
  pathFn: (id: string) => string,
  invalidateKeys?: string[][]
) {
  const queryClient = useQueryClient();
  return useMutation<void, Error, string>({
    mutationFn: (id) => api.delete(pathFn(id)),
    onSuccess: () => {
      invalidateKeys?.forEach(key => queryClient.invalidateQueries({ queryKey: key }));
    },
  });
}
