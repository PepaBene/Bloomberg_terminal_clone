import { useApiQuery } from './useApi';
import { FI } from '@/api/endpoints';

// [P1-F-013 fix] Explicit per-hook staleTime, matching the pattern already
// used by the sibling `frontend/src/api/hooks/useFiBonds.ts` (and
// useFiTreasuries/useFiCredit/useFiIntelligence) instead of relying solely
// on the global 5-minute QueryClient default. Reference/slow-changing data
// (ratings, cash-flow schedules, covenants, historical series) gets the
// longer STALE_24H; more dynamic/market-priced data (current curves,
// intraday-ish prices, spreads, CDS, index returns) gets the shorter
// STALE_1H.
const STALE_24H = 24 * 60 * 60 * 1000;
const STALE_1H = 60 * 60 * 1000;

// ---------------------------------------------------------------------------
// Yield Curve
// ---------------------------------------------------------------------------

export function useYieldCurve() {
  return useApiQuery(['fi', 'yield-curve'], FI.yieldCurve.current, undefined, {
    staleTime: STALE_1H,
  });
}

export function useYieldCurveSpreads() {
  return useApiQuery(['fi', 'yield-curve', 'spreads'], FI.yieldCurve.spreads, undefined, {
    staleTime: STALE_1H,
  });
}

export function useYieldCurveHistory() {
  return useApiQuery(['fi', 'yield-curve', 'history'], FI.yieldCurve.history, undefined, {
    staleTime: STALE_24H,
  });
}

export function useYieldCurveForward() {
  return useApiQuery(['fi', 'yield-curve', 'forward'], FI.yieldCurve.forward, undefined, {
    staleTime: STALE_1H,
  });
}

export function useRealYieldCurve() {
  return useApiQuery(['fi', 'yield-curve', 'real'], FI.yieldCurve.real, undefined, {
    staleTime: STALE_1H,
  });
}

export function useBreakevenCurve() {
  return useApiQuery(['fi', 'yield-curve', 'breakeven'], FI.yieldCurve.breakeven, undefined, {
    staleTime: STALE_1H,
  });
}

export function useSwapCurve() {
  return useApiQuery(['fi', 'yield-curve', 'swap'], FI.yieldCurve.swap, undefined, {
    staleTime: STALE_1H,
  });
}

export function useSovereignCurve(countryCode?: string) {
  return useApiQuery(['fi', 'yield-curve', 'sovereign', countryCode], FI.yieldCurve.sovereign(countryCode ?? ''), undefined, {
    enabled: !!countryCode,
    staleTime: STALE_1H,
  });
}

// ---------------------------------------------------------------------------
// Treasuries
// ---------------------------------------------------------------------------

export function useTreasuries() {
  return useApiQuery(['fi', 'treasuries'], FI.treasuries.list, undefined, {
    staleTime: STALE_1H,
  });
}

export function useTreasuryDetail(cusip: string | undefined) {
  return useApiQuery(['fi', 'treasuries', cusip], FI.treasuries.detail(cusip ?? ''), undefined, {
    enabled: !!cusip,
    staleTime: STALE_1H,
  });
}

export function useTreasuriesOnTheRun() {
  return useApiQuery(['fi', 'treasuries', 'on-the-run'], FI.treasuries.onTheRun, undefined, {
    staleTime: STALE_1H,
  });
}

export function useTreasuryAuction() {
  return useApiQuery(['fi', 'treasuries', 'auction'], FI.treasuries.auction, undefined, {
    staleTime: STALE_24H,
  });
}

export function useTreasuryAuctionHistory() {
  return useApiQuery(['fi', 'treasuries', 'auction', 'history'], FI.treasuries.auctionHistory, undefined, {
    staleTime: STALE_24H,
  });
}

// ---------------------------------------------------------------------------
// Bonds
// ---------------------------------------------------------------------------

export function useBondDetail(id: string | undefined) {
  return useApiQuery(['fi', 'bonds', id], FI.bonds.detail(id ?? ''), undefined, {
    enabled: !!id,
    staleTime: STALE_24H,
  });
}

export function useBondPrices(cusip: string | undefined) {
  return useApiQuery(['fi', 'bonds', cusip, 'prices'], FI.bonds.prices(cusip ?? ''), undefined, {
    enabled: !!cusip,
    staleTime: STALE_1H,
  });
}

export function useBondSpreads(cusip: string | undefined) {
  return useApiQuery(['fi', 'bonds', cusip, 'spreads'], FI.bonds.spreads(cusip ?? ''), undefined, {
    enabled: !!cusip,
    staleTime: STALE_1H,
  });
}

