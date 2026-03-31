// =============================================================================
// Ownership & Flows — React Query Hooks
// =============================================================================

import { useQuery } from '@tanstack/react-query';
import { api } from '../client';
import { FLOWS } from '../endpoints';

const STALE_24H = 24 * 60 * 60 * 1000;
const STALE_5MIN = 5 * 60 * 1000;

export function useInstitutionalFlows(params?: Record<string, string | number | boolean | undefined>) {
  return useQuery({
    queryKey: ['flows', 'institutional', params],
    queryFn: () => api.get(FLOWS.institutional, params),
    staleTime: STALE_24H,
  });
}

export function useInstitutionalDetail(fundId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['flows', 'institutionalDetail', fundId],
    queryFn: () => api.get(FLOWS.institutionalDetail(fundId)),
    enabled: options?.enabled ?? !!fundId,
    staleTime: STALE_24H,
  });
}

export function useSectorFlows() {
  return useQuery({
    queryKey: ['flows', 'sectors'],
    queryFn: () => api.get(FLOWS.sectors),
    staleTime: STALE_24H,
  });
}

export function useStyleFlows() {
  return useQuery({
    queryKey: ['flows', 'styles'],
    queryFn: () => api.get(FLOWS.styles),
    staleTime: STALE_24H,
  });
}

export function useEtfFlows() {
  return useQuery({
    queryKey: ['flows', 'etf'],
    queryFn: () => api.get(FLOWS.etf),
    staleTime: STALE_24H,
  });
}

export function useEtfFlowDetail(etfId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['flows', 'etfDetail', etfId],
    queryFn: () => api.get(FLOWS.etfDetail(etfId)),
    enabled: options?.enabled ?? !!etfId,
    staleTime: STALE_24H,
  });
}

export function useMutualFundFlows() {
  return useQuery({
    queryKey: ['flows', 'mutualFund'],
    queryFn: () => api.get(FLOWS.mutualFund),
    staleTime: STALE_24H,
  });
}

export function useMutualFundFlowDetail(fundId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['flows', 'mutualFundDetail', fundId],
    queryFn: () => api.get(FLOWS.mutualFundDetail(fundId)),
    enabled: options?.enabled ?? !!fundId,
    staleTime: STALE_24H,
  });
}

export function useWhaleAlerts() {
  return useQuery({
    queryKey: ['flows', 'whaleAlerts'],
    queryFn: () => api.get(FLOWS.whaleAlerts),
    staleTime: STALE_5MIN,
  });
}

export function useActivistActivity() {
  return useQuery({
    queryKey: ['flows', 'activistActivity'],
    queryFn: () => api.get(FLOWS.activistActivity),
    staleTime: STALE_5MIN,
  });
}

export function useDarkPoolFlows() {
  return useQuery({
    queryKey: ['flows', 'darkPool'],
    queryFn: () => api.get(FLOWS.darkPool),
    staleTime: STALE_24H,
  });
}

export function useOptionsFlow() {
  return useQuery({
    queryKey: ['flows', 'optionsFlow'],
    queryFn: () => api.get(FLOWS.optionsFlow),
    staleTime: STALE_24H,
  });
}

export function useInsiderFlow() {
  return useQuery({
    queryKey: ['flows', 'insiderFlow'],
    queryFn: () => api.get(FLOWS.insiderFlow),
    staleTime: STALE_24H,
  });
}

export function useForeignFlow() {
  return useQuery({
    queryKey: ['flows', 'foreignFlow'],
    queryFn: () => api.get(FLOWS.foreignFlow),
    staleTime: STALE_24H,
  });
}

export function useRetailFlow() {
  return useQuery({
    queryKey: ['flows', 'retailFlow'],
    queryFn: () => api.get(FLOWS.retailFlow),
    staleTime: STALE_24H,
  });
}
