// =============================================================================
// Fixed Income — Treasuries & Yield Curves — React Query Hooks
// =============================================================================

import { useQuery } from '@tanstack/react-query';
import { api } from '../client';
import { FI } from '../endpoints';

const STALE_24H = 24 * 60 * 60 * 1000;

// ---------------------------------------------------------------------------
// Treasuries
// ---------------------------------------------------------------------------

export function useTreasuries(params?: Record<string, string | number | boolean | undefined>) {
  return useQuery({
    queryKey: ['fi', 'treasuries', 'list', params],
    queryFn: () => api.get(FI.treasuries.list, params),
    staleTime: STALE_24H,
  });
}

export function useTreasuryDetail(cusip: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['fi', 'treasuries', 'detail', cusip],
    queryFn: () => api.get(FI.treasuries.detail(cusip)),
    enabled: options?.enabled ?? !!cusip,
    staleTime: STALE_24H,
  });
}

export function useOnTheRunTreasuries(params?: Record<string, string | number | boolean | undefined>) {
  return useQuery({
    queryKey: ['fi', 'treasuries', 'onTheRun', params],
    queryFn: () => api.get(FI.treasuries.onTheRun, params),
    staleTime: STALE_24H,
  });
}

export function useTreasuryAuction(params?: Record<string, string | number | boolean | undefined>) {
  return useQuery({
    queryKey: ['fi', 'treasuries', 'auction', params],
    queryFn: () => api.get(FI.treasuries.auction, params),
    staleTime: STALE_24H,
  });
}

export function useTreasuryAuctionHistory(params?: Record<string, string | number | boolean | undefined>) {
  return useQuery({
    queryKey: ['fi', 'treasuries', 'auctionHistory', params],
    queryFn: () => api.get(FI.treasuries.auctionHistory, params),
    staleTime: STALE_24H,
  });
}

// ---------------------------------------------------------------------------
// Yield Curves
// ---------------------------------------------------------------------------

export function useYieldCurve(params?: Record<string, string | number | boolean | undefined>) {
  return useQuery({
    queryKey: ['fi', 'yieldCurve', 'current', params],
    queryFn: () => api.get(FI.yieldCurve.current, params),
    staleTime: STALE_24H,
  });
}

export function useYieldCurveSpreads(params?: Record<string, string | number | boolean | undefined>) {
  return useQuery({
    queryKey: ['fi', 'yieldCurve', 'spreads', params],
    queryFn: () => api.get(FI.yieldCurve.spreads, params),
    staleTime: STALE_24H,
  });
}

export function useYieldCurveHistory(params?: Record<string, string | number | boolean | undefined>) {
  return useQuery({
    queryKey: ['fi', 'yieldCurve', 'history', params],
    queryFn: () => api.get(FI.yieldCurve.history, params),
    staleTime: STALE_24H,
  });
}

export function useForwardCurve(params?: Record<string, string | number | boolean | undefined>) {
  return useQuery({
    queryKey: ['fi', 'yieldCurve', 'forward', params],
    queryFn: () => api.get(FI.yieldCurve.forward, params),
    staleTime: STALE_24H,
  });
}

export function useRealYieldCurve(params?: Record<string, string | number | boolean | undefined>) {
  return useQuery({
    queryKey: ['fi', 'yieldCurve', 'real', params],
    queryFn: () => api.get(FI.yieldCurve.real, params),
    staleTime: STALE_24H,
  });
}

export function useBreakevenInflation(params?: Record<string, string | number | boolean | undefined>) {
  return useQuery({
    queryKey: ['fi', 'yieldCurve', 'breakeven', params],
    queryFn: () => api.get(FI.yieldCurve.breakeven, params),
    staleTime: STALE_24H,
  });
}

export function useSwapCurve(params?: Record<string, string | number | boolean | undefined>) {
  return useQuery({
    queryKey: ['fi', 'yieldCurve', 'swap', params],
    queryFn: () => api.get(FI.yieldCurve.swap, params),
    staleTime: STALE_24H,
  });
}

export function useSovereignYieldCurve(countryCode: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['fi', 'yieldCurve', 'sovereign', countryCode],
    queryFn: () => api.get(FI.yieldCurve.sovereign(countryCode)),
    enabled: options?.enabled ?? !!countryCode,
    staleTime: STALE_24H,
  });
}
