// =============================================================================
// Securities — React Query Hooks
// =============================================================================

import { useQuery, useQueryClient, useMutation } from '@tanstack/react-query';
import { api } from '../client';
import { SECURITIES } from '../endpoints';

export function useSecurities(params?: Record<string, string | number | boolean | undefined>) {
  return useQuery({
    queryKey: ['securities', 'list', params],
    queryFn: () => api.get(SECURITIES.list, params),
    staleTime: 24 * 60 * 60 * 1000,
  });
}

export function useSecurity(id: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['securities', 'detail', id],
    queryFn: () => api.get(SECURITIES.detail(id)),
    enabled: options?.enabled ?? !!id,
    staleTime: 24 * 60 * 60 * 1000,
  });
}

export function useSecuritySearch(query: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['securities', 'search', query],
    queryFn: () => api.get(SECURITIES.search, { q: query }),
    enabled: options?.enabled ?? !!query,
    staleTime: 24 * 60 * 60 * 1000,
  });
}

export function useSecurityFind(query: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['securities', 'find', query],
    queryFn: () => api.get(SECURITIES.find, { q: query }),
    enabled: options?.enabled ?? !!query,
    staleTime: 24 * 60 * 60 * 1000,
  });
}

export function useSecurityPrices(
  id: string,
  params?: Record<string, string | number | boolean | undefined>,
  options?: { enabled?: boolean },
) {
  return useQuery({
    queryKey: ['securities', 'prices', id, params],
    queryFn: () => api.get(SECURITIES.prices(id), params),
    enabled: options?.enabled ?? !!id,
    staleTime: 5 * 60 * 1000, // 5 min — price data
  });
}

export function useSecurityPricesIntraday(id: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['securities', 'pricesIntraday', id],
    queryFn: () => api.get(SECURITIES.pricesIntraday(id)),
    enabled: options?.enabled ?? !!id,
    staleTime: 30 * 1000, // 30s — intraday
  });
}

export function useSecurityPricesHistory(
  id: string,
  params?: Record<string, string | number | boolean | undefined>,
  options?: { enabled?: boolean },
) {
  return useQuery({
    queryKey: ['securities', 'pricesHistory', id, params],
    queryFn: () => api.get(SECURITIES.pricesHistory(id), params),
    enabled: options?.enabled ?? !!id,
    staleTime: 24 * 60 * 60 * 1000,
  });
}

export function useSecurityBulkLookup(symbols: string[], options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['securities', 'bulkLookup', symbols],
    queryFn: () => api.post(SECURITIES.bulkLookup, { symbols }),
    enabled: options?.enabled ?? symbols.length > 0,
    staleTime: 24 * 60 * 60 * 1000,
  });
}

export function useSecurityTranslate() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Record<string, unknown>) => api.post(SECURITIES.translate, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['securities'] });
    },
  });
}

export function useInstitutionalHoldings(id: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['securities', 'institutionalHoldings', id],
    queryFn: () => api.get(SECURITIES.institutionalHoldings(id)),
    enabled: options?.enabled ?? !!id,
    staleTime: 24 * 60 * 60 * 1000,
  });
}

export function useInsiderHoldings(id: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['securities', 'insiderHoldings', id],
    queryFn: () => api.get(SECURITIES.insiderHoldings(id)),
    enabled: options?.enabled ?? !!id,
    staleTime: 24 * 60 * 60 * 1000,
  });
}

export function useOwnershipSummary(id: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['securities', 'ownershipSummary', id],
    queryFn: () => api.get(SECURITIES.ownershipSummary(id)),
    enabled: options?.enabled ?? !!id,
    staleTime: 24 * 60 * 60 * 1000,
  });
}

export function useShortInterest(id: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['securities', 'shortInterest', id],
    queryFn: () => api.get(SECURITIES.shortInterest(id)),
    enabled: options?.enabled ?? !!id,
    staleTime: 24 * 60 * 60 * 1000,
  });
}

export function useTechnicals(id: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['securities', 'technicals', id],
    queryFn: () => api.get(SECURITIES.technicals(id)),
    enabled: options?.enabled ?? !!id,
    staleTime: 5 * 60 * 1000,
  });
}

export function useDividends(id: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['securities', 'dividends', id],
    queryFn: () => api.get(SECURITIES.dividends(id)),
    enabled: options?.enabled ?? !!id,
    staleTime: 24 * 60 * 60 * 1000,
  });
}

export function useSplits(id: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['securities', 'splits', id],
    queryFn: () => api.get(SECURITIES.splits(id)),
    enabled: options?.enabled ?? !!id,
    staleTime: 24 * 60 * 60 * 1000,
  });
}

export function useCorporateActions(id: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['securities', 'corporateActions', id],
    queryFn: () => api.get(SECURITIES.corporateActions(id)),
    enabled: options?.enabled ?? !!id,
    staleTime: 24 * 60 * 60 * 1000,
  });
}

export function useSecurityIdentifiers(id: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['securities', 'identifiers', id],
    queryFn: () => api.get(SECURITIES.identifiers(id)),
    enabled: options?.enabled ?? !!id,
    staleTime: 24 * 60 * 60 * 1000,
  });
}

export function useExchanges() {
  return useQuery({
    queryKey: ['securities', 'exchanges'],
    queryFn: () => api.get(SECURITIES.exchanges),
    staleTime: 24 * 60 * 60 * 1000,
  });
}

export function useSectors() {
  return useQuery({
    queryKey: ['securities', 'sectors'],
    queryFn: () => api.get(SECURITIES.sectors),
    staleTime: 24 * 60 * 60 * 1000,
  });
}
