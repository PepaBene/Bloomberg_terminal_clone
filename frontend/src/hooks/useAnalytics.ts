import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useApiQuery, useApiMutation } from './useApi';
import api from '@/api/client';
import { ANALYTICS } from '@/api/endpoints';

// ---------------------------------------------------------------------------
// Core scoring hooks
// ---------------------------------------------------------------------------

export function useCompositeScores(secId: string | undefined) {
  return useApiQuery(['analytics', secId, 'scores'], ANALYTICS.compositeScores(secId!), undefined, {
    enabled: !!secId,
  });
}

export function useAllScores(secId: string | undefined) {
  return useApiQuery(['analytics', secId, 'scores', 'all'], ANALYTICS.allScores(secId!), undefined, {
    enabled: !!secId,
  });
}

export function useQualityScore(secId: string | undefined) {
  return useApiQuery(['analytics', secId, 'quality'], ANALYTICS.qualityScore(secId!), undefined, {
    enabled: !!secId,
  });
}

export function useValueScore(secId: string | undefined) {
  return useApiQuery(['analytics', secId, 'value'], ANALYTICS.valueScore(secId!), undefined, {
    enabled: !!secId,
  });
}

export function useGrowthScore(secId: string | undefined) {
  return useApiQuery(['analytics', secId, 'growth'], ANALYTICS.growthScore(secId!), undefined, {
    enabled: !!secId,
  });
}

export function useMomentumScore(secId: string | undefined) {
  return useApiQuery(['analytics', secId, 'momentum'], ANALYTICS.momentumScore(secId!), undefined, {
    enabled: !!secId,
  });
}

export function useVolatilityScore(secId: string | undefined) {
  return useApiQuery(['analytics', secId, 'volatility'], ANALYTICS.volatilityScore(secId!), undefined, {
    enabled: !!secId,
  });
}

// ---------------------------------------------------------------------------
// Individual quality scores (Piotroski, Altman, Beneish)
// ---------------------------------------------------------------------------

export function usePiotroskiScore(secId: string | undefined) {
  return useApiQuery(['analytics', secId, 'piotroski'], ANALYTICS.piotroski(secId!), undefined, {
    enabled: !!secId,
  });
}

export function useAltmanScore(secId: string | undefined) {
  return useApiQuery(['analytics', secId, 'altman'], ANALYTICS.altman(secId!), undefined, {
    enabled: !!secId,
  });
}

export function useBeneishScore(secId: string | undefined) {
  return useApiQuery(['analytics', secId, 'beneish'], ANALYTICS.beneish(secId!), undefined, {
    enabled: !!secId,
  });
}

export function useScoreHistory(secId: string | undefined) {
  return useApiQuery(['analytics', secId, 'score-history'], ANALYTICS.scoreHistory(secId!), undefined, {
    enabled: !!secId,
  });
}

// ---------------------------------------------------------------------------
// Ratio & DuPont analysis
// ---------------------------------------------------------------------------

export function useAnalyticsRatios(secId: string | undefined) {
  return useApiQuery(['analytics', secId, 'ratios'], ANALYTICS.ratios(secId!), undefined, {
    enabled: !!secId,
  });
}

export function useDuPont(secId: string | undefined) {
  return useApiQuery(['analytics', secId, 'dupont'], ANALYTICS.dupont(secId!), undefined, {
    enabled: !!secId,
  });
}

export function useDuPontHistory(secId: string | undefined) {
  return useApiQuery(['analytics', secId, 'dupont', 'history'], ANALYTICS.dupontHistory(secId!), undefined, {
    enabled: !!secId,
  });
}

// ---------------------------------------------------------------------------
// Multiples & valuation
// ---------------------------------------------------------------------------

export function useMultiplesHistory(secId: string | undefined) {
  return useApiQuery(['analytics', secId, 'multiples'], ANALYTICS.multiplesHistory(secId!), undefined, {
    enabled: !!secId,
  });
}

export function useHistoricalMultiples(secId: string | undefined) {
  return useApiQuery(['analytics', secId, 'historical-multiples'], ANALYTICS.historicalMultiples(secId!), undefined, {
    enabled: !!secId,
  });
}

export function useFairValue(secId: string | undefined) {
  return useApiQuery(['analytics', secId, 'fair-value'], ANALYTICS.fairValue(secId!), undefined, {
    enabled: !!secId,
  });
}

// ---------------------------------------------------------------------------
// WACC
// ---------------------------------------------------------------------------

export function useWacc(secId: string | undefined) {
  return useApiQuery(['analytics', secId, 'wacc'], ANALYTICS.wacc(secId!), undefined, {
    enabled: !!secId,
  });
}

export function useWaccHistory(secId: string | undefined) {
  return useApiQuery(['analytics', secId, 'wacc', 'history'], ANALYTICS.waccHistory(secId!), undefined, {
    enabled: !!secId,
  });
}

export function useWaccComponents(secId: string | undefined) {
  return useApiQuery(['analytics', secId, 'wacc', 'components'], ANALYTICS.waccComponents(secId!), undefined, {
    enabled: !!secId,
  });
}

// ---------------------------------------------------------------------------
// TTM Metrics
// ---------------------------------------------------------------------------

