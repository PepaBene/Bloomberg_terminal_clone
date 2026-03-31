// =============================================================================
// Macro Economics — React Query Hooks
// =============================================================================

import { useQuery } from '@tanstack/react-query';
import { api } from '../client';
import { MACRO } from '../endpoints';

const STALE_1H = 60 * 60 * 1000;

export function useMacroIndicators() {
  return useQuery({
    queryKey: ['macro', 'indicators'],
    queryFn: () => api.get(MACRO.indicators),
    staleTime: STALE_1H,
  });
}

export function useMacroIndicator(id: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['macro', 'indicatorDetail', id],
    queryFn: () => api.get(MACRO.indicatorDetail(id)),
    enabled: options?.enabled ?? !!id,
    staleTime: STALE_1H,
  });
}

export function useMacroIndicatorHistory(id: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['macro', 'indicatorHistory', id],
    queryFn: () => api.get(MACRO.indicatorHistory(id)),
    enabled: options?.enabled ?? !!id,
    staleTime: STALE_1H,
  });
}

export function useGdp() {
  return useQuery({
    queryKey: ['macro', 'gdp'],
    queryFn: () => api.get(MACRO.gdp),
    staleTime: STALE_1H,
  });
}

export function useGdpByCountry(code: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['macro', 'gdp', code],
    queryFn: () => api.get(MACRO.gdpByCountry(code)),
    enabled: options?.enabled ?? !!code,
    staleTime: STALE_1H,
  });
}

export function useInflation() {
  return useQuery({
    queryKey: ['macro', 'inflation'],
    queryFn: () => api.get(MACRO.inflation),
    staleTime: STALE_1H,
  });
}

export function useInflationByCountry(code: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['macro', 'inflation', code],
    queryFn: () => api.get(MACRO.inflationByCountry(code)),
    enabled: options?.enabled ?? !!code,
    staleTime: STALE_1H,
  });
}

export function useEmployment() {
  return useQuery({
    queryKey: ['macro', 'employment'],
    queryFn: () => api.get(MACRO.employment),
    staleTime: STALE_1H,
  });
}

export function useEmploymentByCountry(code: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['macro', 'employment', code],
    queryFn: () => api.get(MACRO.employmentByCountry(code)),
    enabled: options?.enabled ?? !!code,
    staleTime: STALE_1H,
  });
}

export function useMacroYieldCurve() {
  return useQuery({
    queryKey: ['macro', 'yieldCurve'],
    queryFn: () => api.get(MACRO.yieldCurve),
    staleTime: STALE_1H,
  });
}

export function usePmi() {
  return useQuery({
    queryKey: ['macro', 'pmi'],
    queryFn: () => api.get(MACRO.pmi),
    staleTime: STALE_1H,
  });
}

export function useConsumerConfidence() {
  return useQuery({
    queryKey: ['macro', 'consumerConfidence'],
    queryFn: () => api.get(MACRO.consumerConfidence),
    staleTime: STALE_1H,
  });
}

export function useHousingStarts() {
  return useQuery({
    queryKey: ['macro', 'housingStarts'],
    queryFn: () => api.get(MACRO.housingStarts),
    staleTime: STALE_1H,
  });
}

export function useRetailSales() {
  return useQuery({
    queryKey: ['macro', 'retailSales'],
    queryFn: () => api.get(MACRO.retailSales),
    staleTime: STALE_1H,
  });
}

export function useIndustrialProduction() {
  return useQuery({
    queryKey: ['macro', 'industrialProduction'],
    queryFn: () => api.get(MACRO.industrialProduction),
    staleTime: STALE_1H,
  });
}

export function useTradeBalance() {
  return useQuery({
    queryKey: ['macro', 'tradeBalance'],
    queryFn: () => api.get(MACRO.tradeBalance),
    staleTime: STALE_1H,
  });
}

export function useMoneySupply() {
  return useQuery({
    queryKey: ['macro', 'moneySupply'],
    queryFn: () => api.get(MACRO.moneySupply),
    staleTime: STALE_1H,
  });
}

export function useMacroDashboard() {
  return useQuery({
    queryKey: ['macro', 'dashboard'],
    queryFn: () => api.get(MACRO.dashboard),
    staleTime: STALE_1H,
  });
}
