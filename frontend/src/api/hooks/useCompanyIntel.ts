// =============================================================================
// Company Intelligence Domain — React Query Hooks
// Wraps /v3/intelligence endpoints for deep company analysis
// =============================================================================

import { useQuery } from '@tanstack/react-query';
import { api } from '../client';
import { COMPANY_INTEL } from '../endpoints';

const STALE_24H = 24 * 60 * 60 * 1000;

// ---------------------------------------------------------------------------
// Overview & Business Model
// ---------------------------------------------------------------------------

export function useCompanyIntelOverview(entityId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['companyIntel', 'overview', entityId],
    queryFn: () => api.get(COMPANY_INTEL.overview(entityId)),
    enabled: options?.enabled ?? !!entityId,
    staleTime: STALE_24H,
  });
}

export function useBusinessModel(entityId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['companyIntel', 'businessModel', entityId],
    queryFn: () => api.get(COMPANY_INTEL.businessModel(entityId)),
    enabled: options?.enabled ?? !!entityId,
    staleTime: STALE_24H,
  });
}

// ---------------------------------------------------------------------------
// Capital Allocation & Management
// ---------------------------------------------------------------------------

export function useCapitalAllocation(entityId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['companyIntel', 'capitalAllocation', entityId],
    queryFn: () => api.get(COMPANY_INTEL.capitalAllocation(entityId)),
    enabled: options?.enabled ?? !!entityId,
    staleTime: STALE_24H,
  });
}

export function useManagementQuality(entityId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['companyIntel', 'management', entityId],
    queryFn: () => api.get(COMPANY_INTEL.management(entityId)),
    enabled: options?.enabled ?? !!entityId,
    staleTime: STALE_24H,
  });
}

// ---------------------------------------------------------------------------
// Balance Sheet & Revenue
// ---------------------------------------------------------------------------

export function useBalanceSheetRisk(entityId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['companyIntel', 'balanceSheetRisk', entityId],
    queryFn: () => api.get(COMPANY_INTEL.balanceSheetRisk(entityId)),
    enabled: options?.enabled ?? !!entityId,
    staleTime: STALE_24H,
  });
}

export function useRevenueDrivers(entityId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['companyIntel', 'revenueDrivers', entityId],
    queryFn: () => api.get(COMPANY_INTEL.revenueDrivers(entityId)),
    enabled: options?.enabled ?? !!entityId,
    staleTime: STALE_24H,
  });
}

export function useCostStructure(entityId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['companyIntel', 'costStructure', entityId],
    queryFn: () => api.get(COMPANY_INTEL.costStructure(entityId)),
    enabled: options?.enabled ?? !!entityId,
    staleTime: STALE_24H,
  });
}

// ---------------------------------------------------------------------------
// Growth & Quality
// ---------------------------------------------------------------------------

export function useGrowthProfile(entityId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['companyIntel', 'growthProfile', entityId],
    queryFn: () => api.get(COMPANY_INTEL.growthProfile(entityId)),
    enabled: options?.enabled ?? !!entityId,
    staleTime: STALE_24H,
  });
}

export function useQualityMetrics(entityId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['companyIntel', 'qualityMetrics', entityId],
    queryFn: () => api.get(COMPANY_INTEL.qualityMetrics(entityId)),
    enabled: options?.enabled ?? !!entityId,
    staleTime: STALE_24H,
  });
}

// ---------------------------------------------------------------------------
// Risk & Operating Leverage
// ---------------------------------------------------------------------------

export function useRiskProfile(entityId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['companyIntel', 'riskProfile', entityId],
    queryFn: () => api.get(COMPANY_INTEL.riskProfile(entityId)),
    enabled: options?.enabled ?? !!entityId,
    staleTime: STALE_24H,
  });
}

export function useOperatingLeverage(entityId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['companyIntel', 'operatingLeverage', entityId],
    queryFn: () => api.get(COMPANY_INTEL.operatingLeverage(entityId)),
    enabled: options?.enabled ?? !!entityId,
    staleTime: STALE_24H,
  });
}

// ---------------------------------------------------------------------------
// Margins & Working Capital
// ---------------------------------------------------------------------------

export function useMarginAnalysis(entityId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['companyIntel', 'marginAnalysis', entityId],
    queryFn: () => api.get(COMPANY_INTEL.marginAnalysis(entityId)),
    enabled: options?.enabled ?? !!entityId,
    staleTime: STALE_24H,
  });
}

export function useWorkingCapital(entityId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['companyIntel', 'workingCapital', entityId],
    queryFn: () => api.get(COMPANY_INTEL.workingCapital(entityId)),
    enabled: options?.enabled ?? !!entityId,
    staleTime: STALE_24H,
  });
}
