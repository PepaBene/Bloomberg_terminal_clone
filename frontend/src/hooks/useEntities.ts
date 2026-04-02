import { useApiQuery } from './useApi';
import { ENTITIES, SECURITIES, FUNDAMENTALS } from '@/api/endpoints';

// ---------------------------------------------------------------------------
// Entity hooks
// ---------------------------------------------------------------------------

export function useEntitySearch(query: string) {
  return useApiQuery(['entities', 'search', query], ENTITIES.search, { q: query }, {
    enabled: query.length >= 2,
  });
}

export function useEntity(id: string | undefined) {
  return useApiQuery(['entities', id], ENTITIES.detail(id!), undefined, {
    enabled: !!id,
  });
}

export function useEntityRelationships(id: string | undefined) {
  return useApiQuery(['entities', id, 'relationships'], ENTITIES.relationships(id!), undefined, {
    enabled: !!id,
  });
}

export function useEntitySubsidiaries(id: string | undefined) {
  return useApiQuery(['entities', id, 'subsidiaries'], ENTITIES.subsidiaries(id!), undefined, {
    enabled: !!id,
  });
}

export function useEntityParentChain(id: string | undefined) {
  return useApiQuery(['entities', id, 'parent-chain'], ENTITIES.parentChain(id!), undefined, {
    enabled: !!id,
  });
}

export function useEntityOfficers(id: string | undefined) {
  return useApiQuery(['entities', id, 'officers'], ENTITIES.officers(id!), undefined, {
    enabled: !!id,
  });
}

export function useEntityBoardMembers(id: string | undefined) {
  return useApiQuery(['entities', id, 'board'], ENTITIES.boardMembers(id!), undefined, {
    enabled: !!id,
  });
}

export function useEntityHistory(id: string | undefined) {
  return useApiQuery(['entities', id, 'history'], ENTITIES.history(id!), undefined, {
    enabled: !!id,
  });
}

export function useEntityIdentifiers(id: string | undefined) {
  return useApiQuery(['entities', id, 'identifiers'], ENTITIES.identifiers(id!), undefined, {
    enabled: !!id,
  });
}

export function useEntityClassifications(id: string | undefined) {
  return useApiQuery(['entities', id, 'classifications'], ENTITIES.classifications(id!), undefined, {
    enabled: !!id,
  });
}

// ---------------------------------------------------------------------------
// Security hooks
// ---------------------------------------------------------------------------

export function useSecurity(id: string | undefined) {
  return useApiQuery(['securities', id], SECURITIES.detail(id!), undefined, {
    enabled: !!id,
  });
}

export function useSecuritySearch(query: string) {
  return useApiQuery(['securities', 'search', query], SECURITIES.search, { q: query }, {
    enabled: query.length >= 2,
  });
}

export function useSecurityPrices(id: string | undefined) {
  return useApiQuery(['securities', id, 'prices'], SECURITIES.prices(id!), undefined, {
    enabled: !!id,
  });
}

export function useSecurityPricesIntraday(id: string | undefined) {
  return useApiQuery(['securities', id, 'prices', 'intraday'], SECURITIES.pricesIntraday(id!), undefined, {
    enabled: !!id,
  });
}

export function useSecurityPricesHistory(id: string | undefined, period?: string) {
  return useApiQuery(['securities', id, 'prices', 'history', period], SECURITIES.pricesHistory(id!), { period }, {
    enabled: !!id,
  });
}

export function useInstitutionalHoldings(secId: string | undefined) {
  return useApiQuery(['securities', secId, 'holdings'], SECURITIES.institutionalHoldings(secId!), undefined, {
    enabled: !!secId,
  });
}

export function useInsiderHoldings(secId: string | undefined) {
  return useApiQuery(['securities', secId, 'insider-holdings'], SECURITIES.insiderHoldings(secId!), undefined, {
    enabled: !!secId,
  });
}

export function useOwnershipSummary(secId: string | undefined) {
  return useApiQuery(['securities', secId, 'ownership-summary'], SECURITIES.ownershipSummary(secId!), undefined, {
    enabled: !!secId,
  });
}

export function useShortInterest(secId: string | undefined) {
  return useApiQuery(['securities', secId, 'short-interest'], SECURITIES.shortInterest(secId!), undefined, {
    enabled: !!secId,
  });
}