export function useBondsByIssuer(entityId: string | undefined) {
  return useApiQuery(['fi', 'bonds', 'issuer', entityId], FI.bonds.byIssuer(entityId ?? ''), undefined, {
    enabled: !!entityId,
    staleTime: STALE_24H,
  });
}

export function useBondCashFlows(cusip: string | undefined) {
  return useApiQuery(['fi', 'bonds', cusip, 'cash-flows'], FI.bonds.cashFlows(cusip ?? ''), undefined, {
    enabled: !!cusip,
    staleTime: STALE_24H,
  });
}

export function useBondCallSchedule(cusip: string | undefined) {
  return useApiQuery(['fi', 'bonds', cusip, 'call-schedule'], FI.bonds.callSchedule(cusip ?? ''), undefined, {
    enabled: !!cusip,
    staleTime: STALE_24H,
  });
}

export function useBondCovenants(cusip: string | undefined) {
  return useApiQuery(['fi', 'bonds', cusip, 'covenants'], FI.bonds.covenants(cusip ?? ''), undefined, {
    enabled: !!cusip,
    staleTime: STALE_24H,
  });
}

export function useBondComparables(cusip: string | undefined) {
  return useApiQuery(['fi', 'bonds', cusip, 'comparables'], FI.bonds.comparables(cusip ?? ''), undefined, {
    enabled: !!cusip,
    staleTime: STALE_1H,
  });
}

export function useBondSearch(query: string) {
  return useApiQuery(['fi', 'bonds', 'search', query], FI.bonds.search, { q: query }, {
    enabled: query.length >= 2,
    staleTime: STALE_1H,
  });
}

// ---------------------------------------------------------------------------
// Ratings
// ---------------------------------------------------------------------------

export function useCreditRatings(entityId: string | undefined) {
  return useApiQuery(['fi', 'ratings', entityId], FI.ratings.byEntity(entityId ?? ''), undefined, {
    enabled: !!entityId,
    staleTime: STALE_24H,
  });
}

export function useCreditRatingsHistory(entityId: string | undefined) {
  return useApiQuery(['fi', 'ratings', entityId, 'history'], FI.ratings.history(entityId ?? ''), undefined, {
    enabled: !!entityId,
    staleTime: STALE_24H,
  });
}

export function useRecentRatingChanges() {
  return useApiQuery(['fi', 'ratings', 'changes'], FI.ratings.recentChanges, undefined, {
    staleTime: STALE_1H,
  });
}

export function useRatingDistribution() {
  return useApiQuery(['fi', 'ratings', 'distribution'], FI.ratings.distribution, undefined, {
    staleTime: STALE_24H,
  });
}

export function useTransitionMatrix() {
  return useApiQuery(['fi', 'ratings', 'transition-matrix'], FI.ratings.transitionMatrix, undefined, {
    staleTime: STALE_24H,
  });
}

export function useRatingOutlook(entityId: string | undefined) {
  return useApiQuery(['fi', 'ratings', entityId, 'outlook'], FI.ratings.outlook(entityId ?? ''), undefined, {
    enabled: !!entityId,
    staleTime: STALE_24H,
  });
}

// ---------------------------------------------------------------------------
// Credit
// ---------------------------------------------------------------------------

export function useCreditScore(entityId: string | undefined) {
  return useApiQuery(['fi', 'credit', entityId, 'score'], FI.credit.score(entityId ?? ''), undefined, {
    enabled: !!entityId,
    staleTime: STALE_24H,
  });
}

export function useCreditRatios(entityId: string | undefined) {
  return useApiQuery(['fi', 'credit', entityId, 'ratios'], FI.credit.ratios(entityId ?? ''), undefined, {
    enabled: !!entityId,
    staleTime: STALE_24H,
  });
}

export function useCreditPeers(entityId: string | undefined) {
  return useApiQuery(['fi', 'credit', entityId, 'peers'], FI.credit.peers(entityId ?? ''), undefined, {
    enabled: !!entityId,
    staleTime: STALE_24H,
  });
}

export function useCreditTrend(entityId: string | undefined) {
  return useApiQuery(['fi', 'credit', entityId, 'trend'], FI.credit.trend(entityId ?? ''), undefined, {
    enabled: !!entityId,
    staleTime: STALE_24H,
  });
}

export function useCreditSpreads() {
  return useApiQuery(['fi', 'credit', 'sector-spreads'], FI.credit.sectorSpreads, undefined, {
    staleTime: STALE_1H,
  });
}

export function useDistressedCredit() {
  return useApiQuery(['fi', 'credit', 'distressed'], FI.credit.distressed, undefined, {
    staleTime: STALE_1H,
  });
}

export function useDefaultProbability(entityId: string | undefined) {
  return useApiQuery(['fi', 'credit', entityId, 'default-prob'], FI.credit.defaultProbability(entityId ?? ''), undefined, {
    enabled: !!entityId,
    staleTime: STALE_24H,
  });
}

