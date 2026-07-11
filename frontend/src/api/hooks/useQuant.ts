// =============================================================================
// Quant Domain — React Query Hooks
// Wraps analytics correlation/factor + benchmark endpoints for quant workflows
// =============================================================================

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../client';
import { ANALYTICS, BENCHMARKS } from '../endpoints';

const STALE_24H = 24 * 60 * 60 * 1000;
const STALE_1H = 60 * 60 * 1000;

// ---------------------------------------------------------------------------
// Correlation Matrix — POST mutation
// ---------------------------------------------------------------------------

export function useCorrelationMatrix() {
  return useMutation({
    mutationFn: (params: Record<string, unknown>) =>
      api.post(ANALYTICS.correlation, params),
  });
}

// ---------------------------------------------------------------------------
// Factor Exposure (Quant alias)
// ---------------------------------------------------------------------------

export function useFactorExposureQuant(secId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['quant', 'factorExposure', secId],
    queryFn: () => api.get(ANALYTICS.factorExposure(secId)),
    enabled: options?.enabled ?? !!secId,
    staleTime: STALE_24H,
  });
}

// ---------------------------------------------------------------------------
// Benchmarks
// ---------------------------------------------------------------------------

export interface BenchmarkSummary {
  benchmark_id: string;
  name: string;
  code: string;
  ticker: string | null;
  benchmark_type: 'INDEX' | 'CUSTOM';
  constituent_count: number | null;
  created_at: string | null;
}

export interface CreateBenchmarkRequest {
  name: string;
  constituents: { ticker: string; weight: number }[];
}

// [Bug 94 fix] Real backend now exists (src/api/routers/benchmarks.py) --
// returns a plain array of BenchmarkSummary, not wrapped in `.benchmarks`/
// `.indices`.
export function useBenchmarks(options?: { enabled?: boolean }) {
  return useQuery<BenchmarkSummary[]>({
    queryKey: ['quant', 'benchmarks'],
    queryFn: () => api.get<BenchmarkSummary[]>(BENCHMARKS.list),
    enabled: options?.enabled ?? true,
    staleTime: STALE_1H,
  });
}

// [Bug 95 fix] Real backend now exists -- POST /v1/benchmarks persists a
// custom weighted benchmark/index and invalidates the list so
// CustomIndexBuilder.tsx sees it immediately.
export function useCreateBenchmark() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: CreateBenchmarkRequest) => api.post(BENCHMARKS.create, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['quant', 'benchmarks'] });
    },
  });
}

export function useBenchmarkDetail(id: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['quant', 'benchmarkDetail', id],
    queryFn: () => api.get(BENCHMARKS.detail(id)),
    enabled: options?.enabled ?? !!id,
    staleTime: STALE_1H,
  });
}

export function useBenchmarkReturns(id: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['quant', 'benchmarkReturns', id],
    queryFn: () => api.get(BENCHMARKS.returns(id)),
    enabled: options?.enabled ?? !!id,
    staleTime: STALE_1H,
  });
}

export function useBenchmarkConstituents(id: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['quant', 'benchmarkConstituents', id],
    queryFn: () => api.get(BENCHMARKS.constituents(id)),
    enabled: options?.enabled ?? !!id,
    staleTime: STALE_1H,
  });
}

export function useBenchmarkCompare() {
  return useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      api.post(BENCHMARKS.compare, body),
  });
}

export function useBenchmarkFactSheet(id: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['quant', 'benchmarkFactSheet', id],
    queryFn: () => api.get(BENCHMARKS.factSheets(id)),
    enabled: options?.enabled ?? !!id,
    staleTime: STALE_1H,
  });
}