export function useSecurityTechnicals(secId: string | undefined) {
  return useApiQuery(['securities', secId, 'technicals'], SECURITIES.technicals(secId!), undefined, {
    enabled: !!secId,
  });
}

export function useSecurityDividends(secId: string | undefined) {
  return useApiQuery(['securities', secId, 'dividends'], SECURITIES.dividends(secId!), undefined, {
    enabled: !!secId,
  });
}

export function useSecuritySplits(secId: string | undefined) {
  return useApiQuery(['securities', secId, 'splits'], SECURITIES.splits(secId!), undefined, {
    enabled: !!secId,
  });
}

export function useSecurityCorporateActions(secId: string | undefined) {
  return useApiQuery(['securities', secId, 'corporate-actions'], SECURITIES.corporateActions(secId!), undefined, {
    enabled: !!secId,
  });
}

export function useSecurityIdentifiers(secId: string | undefined) {
  return useApiQuery(['securities', secId, 'identifiers'], SECURITIES.identifiers(secId!), undefined, {
    enabled: !!secId,
  });
}

export function useExchanges() {
  return useApiQuery(['securities', 'exchanges'], SECURITIES.exchanges);
}

export function useSectors() {
  return useApiQuery(['securities', 'sectors'], SECURITIES.sectors);
}

// ---------------------------------------------------------------------------
// Fundamentals hooks
// ---------------------------------------------------------------------------

export function useIncomeStatements(entityId: string | undefined, annual?: boolean) {
  return useApiQuery(
    ['fundamentals', entityId, 'income', annual ? 'annual' : 'quarterly'],
    FUNDAMENTALS.incomeStatements(entityId!),
    { annual: annual ? 'true' : 'false' },
    { enabled: !!entityId }
  );
}

export function useBalanceSheets(entityId: string | undefined) {
  return useApiQuery(['fundamentals', entityId, 'balance'], FUNDAMENTALS.balanceSheets(entityId!), undefined, {
    enabled: !!entityId,
  });
}

export function useCashFlows(entityId: string | undefined) {
  return useApiQuery(['fundamentals', entityId, 'cashflow'], FUNDAMENTALS.cashFlows(entityId!), undefined, {
    enabled: !!entityId,
  });
}

export function useFilings(entityId: string | undefined) {
  return useApiQuery(['fundamentals', entityId, 'filings'], FUNDAMENTALS.filings(entityId!), undefined, {
    enabled: !!entityId,
  });
}

export function useSegments(entityId: string | undefined) {
  return useApiQuery(['fundamentals', entityId, 'segments'], FUNDAMENTALS.segments(entityId!), undefined, {
    enabled: !!entityId,
  });
}

export function useEntityRatios(entityId: string | undefined) {
  return useApiQuery(['fundamentals', entityId, 'ratios'], FUNDAMENTALS.ratios(entityId!), undefined, {
    enabled: !!entityId,
  });
}

export function useRevenueBreakdown(entityId: string | undefined) {
  return useApiQuery(['fundamentals', entityId, 'revenue-breakdown'], FUNDAMENTALS.revenueBreakdown(entityId!), undefined, {
    enabled: !!entityId,
  });
}

export function useGeographicBreakdown(entityId: string | undefined) {
  return useApiQuery(['fundamentals', entityId, 'geographic-breakdown'], FUNDAMENTALS.geographicBreakdown(entityId!), undefined, {
    enabled: !!entityId,
  });
}

export function useQuarterlyTrends(entityId: string | undefined) {
  return useApiQuery(['fundamentals', entityId, 'quarterly-trends'], FUNDAMENTALS.quarterlyTrends(entityId!), undefined, {
    enabled: !!entityId,
  });
}

export function useAnnualSummary(entityId: string | undefined) {
  return useApiQuery(['fundamentals', entityId, 'annual-summary'], FUNDAMENTALS.annualSummary(entityId!), undefined, {
    enabled: !!entityId,
  });
}

export function useKPIs(entityId: string | undefined) {
  return useApiQuery(['fundamentals', entityId, 'kpis'], FUNDAMENTALS.kpis(entityId!), undefined, {
    enabled: !!entityId,
  });
}