export function useRecoveryRate(entityId: string | undefined) {
  return useApiQuery(['fi', 'credit', entityId, 'recovery-rate'], FI.credit.recoveryRate(entityId ?? ''), undefined, {
    enabled: !!entityId,
    staleTime: STALE_24H,
  });
}

export function useCDS(entityId: string | undefined) {
  return useApiQuery(['fi', 'credit', entityId, 'cds'], FI.credit.cds(entityId ?? ''), undefined, {
    enabled: !!entityId,
    staleTime: STALE_1H,
  });
}

export function useCDSCurve(entityId: string | undefined) {
  return useApiQuery(['fi', 'credit', entityId, 'cds', 'curve'], FI.credit.cdsCurve(entityId ?? ''), undefined, {
    enabled: !!entityId,
    staleTime: STALE_1H,
  });
}

// ---------------------------------------------------------------------------
// New Issuance & Indices
// ---------------------------------------------------------------------------

export function useNewIssuance() {
  return useApiQuery(['fi', 'new-issues'], FI.newIssues, undefined, {
    staleTime: STALE_1H,
  });
}

export function useNewIssuancePipeline() {
  return useApiQuery(['fi', 'new-issues', 'pipeline'], FI.newIssuesPipeline, undefined, {
    staleTime: STALE_24H,
  });
}

export function useFIIndices() {
  return useApiQuery(['fi', 'indices'], FI.indices.list, undefined, {
    staleTime: STALE_1H,
  });
}

export function useFIIndexDetail(indexId: string | undefined) {
  return useApiQuery(['fi', 'indices', indexId], FI.indices.detail(indexId ?? ''), undefined, {
    enabled: !!indexId,
    staleTime: STALE_1H,
  });
}

export function useFIIndexConstituents(indexId: string | undefined) {
  return useApiQuery(['fi', 'indices', indexId, 'constituents'], FI.indices.constituents(indexId ?? ''), undefined, {
    enabled: !!indexId,
    staleTime: STALE_1H,
  });
}

export function useFIIndexReturns(indexId: string | undefined) {
  return useApiQuery(['fi', 'indices', indexId, 'returns'], FI.indices.returns(indexId ?? ''), undefined, {
    enabled: !!indexId,
    staleTime: STALE_1H,
  });
}

// ---------------------------------------------------------------------------
// Muni
// ---------------------------------------------------------------------------

export function useMuniBonds() {
  return useApiQuery(['fi', 'muni'], FI.muni.list, undefined, {
    staleTime: STALE_24H,
  });
}

export function useMuniDetail(cusip: string | undefined) {
  return useApiQuery(['fi', 'muni', cusip], FI.muni.detail(cusip ?? ''), undefined, {
    enabled: !!cusip,
    staleTime: STALE_24H,
  });
}

export function useMuniByState(state?: string) {
  return useApiQuery(['fi', 'muni', 'state', state], FI.muni.byState(state ?? ''), undefined, {
    enabled: !!state,
    staleTime: STALE_24H,
  });
}

export function useMuniYields() {
  return useApiQuery(['fi', 'muni', 'yields'], FI.muni.yields, undefined, {
    staleTime: STALE_1H,
  });
}

// ---------------------------------------------------------------------------
// Mortgage
// ---------------------------------------------------------------------------

export function useMortgagePools() {
  return useApiQuery(['fi', 'mortgage', 'pools'], FI.mortgage.pools, undefined, {
    staleTime: STALE_24H,
  });
}

export function useMortgagePrepayment(poolId: string | undefined) {
  return useApiQuery(['fi', 'mortgage', poolId, 'prepayment'], FI.mortgage.prepayment(poolId ?? ''), undefined, {
    enabled: !!poolId,
    staleTime: STALE_24H,
  });
}

export function useMortgageCashFlows(poolId: string | undefined) {
  return useApiQuery(['fi', 'mortgage', poolId, 'cash-flows'], FI.mortgage.cashFlows(poolId ?? ''), undefined, {
    enabled: !!poolId,
    staleTime: STALE_24H,
  });
}

// ---------------------------------------------------------------------------
// FI Analytics
// ---------------------------------------------------------------------------

export function useFIBondScreen() {
  return useApiQuery(['fi', 'screen', 'bonds'], FI.screen, undefined, {
    staleTime: STALE_1H,
  });
}

// FI Briefing (aggregated view)
export function useFIBriefing() {
  // Returns yield curve briefing as the primary FI briefing source
  return useApiQuery(['fi', 'briefing'], FI.yieldCurve.current, undefined, {
    staleTime: STALE_1H,
  });
}