export function useTTM(secId: string | undefined) {
  return useApiQuery(['analytics', secId, 'ttm'], ANALYTICS.ttm(secId!), undefined, {
    enabled: !!secId,
  });
}

// ---------------------------------------------------------------------------
// Comps / Comparable Analysis
// ---------------------------------------------------------------------------

export function useComps(secId: string | undefined) {
  return useApiQuery(['analytics', secId, 'comps'], ANALYTICS.comps(secId!), undefined, {
    enabled: !!secId,
  });
}

export function useCompsSummary(secId: string | undefined) {
  return useApiQuery(['analytics', secId, 'comps', 'summary'], ANALYTICS.compsSummary(secId!), undefined, {
    enabled: !!secId,
  });
}

// ---------------------------------------------------------------------------
// Industry KPIs
// ---------------------------------------------------------------------------

export function useIndustryKpis(secId: string | undefined) {
  return useApiQuery(['analytics', secId, 'kpis'], ANALYTICS.industryKpis(secId!), undefined, {
    enabled: !!secId,
  });
}

// ---------------------------------------------------------------------------
// Trends
// ---------------------------------------------------------------------------

export function useTrends(secId: string | undefined) {
  return useApiQuery(['analytics', secId, 'trends'], ANALYTICS.trends(secId!), undefined, {
    enabled: !!secId,
  });
}

// ---------------------------------------------------------------------------
// Peer analysis
// ---------------------------------------------------------------------------

export function usePeerGroup(secId: string | undefined) {
  return useApiQuery(['analytics', secId, 'peer-group'], ANALYTICS.peerGroup(secId!), undefined, {
    enabled: !!secId,
  });
}

export function usePeerComparison(secId: string | undefined) {
  return useApiQuery(['analytics', secId, 'peers'], ANALYTICS.peerComparison(secId!), undefined, {
    enabled: !!secId,
  });
}

export function usePeerRanking(secId: string | undefined) {
  return useApiQuery(['analytics', secId, 'peer-ranking'], ANALYTICS.peerRanking(secId!), undefined, {
    enabled: !!secId,
  });
}

export function useSavePeerGroup(securityId: string | undefined) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (peerIds: string[]) =>
      api.post(ANALYTICS.peerCustomSave(securityId!), { peer_ids: peerIds }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['analytics', 'peers'] });
    },
  });
}

export function useSectorRelative(secId: string | undefined) {
  return useApiQuery(['analytics', secId, 'sector-relative'], ANALYTICS.sectorRelative(secId!), undefined, {
    enabled: !!secId,
  });
}

// ---------------------------------------------------------------------------
// DCF & valuation models
// ---------------------------------------------------------------------------

export function useDCFModel(secId: string | undefined) {
  return useApiQuery(['analytics', secId, 'dcf'], ANALYTICS.dcf(secId!), undefined, {
    enabled: !!secId,
  });
}

export function useDCFSensitivity(secId: string | undefined) {
  return useApiQuery(['analytics', secId, 'dcf', 'sensitivity'], ANALYTICS.dcfSensitivity(secId!), undefined, {
    enabled: !!secId,
  });
}

export function useFootballField(secId: string | undefined) {
  return useApiQuery(['analytics', secId, 'football-field'], ANALYTICS.footballField(secId!), undefined, {
    enabled: !!secId,
  });
}

// ---------------------------------------------------------------------------
// Technical & factor
// ---------------------------------------------------------------------------

export function useTechnicalSignals(secId: string | undefined) {
  return useApiQuery(['analytics', secId, 'technical-signals'], ANALYTICS.technicalSignals(secId!), undefined, {
    enabled: !!secId,
  });
}

export function useSeasonality(secId: string | undefined) {
  return useApiQuery(['analytics', secId, 'seasonality'], ANALYTICS.seasonality(secId!), undefined, {
    enabled: !!secId,
  });
}

export function useFactorExposure(secId: string | undefined) {
  return useApiQuery(['analytics', secId, 'factor-exposure'], ANALYTICS.factorExposure(secId!), undefined, {
    enabled: !!secId,
  });
}

// ---------------------------------------------------------------------------
// Screening
// ---------------------------------------------------------------------------

export function useScreener(filters?: Record<string, unknown>) {
  return useApiQuery(
    ['analytics', 'screen', JSON.stringify(filters)],
    ANALYTICS.screen,
    undefined,
    { enabled: !!filters }
  );
}

export function useRunScreen() {
  return useApiMutation<any, any>(ANALYTICS.screen);
}

export function useSaveScreen() {
  return useApiMutation<any, any>(ANALYTICS.screenSave, [['analytics', 'screen', 'history']]);
}

export function useScreenFields() {
  return useApiQuery(['analytics', 'screen', 'fields'], ANALYTICS.screenFields);
}

export function useScreenPrebuilt() {
  return useApiQuery(['analytics', 'screen', 'prebuilt'], ANALYTICS.screenPrebuilt);
}

export function useScreenHistory() {
  return useApiQuery(['analytics', 'screen', 'history'], ANALYTICS.screenHistory);
}

// ---------------------------------------------------------------------------
// Correlation
// ---------------------------------------------------------------------------

export function useCorrelation() {
  return useApiQuery(['analytics', 'correlation'], ANALYTICS.correlation);
}
