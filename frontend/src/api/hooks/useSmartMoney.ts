// =============================================================================
// Smart Money / Notable-Filer Tracking — React Query Hooks
// Wraps /v1/smart-money/* endpoints (src/api/routers/smart_money.py).
// =============================================================================

import { useQuery } from '@tanstack/react-query';
import { api } from '../client';
import { SMART_MONEY } from '../endpoints';

const STALE_1H = 60 * 60 * 1000;

// ---------------------------------------------------------------------------
// Registry — notable investors (13F gurus, insiders, politicians)
// ---------------------------------------------------------------------------

export function useNotableInvestors(category?: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['smartMoney', 'investors', category ?? 'all'],
    queryFn: () => api.get(SMART_MONEY.investors(category)),
    enabled: options?.enabled ?? true,
    staleTime: STALE_1H,
  });
}

export function useNotableInvestor(key: string | undefined, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['smartMoney', 'investor', key],
    queryFn: () => api.get(SMART_MONEY.investor(key as string)),
    enabled: options?.enabled ?? !!key,
    staleTime: STALE_1H,
  });
}

// ---------------------------------------------------------------------------
// 13F filer profile — quarter-over-quarter activity
// ---------------------------------------------------------------------------

export function useFilerProfile(key: string | undefined, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['smartMoney', 'filerProfile', key],
    queryFn: () => api.get(SMART_MONEY.filerProfile(key as string)),
    enabled: options?.enabled ?? !!key,
    staleTime: STALE_1H,
  });
}

// ---------------------------------------------------------------------------
// Congressional (STOCK Act) trades
// ---------------------------------------------------------------------------

export function useCongressionalTrades(
  params?: { politician?: string; ticker?: string; page?: number; page_size?: number },
  options?: { enabled?: boolean },
) {
  return useQuery({
    queryKey: ['smartMoney', 'congress', params],
    queryFn: () => api.get(SMART_MONEY.congress, params as Record<string, string | number | boolean | undefined>),
    enabled: options?.enabled ?? true,
    staleTime: STALE_1H,
  });
}

// ---------------------------------------------------------------------------
// Consensus — securities multiple tracked 13F managers agree on
// ---------------------------------------------------------------------------

export function useSmartMoneyConsensus(options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['smartMoney', 'consensus'],
    queryFn: () => api.get(SMART_MONEY.consensus),
    enabled: options?.enabled ?? true,
    staleTime: STALE_1H,
  });
}

// ---------------------------------------------------------------------------
// Flow — net smart-money pressure on a single ticker
// ---------------------------------------------------------------------------

export function useSmartMoneyFlow(ticker: string | undefined, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['smartMoney', 'flow', ticker],
    queryFn: () => api.get(SMART_MONEY.flow(ticker as string)),
    enabled: options?.enabled ?? !!ticker,
    staleTime: STALE_1H,
  });
}
