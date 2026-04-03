import { useApiQuery } from './useApi';
import { FI } from '@/api/endpoints';

// ---------------------------------------------------------------------------
// Yield Curve
// ---------------------------------------------------------------------------

export function useYieldCurve() {
  return useApiQuery(['fi', 'yield-curve'], FI.yieldCurve.current);
}

export function useYieldCurveSpreads() {
  return useApiQuery(['fi', 'yield-curve', 'spreads'], FI.yieldCurve.spreads);
}

export function useYieldCurveHistory() {
  return useApiQuery(['fi', 'yield-curve', 'history'], FI.yieldCurve.history);
}

export function useYieldCurveForward() {
  return useApiQuery(['fi', 'yield-curve', 'forward'], FI.yieldCurve.forward);
}

export function useRealYieldCurve() {
  return useApiQuery(['fi', 'yield-curve', 'real'], FI.yieldCurve.real);
}

export function useBreakevenCurve() {
  return useApiQuery(['fi', 'yield-curve', 'breakeven'], FI.yieldCurve.breakeven);
}

export function useSwapCurve() {
  return useApiQuery(['fi', 'yield-curve', 'swap'], FI.yieldCurve.swap);
}

export function useSovereignCurve(countryCode?: string) {
  return useApiQuery(['fi', 'yield-curve', 'sovereign', countryCode], FI.yieldCurve.sovereign(countryCode ?? ''), undefined, {
    enabled: !!countryCode,
  });
}

// ---------------------------------------------------------------------------
// Treasuries
// ---------------------------------------------------------------------------

export function useTreasuries() {
  return useApiQuery(['fi', 'treasuries'], FI.treasuries.list);
}

export function useTreasuryDetail(cusip: string | undefined) {
  return useApiQuery(['fi', 'treasuries', cusip], FI.treasuries.detail(cusip ?? ''), undefined, {
    enabled: !!cusip,
  });
}

export function useTreasuriesOnTheRun() {
  return useApiQuery(['fi', 'treasuries', 'on-the-run'], FI.treasuries.onTheRun);
}

export function useTreasuryAuction() {
  return useApiQuery(['fi', 'treasuries', 'auction'], FI.treasuries.auction);
}

export function useTreasuryAuctionHistory() {
  return useApiQuery(['fi', 'treasuries', 'auction', 'history'], FI.treasuries.auctionHistory);
}

// ---------------------------------------------------------------------------
// Bonds
// ---------------------------------------------------------------------------

export function useBondDetail(id: string | undefined) {
  return useApiQuery(['fi', 'bonds', id], FI.bonds.detail(id ?? ''), undefined, {
    enabled: !!id,
  });
}

export function useBondPrices(cusip: string | undefined) {
  return useApiQuery(['fi', 'bonds', cusip, 'prices'], FI.bonds.prices(cusip ?? ''), undefined, {
    enabled: !!cusip,
  });
}

export function useBondSpreads(cusip: string | undefined) {
  return useApiQuery(['fi', 'bonds', cusip, 'spreads'], FI.bonds.spreads(cusip ?? ''), undefined, {
    enabled: !!cusip,
  });
}

export function useBondsByIssuer(entityId: string | undefined) {
  return useApiQuery(['fi', 'bonds', 'issuer', entityId], FI.bonds.byIssuer(entityId ?? ''), undefined, {
    enabled: !!entityId,
  });
}

export function useBondCashFlows(cusip: string | undefined) {
  return useApiQuery(['fi', 'bonds', cusip, 'cash-flows'], FI.bonds.cashFlows(cusip ?? ''), undefined, {
    enabled: !!cusip,
  });
}

export function useBondCallSchedule(cusip: string | undefined) {
  return useApiQuery(['fi', 'bonds', cusip, 'call-schedule'], FI.bonds.callSchedule(cusip ?? ''), undefined, {
    enabled: !!cusip,
  });
}

export function useBondCovenants(cusip: string | undefined) {
  return useApiQuery(['fi', 'bonds', cusip, 'covenants'], FI.bonds.covenants(cusip ?? ''), undefined, {
    enabled: !!cusip,
  });
}

export function useBondComparables(cusip: string | undefined) {
  return useApiQuery(['fi', 'bonds', cusip, 'comparables'], FI.bonds.comparables(cusip ?? ''), undefined, {
    enabled: !!cusip,
  });
}

export function useBondSearch(query: string) {
  return useApiQuery(['fi', 'bonds', 'search', query], FI.bonds.search, { q: query }, {
    enabled: query.length >= 2,
  });
}

// ---------------------------------------------------------------------------
// Ratings
// ---------------------------------------------------------------------------

export function useCreditRatings(entityId: string | undefined) {
  return useApiQuery(['fi', 'ratings', entityId], FI.ratings.byEntity(entityId ?? ''), undefined, {
    enabled: !!entityId,
  });
}

export function useCreditRatingsHistory(entityId: string | undefined) {
  return useApiQuery(['fi', 'ratings', entityId, 'history'], FI.ratings.history(entityId ?? ''), undefined, {
    enabled: !!entityId,
  });
}

export function useRecentRatingChanges() {
  return useApiQuery(['fi', 'ratings', 'changes'], FI.ratings.recentChanges);
}

export function useRatingDistribution() {
  return useApiQuery(['fi', 'ratings', 'distribution'], FI.ratings.distribution);
}

export function useTransitionMatrix() {
  return useApiQuery(['fi', 'ratings', 'transition-matrix'], FI.ratings.transitionMatrix);
}

