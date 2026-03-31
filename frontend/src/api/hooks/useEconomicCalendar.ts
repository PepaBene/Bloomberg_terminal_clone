// =============================================================================
// Economic Calendar — React Query Hooks
// =============================================================================

import { useQuery } from '@tanstack/react-query';
import { api } from '../client';
import { ECONOMIC_CALENDAR } from '../endpoints';

const STALE_1H = 60 * 60 * 1000;

export function useUpcomingEvents() {
  return useQuery({
    queryKey: ['economicCalendar', 'upcoming'],
    queryFn: () => api.get(ECONOMIC_CALENDAR.upcoming),
    staleTime: STALE_1H,
  });
}

export function useEconomicReleases() {
  return useQuery({
    queryKey: ['economicCalendar', 'releases'],
    queryFn: () => api.get(ECONOMIC_CALENDAR.releases),
    staleTime: STALE_1H,
  });
}

export function useEventsByDate(date: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['economicCalendar', 'byDate', date],
    queryFn: () => api.get(ECONOMIC_CALENDAR.byDate(date)),
    enabled: options?.enabled ?? !!date,
    staleTime: STALE_1H,
  });
}

export function useEventsByCountry(code: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['economicCalendar', 'byCountry', code],
    queryFn: () => api.get(ECONOMIC_CALENDAR.byCountry(code)),
    enabled: options?.enabled ?? !!code,
    staleTime: STALE_1H,
  });
}

export function useHighImpactEvents() {
  return useQuery({
    queryKey: ['economicCalendar', 'highImpact'],
    queryFn: () => api.get(ECONOMIC_CALENDAR.byImportance),
    staleTime: STALE_1H,
  });
}

export function useIpoCalendar() {
  return useQuery({
    queryKey: ['economicCalendar', 'ipo'],
    queryFn: () => api.get(ECONOMIC_CALENDAR.ipoCalendar),
    staleTime: STALE_1H,
  });
}

export function useDividendCalendar() {
  return useQuery({
    queryKey: ['economicCalendar', 'dividends'],
    queryFn: () => api.get(ECONOMIC_CALENDAR.dividendCalendar),
    staleTime: STALE_1H,
  });
}

export function useSplitCalendar() {
  return useQuery({
    queryKey: ['economicCalendar', 'splits'],
    queryFn: () => api.get(ECONOMIC_CALENDAR.splitCalendar),
    staleTime: STALE_1H,
  });
}

export function useFedMeetings() {
  return useQuery({
    queryKey: ['economicCalendar', 'fed'],
    queryFn: () => api.get(ECONOMIC_CALENDAR.fedMeetings),
    staleTime: STALE_1H,
  });
}

export function useCentralBankMeetings() {
  return useQuery({
    queryKey: ['economicCalendar', 'centralBanks'],
    queryFn: () => api.get(ECONOMIC_CALENDAR.centralBankMeetings),
    staleTime: STALE_1H,
  });
}

export function useOptionsExpiry() {
  return useQuery({
    queryKey: ['economicCalendar', 'optionsExpiry'],
    queryFn: () => api.get(ECONOMIC_CALENDAR.optionsExpiry),
    staleTime: STALE_1H,
  });
}
