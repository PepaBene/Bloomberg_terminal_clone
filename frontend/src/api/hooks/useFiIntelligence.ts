// =============================================================================
// Fixed Income — Intelligence Briefings — React Query Hooks
// =============================================================================

import { useQuery } from '@tanstack/react-query';
import { api } from '../client';
import { FI_INTELLIGENCE } from '../endpoints';

const STALE_30M = 30 * 60 * 1000;

export function useYieldCurveBriefing(params?: Record<string, string | number | boolean | undefined>) {
  return useQuery({
    queryKey: ['fi', 'intelligence', 'yieldCurveBriefing', params],
    queryFn: () => api.get(FI_INTELLIGENCE.yieldCurveBriefing, params),
    staleTime: STALE_30M,
  });
}

export function useCreditBriefing(params?: Record<string, string | number | boolean | undefined>) {
  return useQuery({
    queryKey: ['fi', 'intelligence', 'creditBriefing', params],
    queryFn: () => api.get(FI_INTELLIGENCE.creditBriefing, params),
    staleTime: STALE_30M,
  });
}

export function useIssuanceToday(params?: Record<string, string | number | boolean | undefined>) {
  return useQuery({
    queryKey: ['fi', 'intelligence', 'issuanceToday', params],
    queryFn: () => api.get(FI_INTELLIGENCE.issuanceToday, params),
    staleTime: STALE_30M,
  });
}

export function useCrossAssetSignals(params?: Record<string, string | number | boolean | undefined>) {
  return useQuery({
    queryKey: ['fi', 'intelligence', 'crossAssetSignals', params],
    queryFn: () => api.get(FI_INTELLIGENCE.crossAssetSignals, params),
    staleTime: STALE_30M,
  });
}

export function useIssuerCreditIntel(entityId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['fi', 'intelligence', 'issuerCredit', entityId],
    queryFn: () => api.get(FI_INTELLIGENCE.issuerCredit(entityId)),
    enabled: options?.enabled ?? !!entityId,
    staleTime: STALE_30M,
  });
}

export function useFiSectorOutlook(sector: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['fi', 'intelligence', 'sectorOutlook', sector],
    queryFn: () => api.get(FI_INTELLIGENCE.sectorOutlook(sector)),
    enabled: options?.enabled ?? !!sector,
    staleTime: STALE_30M,
  });
}

export function useFiRelativeValue(params?: Record<string, string | number | boolean | undefined>) {
  return useQuery({
    queryKey: ['fi', 'intelligence', 'relativeValue', params],
    queryFn: () => api.get(FI_INTELLIGENCE.relativeValue, params),
    staleTime: STALE_30M,
  });
}

export function useFiMarketConditions(params?: Record<string, string | number | boolean | undefined>) {
  return useQuery({
    queryKey: ['fi', 'intelligence', 'marketConditions', params],
    queryFn: () => api.get(FI_INTELLIGENCE.marketConditions, params),
    staleTime: STALE_30M,
  });
}

export function useFiFlowsAnalysis(params?: Record<string, string | number | boolean | undefined>) {
  return useQuery({
    queryKey: ['fi', 'intelligence', 'flowsAnalysis', params],
    queryFn: () => api.get(FI_INTELLIGENCE.flowsAnalysis, params),
    staleTime: STALE_30M,
  });
}

export function useFiLiquidityIndex(params?: Record<string, string | number | boolean | undefined>) {
  return useQuery({
    queryKey: ['fi', 'intelligence', 'liquidityIndex', params],
    queryFn: () => api.get(FI_INTELLIGENCE.liquidityIndex, params),
    staleTime: STALE_30M,
  });
}

export function useFiTechnicalLevels(params?: Record<string, string | number | boolean | undefined>) {
  return useQuery({
    queryKey: ['fi', 'intelligence', 'technicalLevels', params],
    queryFn: () => api.get(FI_INTELLIGENCE.technicalLevels, params),
    staleTime: STALE_30M,
  });
}
