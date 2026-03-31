// =============================================================================
// Market Data — React Query Hooks
// =============================================================================

import { useQuery } from '@tanstack/react-query';
import { api } from '../client';
import { MARKET_DATA } from '../endpoints';

const STALE_30S = 30 * 1000;

export function useQuote(symbol: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['marketData', 'quote', symbol],
    queryFn: () => api.get(MARKET_DATA.quote(symbol)),
    enabled: options?.enabled ?? !!symbol,
    staleTime: STALE_30S,
  });
}

export function useQuotes(params?: Record<string, string | number | boolean | undefined>) {
  return useQuery({
    queryKey: ['marketData', 'quotes', params],
    queryFn: () => api.get(MARKET_DATA.quotes, params),
    staleTime: STALE_30S,
  });
}

export function useMarketDepth(symbol: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['marketData', 'depth', symbol],
    queryFn: () => api.get(MARKET_DATA.depth(symbol)),
    enabled: options?.enabled ?? !!symbol,
    staleTime: STALE_30S,
  });
}

export function useTrades(symbol: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['marketData', 'trades', symbol],
    queryFn: () => api.get(MARKET_DATA.trades(symbol)),
    enabled: options?.enabled ?? !!symbol,
    staleTime: STALE_30S,
  });
}

export function useOhlcv(symbol: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['marketData', 'ohlcv', symbol],
    queryFn: () => api.get(MARKET_DATA.ohlcv(symbol)),
    enabled: options?.enabled ?? !!symbol,
    staleTime: STALE_30S,
  });
}

export function useMarketSnapshot() {
  return useQuery({
    queryKey: ['marketData', 'snapshot'],
    queryFn: () => api.get(MARKET_DATA.snapshot),
    staleTime: STALE_30S,
  });
}

export function useMarketStatus() {
  return useQuery({
    queryKey: ['marketData', 'status'],
    queryFn: () => api.get(MARKET_DATA.marketStatus),
    staleTime: STALE_30S,
  });
}

export function useIndices() {
  return useQuery({
    queryKey: ['marketData', 'indices'],
    queryFn: () => api.get(MARKET_DATA.indices),
    staleTime: STALE_30S,
  });
}

export function useIndexDetail(id: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['marketData', 'indexDetail', id],
    queryFn: () => api.get(MARKET_DATA.indexDetail(id)),
    enabled: options?.enabled ?? !!id,
    staleTime: STALE_30S,
  });
}

export function useIndexConstituents(id: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['marketData', 'indexConstituents', id],
    queryFn: () => api.get(MARKET_DATA.indexConstituents(id)),
    enabled: options?.enabled ?? !!id,
    staleTime: STALE_30S,
  });
}

export function useFutures() {
  return useQuery({
    queryKey: ['marketData', 'futures'],
    queryFn: () => api.get(MARKET_DATA.futures),
    staleTime: STALE_30S,
  });
}

export function useFutureDetail(symbol: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['marketData', 'futureDetail', symbol],
    queryFn: () => api.get(MARKET_DATA.futureDetail(symbol)),
    enabled: options?.enabled ?? !!symbol,
    staleTime: STALE_30S,
  });
}

export function useOptions(underlyer: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['marketData', 'options', underlyer],
    queryFn: () => api.get(MARKET_DATA.options(underlyer)),
    enabled: options?.enabled ?? !!underlyer,
    staleTime: STALE_30S,
  });
}

export function useOptionChain(underlyer: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['marketData', 'optionChain', underlyer],
    queryFn: () => api.get(MARKET_DATA.optionChain(underlyer)),
    enabled: options?.enabled ?? !!underlyer,
    staleTime: STALE_30S,
  });
}

export function useImpliedVolatility(underlyer: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['marketData', 'impliedVolatility', underlyer],
    queryFn: () => api.get(MARKET_DATA.impliedVolatility(underlyer)),
    enabled: options?.enabled ?? !!underlyer,
    staleTime: STALE_30S,
  });
}

export function useVolumeProfile(symbol: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['marketData', 'volumeProfile', symbol],
    queryFn: () => api.get(MARKET_DATA.volumeProfile(symbol)),
    enabled: options?.enabled ?? !!symbol,
    staleTime: STALE_30S,
  });
}

export function useHeatmap() {
  return useQuery({
    queryKey: ['marketData', 'heatmap'],
    queryFn: () => api.get(MARKET_DATA.heatmap),
    staleTime: STALE_30S,
  });
}

export function useMovers() {
  return useQuery({
    queryKey: ['marketData', 'movers'],
    queryFn: () => api.get(MARKET_DATA.movers),
    staleTime: STALE_30S,
  });
}

export function useMoversBySector(sector: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['marketData', 'movers', sector],
    queryFn: () => api.get(MARKET_DATA.moversBySector(sector)),
    enabled: options?.enabled ?? !!sector,
    staleTime: STALE_30S,
  });
}

export function useHighs52w() {
  return useQuery({
    queryKey: ['marketData', 'highs52w'],
    queryFn: () => api.get(MARKET_DATA.highs52w),
    staleTime: STALE_30S,
  });
}

export function useLows52w() {
  return useQuery({
    queryKey: ['marketData', 'lows52w'],
    queryFn: () => api.get(MARKET_DATA.lows52w),
    staleTime: STALE_30S,
  });
}

export function useMostActive() {
  return useQuery({
    queryKey: ['marketData', 'mostActive'],
    queryFn: () => api.get(MARKET_DATA.mostActive),
    staleTime: STALE_30S,
  });
}

export function useAdvancersDecliners() {
  return useQuery({
    queryKey: ['marketData', 'advancersDecliners'],
    queryFn: () => api.get(MARKET_DATA.advancersDecliners),
    staleTime: STALE_30S,
  });
}

export function useVix() {
  return useQuery({
    queryKey: ['marketData', 'vix'],
    queryFn: () => api.get(MARKET_DATA.vix),
    staleTime: STALE_30S,
  });
}
