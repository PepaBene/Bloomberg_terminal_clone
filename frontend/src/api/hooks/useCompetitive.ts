// =============================================================================
// Competitive Domain — React Query Hooks
// Wraps /v3/competitive endpoints for competitive intelligence
// =============================================================================

import { useQuery } from '@tanstack/react-query';
import { api } from '../client';
import { COMPETITIVE } from '../endpoints';

const STALE_24H = 24 * 60 * 60 * 1000;

// ---------------------------------------------------------------------------
// Moat & Concentration
// ---------------------------------------------------------------------------

export function useMoat(entityId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['competitive', 'moat', entityId],
    queryFn: () => api.get(COMPETITIVE.moat(entityId)),
    enabled: options?.enabled ?? !!entityId,
    staleTime: STALE_24H,
  });
}

export function useConcentrationRisk(entityId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['competitive', 'concentration', entityId],
    queryFn: () => api.get(COMPETITIVE.concentration(entityId)),
    enabled: options?.enabled ?? !!entityId,
    staleTime: STALE_24H,
  });
}

// ---------------------------------------------------------------------------
// Landscape & Peers
// ---------------------------------------------------------------------------

export function useCompetitiveLandscape(entityId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['competitive', 'landscape', entityId],
    queryFn: () => api.get(COMPETITIVE.landscape(entityId)),
    enabled: options?.enabled ?? !!entityId,
    staleTime: STALE_24H,
  });
}

export function useCompetitivePeers(entityId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['competitive', 'peers', entityId],
    queryFn: () => api.get(COMPETITIVE.peers(entityId)),
    enabled: options?.enabled ?? !!entityId,
    staleTime: STALE_24H,
  });
}

// ---------------------------------------------------------------------------
// Market Share & SWOT
// ---------------------------------------------------------------------------

export function useMarketShare(entityId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['competitive', 'marketShare', entityId],
    queryFn: () => api.get(COMPETITIVE.marketShare(entityId)),
    enabled: options?.enabled ?? !!entityId,
    staleTime: STALE_24H,
  });
}

export function useSwot(entityId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['competitive', 'swot', entityId],
    queryFn: () => api.get(COMPETITIVE.swot(entityId)),
    enabled: options?.enabled ?? !!entityId,
    staleTime: STALE_24H,
  });
}

// ---------------------------------------------------------------------------
// Porter's Forces & Supply Chain
// ---------------------------------------------------------------------------

export function usePorterForces(entityId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['competitive', 'porterForces', entityId],
    queryFn: () => api.get(COMPETITIVE.porterForces(entityId)),
    enabled: options?.enabled ?? !!entityId,
    staleTime: STALE_24H,
  });
}

export function useSupplyChain(entityId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['competitive', 'supplyChain', entityId],
    queryFn: () => api.get(COMPETITIVE.supplyChain(entityId)),
    enabled: options?.enabled ?? !!entityId,
    staleTime: STALE_24H,
  });
}

// ---------------------------------------------------------------------------
// Customers & Suppliers
// ---------------------------------------------------------------------------

export function useCustomers(entityId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['competitive', 'customers', entityId],
    queryFn: () => api.get(COMPETITIVE.customers(entityId)),
    enabled: options?.enabled ?? !!entityId,
    staleTime: STALE_24H,
  });
}

export function useSuppliers(entityId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['competitive', 'suppliers', entityId],
    queryFn: () => api.get(COMPETITIVE.suppliers(entityId)),
    enabled: options?.enabled ?? !!entityId,
    staleTime: STALE_24H,
  });
}
