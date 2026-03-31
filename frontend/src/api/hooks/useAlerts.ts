// =============================================================================
// Alerts Domain — React Query Hooks
// Wraps /v3/alerts endpoints for alert management & monitoring
// =============================================================================

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../client';
import { ALERTS } from '../endpoints';

const STALE_5M = 5 * 60 * 1000;

// ---------------------------------------------------------------------------
// Alert List & History
// ---------------------------------------------------------------------------

export function useAlerts() {
  return useQuery({
    queryKey: ['alerts', 'list'],
    queryFn: () => api.get(ALERTS.list),
    staleTime: STALE_5M,
  });
}

export function useAlertHistory() {
  return useQuery({
    queryKey: ['alerts', 'history'],
    queryFn: () => api.get(ALERTS.history),
    staleTime: STALE_5M,
  });
}

// ---------------------------------------------------------------------------
// Acknowledge — POST mutation
// ---------------------------------------------------------------------------

export function useAcknowledgeAlert() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.post(ALERTS.acknowledge(id)),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['alerts'] });
    },
  });
}

// ---------------------------------------------------------------------------
// Alert Rules CRUD
// ---------------------------------------------------------------------------

export function useAlertRules() {
  return useQuery({
    queryKey: ['alerts', 'rules'],
    queryFn: () => api.get(ALERTS.rules),
    staleTime: STALE_5M,
  });
}

export function useCreateAlertRule() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Record<string, unknown>) => api.post(ALERTS.create, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['alerts'] });
    },
  });
}

export function useUpdateAlertRule() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ ruleId, ...body }: Record<string, unknown> & { ruleId: string }) =>
      api.put(ALERTS.update(ruleId), body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['alerts'] });
    },
  });
}

export function useDeleteAlertRule() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (ruleId: string) => api.delete(ALERTS.delete(ruleId)),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['alerts'] });
    },
  });
}

// ---------------------------------------------------------------------------
// Fixed Income Alerts
// ---------------------------------------------------------------------------

export function useFiRatingAlerts() {
  return useQuery({
    queryKey: ['alerts', 'fi', 'ratings'],
    queryFn: () => api.get(ALERTS.fi.ratings),
    staleTime: STALE_5M,
  });
}

export function useFallenAngels() {
  return useQuery({
    queryKey: ['alerts', 'fi', 'fallenAngels'],
    queryFn: () => api.get(ALERTS.fi.fallenAngels),
    staleTime: STALE_5M,
  });
}

export function useRisingStars() {
  return useQuery({
    queryKey: ['alerts', 'fi', 'risingStars'],
    queryFn: () => api.get(ALERTS.fi.risingStars),
    staleTime: STALE_5M,
  });
}

export function useSpreadMoveAlerts() {
  return useQuery({
    queryKey: ['alerts', 'fi', 'spreadMoves'],
    queryFn: () => api.get(ALERTS.fi.spreadMoves),
    staleTime: STALE_5M,
  });
}

export function useMaturityAlerts() {
  return useQuery({
    queryKey: ['alerts', 'fi', 'maturityAlerts'],
    queryFn: () => api.get(ALERTS.fi.maturityAlerts),
    staleTime: STALE_5M,
  });
}

export function useCovenantBreachAlerts() {
  return useQuery({
    queryKey: ['alerts', 'fi', 'covenantBreaches'],
    queryFn: () => api.get(ALERTS.fi.covenantBreaches),
    staleTime: STALE_5M,
  });
}

// ---------------------------------------------------------------------------
// Equity Alerts
// ---------------------------------------------------------------------------

export function usePriceAlerts() {
  return useQuery({
    queryKey: ['alerts', 'equity', 'priceAlerts'],
    queryFn: () => api.get(ALERTS.equity.priceAlerts),
    staleTime: STALE_5M,
  });
}

export function useVolumeAlerts() {
  return useQuery({
    queryKey: ['alerts', 'equity', 'volumeAlerts'],
    queryFn: () => api.get(ALERTS.equity.volumeAlerts),
    staleTime: STALE_5M,
  });
}

export function useEarningsAlerts() {
  return useQuery({
    queryKey: ['alerts', 'equity', 'earningsAlerts'],
    queryFn: () => api.get(ALERTS.equity.earningsAlerts),
    staleTime: STALE_5M,
  });
}

export function useDividendAlerts() {
  return useQuery({
    queryKey: ['alerts', 'equity', 'dividendAlerts'],
    queryFn: () => api.get(ALERTS.equity.dividendAlerts),
    staleTime: STALE_5M,
  });
}