export function useRatingOutlook(entityId: string | undefined) {
  return useApiQuery(['fi', 'ratings', entityId, 'outlook'], FI.ratings.outlook(entityId ?? ''), undefined, {
    enabled: !!entityId,
  });
}

// ---------------------------------------------------------------------------
// Credit
// ---------------------------------------------------------------------------

export function useCreditScore(entityId: string | undefined) {
  return useApiQuery(['fi', 'credit', entityId, 'score'], FI.credit.score(entityId ?? ''), undefined, {
    enabled: !!entityId,
  });
}

export function useCreditRatios(entityId: string | undefined) {
  return useApiQuery(['fi', 'credit', entityId, 'ratios'], FI.credit.ratios(entityId ?? ''), undefined, {
    enabled: !!entityId,
  });
}

export function useCreditPeers(entityId: string | undefined) {
  return useApiQuery(['fi', 'credit', entityId, 'peers'], FI.credit.peers(entityId ?? ''), undefined, {
    enabled: !!entityId,
  });
}

export function useCreditTrend(entityId: string | undefined) {
  return useApiQuery(['fi', 'credit', entityId, 'trend'], FI.credit.trend(entityId ?? ''), undefined, {
    enabled: !!entityId,
  });
}

export function useCreditSpreads() {
  return useApiQuery(['fi', 'credit', 'sector-spreads'], FI.credit.sectorSpreads);
}

export function useDistressedCredit() {
  return useApiQuery(['fi', 'credit', 'distressed'], FI.credit.distressed);
}

export function useDefaultProbability(entityId: string | undefined) {
  return useApiQuery(['fi', 'credit', entityId, 'default-prob'], FI.credit.defaultProbability(entityId ?? ''), undefined, {
    enabled: !!entityId,
  });
}

export function useRecoveryRate(entityId: string | undefined) {
  return useApiQuery(['fi', 'credit', entityId, 'recovery-rate'], FI.credit.recoveryRate(entityId ?? ''), undefined, {
    enabled: !!entityId,
  });
}

export function useCDS(entityId: string | undefined) {
  return useApiQuery(['fi', 'credit', entityId, 'cds'], FI.credit.cds(entityId ?? ''), undefined, {
    enabled: !!entityId,
  });
}

export function useCDSCurve(entityId: string | undefined) {
  return useApiQuery(['fi', 'credit', entityId, 'cds', 'curve'], FI.credit.cdsCurve(entityId ?? ''), undefined, {
    enabled: !!entityId,
  });
}

// ---------------------------------------------------------------------------
// New Issuance & Indices
// ---------------------------------------------------------------------------

export function useNewIssuance() {
  return useApiQuery(['fi', 'new-issues'], FI.newIssues);
}

export function useNewIssuancePipeline() {
  return useApiQuery(['fi', 'new-issues', 'pipeline'], FI.newIssuesPipeline);
}

export function useFIIndices() {
  return useApiQuery(['fi', 'indices'], FI.indices.list);
}

export function useFIIndexDetail(indexId: string | undefined) {
  return useApiQuery(['fi', 'indices', indexId], FI.indices.detail(indexId ?? ''), undefined, {
    enabled: !!indexId,
  });
}

export function useFIIndexConstituents(indexId: string | undefined) {
  return useApiQuery(['fi', 'indices', indexId, 'constituents'], FI.indices.constituents(indexId ?? ''), undefined, {
    enabled: !!indexId,
  });
}

export function useFIIndexReturns(indexId: string | undefined) {
  return useApiQuery(['fi', 'indices', indexId, 'returns'], FI.indices.returns(indexId ?? ''), undefined, {
    enabled: !!indexId,
  });
}

// ---------------------------------------------------------------------------
// Muni
// ---------------------------------------------------------------------------

export function useMuniBonds() {
  return useApiQuery(['fi', 'muni'], FI.muni.list);
}

export function useMuniDetail(cusip: string | undefined) {
  return useApiQuery(['fi', 'muni', cusip], FI.muni.detail(cusip ?? ''), undefined, {
    enabled: !!cusip,
  });
}

export function useMuniByState(state?: string) {
  return useApiQuery(['fi', 'muni', 'state', state], FI.muni.byState(state ?? ''), undefined, {
    enabled: !!state,
  });
}

export function useMuniYields() {
  return useApiQuery(['fi', 'muni', 'yields'], FI.muni.yields);
}

// ---------------------------------------------------------------------------
// Mortgage
// ---------------------------------------------------------------------------

export function useMortgagePools() {
  return useApiQuery(['fi', 'mortgage', 'pools'], FI.mortgage.pools);
}

export function useMortgagePrepayment(poolId: string | undefined) {
  return useApiQuery(['fi', 'mortgage', poolId, 'prepayment'], FI.mortgage.prepayment(poolId ?? ''), undefined, {
    enabled: !!poolId,
  });
}

export function useMortgageCashFlows(poolId: string | undefined) {
  return useApiQuery(['fi', 'mortgage', poolId, 'cash-flows'], FI.mortgage.cashFlows(poolId ?? ''), undefined, {
    enabled: !!poolId,
  });
}

// ---------------------------------------------------------------------------
// FI Analytics
// ---------------------------------------------------------------------------

export function useFIBondScreen() {
  return useApiQuery(['fi', 'screen', 'bonds'], FI.screen);
}

// FI Briefing (aggregated view)
export function useFIBriefing() {
  // Returns yield curve briefing as the primary FI briefing source
  return useApiQuery(['fi', 'briefing'], FI.yieldCurve.current);
}
