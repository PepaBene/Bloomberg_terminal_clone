// =============================================================================
// Global Intelligence Domain — React Query Hooks
// Wraps /v3/global endpoints for macro, geopolitical & commodity data
// =============================================================================

import { useQuery } from '@tanstack/react-query';
import { api } from '../client';
import { GLOBAL } from '../endpoints';

const STALE_1H = 60 * 60 * 1000;

// ---------------------------------------------------------------------------
// Countries
// ---------------------------------------------------------------------------

export function useCountries() {
  return useQuery({
    queryKey: ['global', 'countries'],
    queryFn: () => api.get(GLOBAL.countries),
    staleTime: STALE_1H,
  });
}

export function useCountryDetail(code: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['global', 'countryDetail', code],
    queryFn: () => api.get(GLOBAL.countryDetail(code)),
    enabled: options?.enabled ?? !!code,
    staleTime: STALE_1H,
  });
}

export function useCountryRisk(code: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['global', 'countryRisk', code],
    queryFn: () => api.get(GLOBAL.countryRisk(code)),
    enabled: options?.enabled ?? !!code,
    staleTime: STALE_1H,
  });
}

export function useCountryEconomics(code: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['global', 'countryEconomics', code],
    queryFn: () => api.get(GLOBAL.countryEconomics(code)),
    enabled: options?.enabled ?? !!code,
    staleTime: STALE_1H,
  });
}

// ---------------------------------------------------------------------------
// Geopolitical Events & Macro
// ---------------------------------------------------------------------------

export function useGeopoliticalEvents() {
  return useQuery({
    queryKey: ['global', 'events'],
    queryFn: () => api.get(GLOBAL.events),
    staleTime: STALE_1H,
  });
}

export function useGlobalMacroDashboard() {
  return useQuery({
    queryKey: ['global', 'macroDashboard'],
    queryFn: () => api.get(GLOBAL.macroDashboard),
    staleTime: STALE_1H,
  });
}

// ---------------------------------------------------------------------------
// Central Banks
// ---------------------------------------------------------------------------

export function useCentralBanks() {
  return useQuery({
    queryKey: ['global', 'centralBanks'],
    queryFn: () => api.get(GLOBAL.centralBanks),
    staleTime: STALE_1H,
  });
}

export function useCentralBankDetail(bankId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['global', 'centralBankDetail', bankId],
    queryFn: () => api.get(GLOBAL.centralBankDetail(bankId)),
    enabled: options?.enabled ?? !!bankId,
    staleTime: STALE_1H,
  });
}

// ---------------------------------------------------------------------------
// Inflation & Recession
// ---------------------------------------------------------------------------

export function useGlobalInflation() {
  return useQuery({
    queryKey: ['global', 'inflation'],
    queryFn: () => api.get(GLOBAL.inflation),
    staleTime: STALE_1H,
  });
}

export function useRecessionProbability() {
  return useQuery({
    queryKey: ['global', 'recessionProb'],
    queryFn: () => api.get(GLOBAL.recessionProb),
    staleTime: STALE_1H,
  });
}

// ---------------------------------------------------------------------------
// Commodities
// ---------------------------------------------------------------------------

export function useCommodities() {
  return useQuery({
    queryKey: ['global', 'commodities'],
    queryFn: () => api.get(GLOBAL.commodities),
    staleTime: STALE_1H,
  });
}

export function useCommodityDetail(symbol: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['global', 'commodityDetail', symbol],
    queryFn: () => api.get(GLOBAL.commodityDetail(symbol)),
    enabled: options?.enabled ?? !!symbol,
    staleTime: STALE_1H,
  });
}

export function useCommodityPrices(symbol: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['global', 'commodityPrices', symbol],
    queryFn: () => api.get(GLOBAL.commodityPrices(symbol)),
    enabled: options?.enabled ?? !!symbol,
    staleTime: STALE_1H,
  });
}

// ---------------------------------------------------------------------------
// Political & Trade
// ---------------------------------------------------------------------------

export function useBills() {
  return useQuery({
    queryKey: ['global', 'bills'],
    queryFn: () => api.get(GLOBAL.bills),
    staleTime: STALE_1H,
  });
}

export function useSanctions() {
  return useQuery({
    queryKey: ['global', 'sanctions'],
    queryFn: () => api.get(GLOBAL.sanctions),
    staleTime: STALE_1H,
  });
}

export function useTradeData() {
  return useQuery({
    queryKey: ['global', 'tradeData'],
    queryFn: () => api.get(GLOBAL.tradeData),
    staleTime: STALE_1H,
  });
}

// ---------------------------------------------------------------------------
// FX
// ---------------------------------------------------------------------------

export function useFxRates() {
  return useQuery({
    queryKey: ['global', 'fxRates'],
    queryFn: () => api.get(GLOBAL.fxRates),
    staleTime: STALE_1H,
  });
}

export function useFxHistory(pair: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['global', 'fxHistory', pair],
    queryFn: () => api.get(GLOBAL.fxHistory(pair)),
    enabled: options?.enabled ?? !!pair,
    staleTime: STALE_1H,
  });
}

export function useFxForward(pair: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['global', 'fxForward', pair],
    queryFn: () => api.get(GLOBAL.fxForward(pair)),
    enabled: options?.enabled ?? !!pair,
    staleTime: STALE_1H,
  });
}

// ---------------------------------------------------------------------------
// Global Indices
// ---------------------------------------------------------------------------

export function useGlobalIndices() {
  return useQuery({
    queryKey: ['global', 'globalIndices'],
    queryFn: () => api.get(GLOBAL.globalIndices),
    staleTime: STALE_1H,
  });
}
