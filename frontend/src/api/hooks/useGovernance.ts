// =============================================================================
// Governance Domain — React Query Hooks
// Wraps /v3/filings governance endpoints for corporate governance data
// =============================================================================

import { useQuery } from '@tanstack/react-query';
import { api } from '../client';
import { GOVERNANCE } from '../endpoints';

const STALE_24H = 24 * 60 * 60 * 1000;

// ---------------------------------------------------------------------------
// Proxy & Compensation
// ---------------------------------------------------------------------------

export function useProxyFilings(entityId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['governance', 'proxy', entityId],
    queryFn: () => api.get(GOVERNANCE.proxy(entityId)),
    enabled: options?.enabled ?? !!entityId,
    staleTime: STALE_24H,
  });
}

export function useCompensation(entityId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['governance', 'compensation', entityId],
    queryFn: () => api.get(GOVERNANCE.compensation(entityId)),
    enabled: options?.enabled ?? !!entityId,
    staleTime: STALE_24H,
  });
}

// ---------------------------------------------------------------------------
// Governance & Board
// ---------------------------------------------------------------------------

export function useGovernance(entityId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['governance', 'governance', entityId],
    queryFn: () => api.get(GOVERNANCE.governance(entityId)),
    enabled: options?.enabled ?? !!entityId,
    staleTime: STALE_24H,
  });
}

export function useBoardComposition(entityId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['governance', 'board', entityId],
    queryFn: () => api.get(GOVERNANCE.board(entityId)),
    enabled: options?.enabled ?? !!entityId,
    staleTime: STALE_24H,
  });
}

// ---------------------------------------------------------------------------
// Shareholder Proposals
// ---------------------------------------------------------------------------

export function useShareholderProposals(entityId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['governance', 'shareholderProposals', entityId],
    queryFn: () => api.get(GOVERNANCE.shareholderProposals(entityId)),
    enabled: options?.enabled ?? !!entityId,
    staleTime: STALE_24H,
  });
}
