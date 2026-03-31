// =============================================================================
// Portfolios — React Query Hooks
// =============================================================================

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../client';
import { PORTFOLIOS } from '../endpoints';

const STALE_1H = 60 * 60 * 1000;

// ---------------------------------------------------------------------------
// List / Detail / CRUD
// ---------------------------------------------------------------------------

export function usePortfolios(params?: Record<string, string | number | boolean | undefined>) {
  return useQuery({
    queryKey: ['portfolios', 'list', params],
    queryFn: () => api.get(PORTFOLIOS.list, params),
    staleTime: STALE_1H,
  });
}

export function usePortfolio(id: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['portfolios', 'detail', id],
    queryFn: () => api.get(PORTFOLIOS.detail(id)),
    enabled: options?.enabled ?? !!id,
    staleTime: STALE_1H,
  });
}

export function useCreatePortfolio() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Record<string, unknown>) => api.post(PORTFOLIOS.create, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['portfolios'] });
    },
  });
}

export function useUpdatePortfolio() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...body }: Record<string, unknown> & { id: string }) =>
      api.put(PORTFOLIOS.update(id), body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['portfolios'] });
    },
  });
}

export function useDeletePortfolio() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.delete(PORTFOLIOS.delete(id)),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['portfolios'] });
    },
  });
}

// ---------------------------------------------------------------------------
// Positions
// ---------------------------------------------------------------------------

export function usePositions(portfolioId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['portfolios', portfolioId, 'positions'],
    queryFn: () => api.get(PORTFOLIOS.positions(portfolioId)),
    enabled: options?.enabled ?? !!portfolioId,
    staleTime: STALE_1H,
  });
}

export function usePositionDetail(portfolioId: string, posId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['portfolios', portfolioId, 'positions', posId],
    queryFn: () => api.get(PORTFOLIOS.positionDetail(portfolioId, posId)),
    enabled: options?.enabled ?? !!(portfolioId && posId),
    staleTime: STALE_1H,
  });
}

// ---------------------------------------------------------------------------
// Transactions
// ---------------------------------------------------------------------------

export function useTransactions(portfolioId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['portfolios', portfolioId, 'transactions'],
    queryFn: () => api.get(PORTFOLIOS.transactions(portfolioId)),
    enabled: options?.enabled ?? !!portfolioId,
    staleTime: STALE_1H,
  });
}

export function useAddTransaction(portfolioId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      api.post(PORTFOLIOS.addTransaction(portfolioId), body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['portfolios', portfolioId] });
    },
  });
}

// ---------------------------------------------------------------------------
// NAV
// ---------------------------------------------------------------------------

export function usePortfolioNav(portfolioId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['portfolios', portfolioId, 'nav'],
    queryFn: () => api.get(PORTFOLIOS.nav(portfolioId)),
    enabled: options?.enabled ?? !!portfolioId,
    staleTime: STALE_1H,
  });
}

export function usePortfolioNavHistory(portfolioId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['portfolios', portfolioId, 'navHistory'],
    queryFn: () => api.get(PORTFOLIOS.navHistory(portfolioId)),
    enabled: options?.enabled ?? !!portfolioId,
    staleTime: STALE_1H,
  });
}

// ---------------------------------------------------------------------------
// Upload
// ---------------------------------------------------------------------------

export function useUploadPreview() {
  return useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      api.post(PORTFOLIOS.uploadPreview, body),
  });
}

export function useUploadCommit() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      api.post(PORTFOLIOS.uploadCommit, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['portfolios'] });
    },
  });
}

// ---------------------------------------------------------------------------
// Clone / Snapshot
// ---------------------------------------------------------------------------

export function useClonePortfolio() {
  return useMutation({
    mutationFn: (id: string) => api.post(PORTFOLIOS.clone(id)),
  });
}

export function usePortfolioSnapshot(portfolioId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['portfolios', portfolioId, 'snapshot'],
    queryFn: () => api.get(PORTFOLIOS.snapshot(portfolioId)),
    enabled: options?.enabled ?? !!portfolioId,
    staleTime: STALE_1H,
  });
}

// ---------------------------------------------------------------------------
// Allocations
// ---------------------------------------------------------------------------

export function useAllocations(portfolioId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['portfolios', portfolioId, 'allocations'],
    queryFn: () => api.get(PORTFOLIOS.allocations(portfolioId)),
    enabled: options?.enabled ?? !!portfolioId,
    staleTime: STALE_1H,
  });
}

export function useAllocationsBySector(portfolioId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['portfolios', portfolioId, 'allocations', 'sector'],
    queryFn: () => api.get(PORTFOLIOS.allocationsBySector(portfolioId)),
    enabled: options?.enabled ?? !!portfolioId,
    staleTime: STALE_1H,
  });
}

export function useAllocationsByCountry(portfolioId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['portfolios', portfolioId, 'allocations', 'country'],
    queryFn: () => api.get(PORTFOLIOS.allocationsByCountry(portfolioId)),
    enabled: options?.enabled ?? !!portfolioId,
    staleTime: STALE_1H,
  });
}

export function useAllocationsByAssetClass(portfolioId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['portfolios', portfolioId, 'allocations', 'assetClass'],
    queryFn: () => api.get(PORTFOLIOS.allocationsByAssetClass(portfolioId)),
    enabled: options?.enabled ?? !!portfolioId,
    staleTime: STALE_1H,
  });
}

// ---------------------------------------------------------------------------
// Rebalance / Optimize / What-If
// ---------------------------------------------------------------------------

export function useRebalance(portfolioId: string) {
  return useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      api.post(PORTFOLIOS.rebalance(portfolioId), body),
  });
}

export function useOptimize(portfolioId: string) {
  return useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      api.post(PORTFOLIOS.optimize(portfolioId), body),
  });
}

export function useWhatIf(portfolioId: string) {
  return useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      api.post(PORTFOLIOS.whatIf(portfolioId), body),
  });
}

// ---------------------------------------------------------------------------
// Tax / Income / Dividends
// ---------------------------------------------------------------------------

export function useTaxLotAnalysis(portfolioId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['portfolios', portfolioId, 'taxLots'],
    queryFn: () => api.get(PORTFOLIOS.taxLotAnalysis(portfolioId)),
    enabled: options?.enabled ?? !!portfolioId,
    staleTime: STALE_1H,
  });
}

export function usePortfolioIncome(portfolioId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['portfolios', portfolioId, 'income'],
    queryFn: () => api.get(PORTFOLIOS.income(portfolioId)),
    enabled: options?.enabled ?? !!portfolioId,
    staleTime: STALE_1H,
  });
}

export function useIncomeProjection(portfolioId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['portfolios', portfolioId, 'incomeProjection'],
    queryFn: () => api.get(PORTFOLIOS.incomeProjection(portfolioId)),
    enabled: options?.enabled ?? !!portfolioId,
    staleTime: STALE_1H,
  });
}

export function usePortfolioDividendCalendar(portfolioId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['portfolios', portfolioId, 'dividendCalendar'],
    queryFn: () => api.get(PORTFOLIOS.dividendCalendar(portfolioId)),
    enabled: options?.enabled ?? !!portfolioId,
    staleTime: STALE_1H,
  });
}
