import { useApiQuery } from './useApi';
import {
  NEWS,
  ALERTS,
  FILING_INTELLIGENCE,
  GOVERNANCE,
  SENTIMENT,
  COMPETITIVE,
  INDUSTRY,
  GLOBAL,
  COMPANY_INTEL,
  EARNINGS,
  FI_INTELLIGENCE,
  RESEARCH,
  MACRO,
} from '@/api/endpoints';
import type {
  BalanceSheetRiskAssessment,
  BusinessModelAnalysis,
  CapitalAllocationAssessment,
  CompanyIntelligenceOverview,
  CostStructureResponse,
  ManagementQualityAssessment,
  MarginAnalysisResponse,
  MoatAssessment,
  PorterForcesResponse,
  RevenueDriversResponse,
  SWOTAssessment,
} from '@/types/intelligence';
import type {
  CompanyPrimer,
  InvestmentThesis,
  PrimerListSummary,
} from '@/types/research';

// ---------------------------------------------------------------------------
// Filing Intelligence
// ---------------------------------------------------------------------------

export function useFilingEvents(entityId: string | undefined) {
  return useApiQuery(['filings', entityId, 'events'], FILING_INTELLIGENCE.events(entityId!), undefined, {
    enabled: !!entityId,
  });
}

export function useFilingEventsToday() {
  return useApiQuery(['filings', 'events', 'today'], FILING_INTELLIGENCE.eventsToday);
}

export function useFilingDiffs(entityId: string | undefined) {
  return useApiQuery(['filings', entityId, 'diff'], FILING_INTELLIGENCE.diff(entityId!), undefined, {
    enabled: !!entityId,
  });
}

export function useEightKEvents(entityId: string | undefined) {
  return useApiQuery(['filings', entityId, 'events'], FILING_INTELLIGENCE.events(entityId!), undefined, {
    enabled: !!entityId,
  });
}

export function useFilingInsiders(entityId: string | undefined) {
  return useApiQuery(['filings', entityId, 'insiders'], FILING_INTELLIGENCE.insiders(entityId!), undefined, {
    enabled: !!entityId,
  });
}

export function useFilingRiskFactors(entityId: string | undefined) {
  return useApiQuery(['filings', entityId, 'risk-factors'], FILING_INTELLIGENCE.riskFactors(entityId!), undefined, {
    enabled: !!entityId,
  });
}

export function useFilingMDNA(entityId: string | undefined) {
  return useApiQuery(['filings', entityId, 'mdna'], FILING_INTELLIGENCE.mdna(entityId!), undefined, {
    enabled: !!entityId,
  });
}

// ---------------------------------------------------------------------------
// Governance & ESG
// ---------------------------------------------------------------------------

export function useGovernanceProxy(entityId: string | undefined) {
  return useApiQuery(['governance', entityId, 'proxy'], GOVERNANCE.proxy(entityId!), undefined, {
    enabled: !!entityId,
  });
}

export function useGovernanceCompensation(entityId: string | undefined) {
  return useApiQuery(['governance', entityId, 'compensation'], GOVERNANCE.compensation(entityId!), undefined, {
    enabled: !!entityId,
  });
}

export function useGovernance(entityId: string | undefined) {
  return useApiQuery(['governance', entityId], GOVERNANCE.governance(entityId!), undefined, {
    enabled: !!entityId,
  });
}

export function useGovernanceBoard(entityId: string | undefined) {
  return useApiQuery(['governance', entityId, 'board'], GOVERNANCE.board(entityId!), undefined, {
    enabled: !!entityId,
  });
}

export function useESG(entityId: string | undefined) {
  return useApiQuery(['governance', entityId, 'esg'], GOVERNANCE.esg(entityId!), undefined, {
    enabled: !!entityId,
  });
}

export function useESGScores(entityId: string | undefined) {
  return useApiQuery(['governance', entityId, 'esg', 'scores'], GOVERNANCE.esgScores(entityId!), undefined, {
    enabled: !!entityId,
  });
}

export function useESGHistory(entityId: string | undefined) {
  return useApiQuery(['governance', entityId, 'esg', 'history'], GOVERNANCE.esgHistory(entityId!), undefined, {
    enabled: !!entityId,
  });
}

export function useShareholderProposals(entityId: string | undefined) {
  return useApiQuery(['governance', entityId, 'proposals'], GOVERNANCE.shareholderProposals(entityId!), undefined, {
    enabled: !!entityId,
  });
}

// ---------------------------------------------------------------------------
// Sentiment
// ---------------------------------------------------------------------------

export function useSentiment(entityId: string | undefined) {
  return useApiQuery(['sentiment', entityId], SENTIMENT.byEntity(entityId!), undefined, {
    enabled: !!entityId,
  });
}

export function useSentimentHistory(entityId: string | undefined) {
  return useApiQuery(['sentiment', entityId, 'history'], SENTIMENT.history(entityId!), undefined, {
    enabled: !!entityId,
  });
}

export function useSentimentPeers(entityId: string | undefined) {
  return useApiQuery(['sentiment', entityId, 'peers'], SENTIMENT.peers(entityId!), undefined, {
    enabled: !!entityId,
  });
}

export function useSentimentAnomalies(entityId: string | undefined) {
  return useApiQuery(['sentiment', entityId, 'anomalies'], SENTIMENT.anomalies(entityId!), undefined, {
    enabled: !!entityId,
  });
}

export function useSocialSentiment(entityId: string | undefined) {
  return useApiQuery(['sentiment', entityId, 'social'], SENTIMENT.social(entityId!), undefined, {
    enabled: !!entityId,
  });
}

export function useAnalystConsensus(entityId: string | undefined) {
  return useApiQuery(['sentiment', entityId, 'analyst'], SENTIMENT.analystConsensus(entityId!), undefined, {
    enabled: !!entityId,
  });
}

export function usePriceTargets(entityId: string | undefined) {
  return useApiQuery(['sentiment', entityId, 'price-targets'], SENTIMENT.priceTargets(entityId!), undefined, {
    enabled: !!entityId,
  });
}

export function useOptionsFlow(entityId: string | undefined) {
  return useApiQuery(['sentiment', entityId, 'options-flow'], SENTIMENT.optionsFlow(entityId!), undefined, {
    enabled: !!entityId,
  });
}

export function useSectorSentiment() {
  return useApiQuery(['sentiment', 'sectors'], SENTIMENT.sectorSentiment);
}

export function useMarketSentiment() {
  return useApiQuery(['sentiment', 'market'], SENTIMENT.marketSentiment);
}

// ---------------------------------------------------------------------------
// Earnings
// ---------------------------------------------------------------------------

export function useEarningsTranscripts(entityId: string | undefined) {
  return useApiQuery(['earnings', entityId, 'transcripts'], EARNINGS.transcripts(entityId!), undefined, {
    enabled: !!entityId,
  });
}

export function useEarningsSurprises(entityId: string | undefined) {
  return useApiQuery(['earnings', entityId, 'surprises'], EARNINGS.surprises(entityId!), undefined, {
    enabled: !!entityId,
  });
}

export function useEarningsGuidance(entityId: string | undefined) {
  return useApiQuery(['earnings', entityId, 'guidance'], EARNINGS.guidance(entityId!), undefined, {
    enabled: !!entityId,
  });
}

export function useEarningsCalendar() {
  return useApiQuery(['earnings', 'calendar'], EARNINGS.calendar);
}

export function useEarningsQuality(entityId: string | undefined) {
  return useApiQuery(['earnings', entityId, 'quality'], EARNINGS.quality(entityId!), undefined, {
    enabled: !!entityId,
  });
}

export function useEarningsSeasonality(entityId: string | undefined) {
  return useApiQuery(['earnings', entityId, 'seasonality'], EARNINGS.seasonality(entityId!), undefined, {
    enabled: !!entityId,
  });
}

// ---------------------------------------------------------------------------
// Company Intelligence
// ---------------------------------------------------------------------------

export function useCompanyIntelligence(entityId: string | undefined) {
  return useApiQuery<CompanyIntelligenceOverview>(['intelligence', entityId], COMPANY_INTEL.overview(entityId!), undefined, {
    enabled: !!entityId,
  });
}

export function useBusinessModel(entityId: string | undefined) {
  return useApiQuery<BusinessModelAnalysis>(['intelligence', entityId, 'business-model'], COMPANY_INTEL.businessModel(entityId!), undefined, {
    enabled: !!entityId,
  });
}

export function useCapitalAllocation(entityId: string | undefined) {
  return useApiQuery<CapitalAllocationAssessment>(['intelligence', entityId, 'capital-allocation'], COMPANY_INTEL.capitalAllocation(entityId!), undefined, {
    enabled: !!entityId,
  });
}

export function useManagementIntel(entityId: string | undefined) {
  return useApiQuery<ManagementQualityAssessment>(['intelligence', entityId, 'management'], COMPANY_INTEL.management(entityId!), undefined, {
    enabled: !!entityId,
  });
}

export function useBalanceSheetRisk(entityId: string | undefined) {
  return useApiQuery<BalanceSheetRiskAssessment>(['intelligence', entityId, 'balance-sheet-risk'], COMPANY_INTEL.balanceSheetRisk(entityId!), undefined, {
    enabled: !!entityId,
  });
}

// The 8 hooks below (revenue-drivers/cost-structure/growth-profile/
// quality-metrics/risk-profile/operating-leverage/margin-analysis/
// working-capital) have NO backing route anywhere in src/api/routers/
// (verified by grep) -- not a path bug, a missing backend feature.
// `enabled: false` so they never fire a request against a path that will
// never resolve; remove the override once the corresponding backend
// endpoint actually exists.

// See RevenueDriversResponse in @/types/intelligence for the shape this
// hook expects once a real endpoint exists.
export function useRevenueDrivers(entityId: string | undefined) {
  return useApiQuery<RevenueDriversResponse>(['intelligence', entityId, 'revenue-drivers'], COMPANY_INTEL.revenueDrivers(entityId!), undefined, {
    enabled: false,
  });
}

// See CostStructureResponse in @/types/intelligence.
export function useCostStructure(entityId: string | undefined) {
  return useApiQuery<CostStructureResponse>(['intelligence', entityId, 'cost-structure'], COMPANY_INTEL.costStructure(entityId!), undefined, {
    enabled: false,
  });
}

export function useGrowthProfile(entityId: string | undefined) {
  return useApiQuery(['intelligence', entityId, 'growth-profile'], COMPANY_INTEL.growthProfile(entityId!), undefined, {
    enabled: false,
  });
}

export function useQualityMetrics(entityId: string | undefined) {
  return useApiQuery(['intelligence', entityId, 'quality-metrics'], COMPANY_INTEL.qualityMetrics(entityId!), undefined, {
    enabled: false,
  });
}

export function useRiskProfile(entityId: string | undefined) {
  return useApiQuery(['intelligence', entityId, 'risk-profile'], COMPANY_INTEL.riskProfile(entityId!), undefined, {
    enabled: false,
  });
}

export function useOperatingLeverage(entityId: string | undefined) {
  return useApiQuery(['intelligence', entityId, 'operating-leverage'], COMPANY_INTEL.operatingLeverage(entityId!), undefined, {
    enabled: false,
  });
}

// See MarginAnalysisResponse in @/types/intelligence.
export function useMarginAnalysis(entityId: string | undefined) {
  return useApiQuery<MarginAnalysisResponse>(['intelligence', entityId, 'margin-analysis'], COMPANY_INTEL.marginAnalysis(entityId!), undefined, {
    enabled: false,
  });
}

export function useWorkingCapital(entityId: string | undefined) {
  return useApiQuery(['intelligence', entityId, 'working-capital'], COMPANY_INTEL.workingCapital(entityId!), undefined, {
    enabled: false,
  });
}

// ---------------------------------------------------------------------------
// Competitive Intelligence
// ---------------------------------------------------------------------------

export function useMoatAssessment(entityId: string | undefined) {
  return useApiQuery<MoatAssessment>(['competitive', entityId, 'moat'], COMPETITIVE.moat(entityId!), undefined, {
    enabled: !!entityId,
  });
}

export function useCompetitiveLandscape(entityId: string | undefined) {
  return useApiQuery(['competitive', entityId, 'landscape'], COMPETITIVE.landscape(entityId!), undefined, {
    enabled: !!entityId,
  });
}

export function useCompetitivePeers(entityId: string | undefined) {
  return useApiQuery(['competitive', entityId, 'peers'], COMPETITIVE.peers(entityId!), undefined, {
    enabled: !!entityId,
  });
}

export function useMarketShare(entityId: string | undefined) {
  return useApiQuery(['competitive', entityId, 'market-share'], COMPETITIVE.marketShare(entityId!), undefined, {
    enabled: !!entityId,
  });
}

// NOTE: COMPETITIVE.swot has no backing route in src/api/routers/*.py yet
// (no SWOT schema/model exists anywhere in the backend) -- see
// SWOTAssessment in @/types/intelligence. `enabled: false` so this never
// fires a request against a path that will never resolve.
export function useSWOT(entityId: string | undefined) {
  return useApiQuery<SWOTAssessment>(['competitive', entityId, 'swot'], COMPETITIVE.swot(entityId!), undefined, {
    enabled: false,
  });
}

// NOTE: COMPETITIVE.porterForces has no backing route yet -- see
// PorterForcesResponse in @/types/intelligence.
export function usePorterForces(entityId: string | undefined) {
  return useApiQuery<PorterForcesResponse>(['competitive', entityId, 'porter'], COMPETITIVE.porterForces(entityId!), undefined, {
    enabled: false,
  });
}

// NOTE: COMPETITIVE.supplyChain has no backing route either -- unused today
// (no page calls this hook), disabled for the same reason as swot/porter.
export function useSupplyChain(entityId: string | undefined) {
  return useApiQuery(['competitive', entityId, 'supply-chain'], COMPETITIVE.supplyChain(entityId!), undefined, {
    enabled: false,
  });
}

export function useCustomers(entityId: string | undefined) {
  return useApiQuery(['competitive', entityId, 'customers'], COMPETITIVE.customers(entityId!), undefined, {
    enabled: !!entityId,
  });
}

export function useSuppliers(entityId: string | undefined) {
  return useApiQuery(['competitive', entityId, 'suppliers'], COMPETITIVE.suppliers(entityId!), undefined, {
    enabled: !!entityId,
  });
}

// ---------------------------------------------------------------------------
// Industry
// ---------------------------------------------------------------------------

export function useIndustryOverview(gicsCode: string | undefined) {
  return useApiQuery(['industry', gicsCode, 'overview'], INDUSTRY.overview(gicsCode!), undefined, {
    enabled: !!gicsCode,
  });
}

export function useIndustryEconomics(gicsCode: string | undefined) {
  return useApiQuery(['industry', gicsCode, 'economics'], INDUSTRY.economics(gicsCode!), undefined, {
    enabled: !!gicsCode,
  });
}

export function useIndustryCycle(gicsCode: string | undefined) {
  return useApiQuery(['industry', gicsCode, 'cycle'], INDUSTRY.cycle(gicsCode!), undefined, {
    enabled: !!gicsCode,
  });
}

export function useIndustryRankings() {
  return useApiQuery(['industry', 'rankings'], INDUSTRY.rankings);
}

export function useIndustryList() {
  return useApiQuery(['industry', 'list'], INDUSTRY.list);
}

export function useGICSTree() {
  return useApiQuery(['industry', 'gics'], INDUSTRY.gicsTree);
}

// ---------------------------------------------------------------------------
// Global / Macro
// ---------------------------------------------------------------------------

export function useCountryRisk(countryCode?: string) {
  return useApiQuery(['global', 'country-risk', countryCode], GLOBAL.countryRisk(countryCode!), undefined, {
    enabled: !!countryCode,
  });
}

export function useCountryDetail(countryCode?: string) {
  return useApiQuery(['global', 'country', countryCode], GLOBAL.countryDetail(countryCode!), undefined, {
    enabled: !!countryCode,
  });
}

export function useCountryEconomics(countryCode?: string) {
  return useApiQuery(['global', 'country', countryCode, 'economics'], GLOBAL.countryEconomics(countryCode!), undefined, {
    enabled: !!countryCode,
  });
}

export function useCountries() {
  return useApiQuery(['global', 'countries'], GLOBAL.countries);
}

export function useGeopoliticalEvents() {
  return useApiQuery(['global', 'events'], GLOBAL.events);
}

export function useMacroDashboard() {
  return useApiQuery(['global', 'macro', 'dashboard'], GLOBAL.macroDashboard);
}

export function useCentralBanks() {
  return useApiQuery(['global', 'central-banks'], GLOBAL.centralBanks);
}

export function useCentralBankDetail(bankId: string | undefined) {
  return useApiQuery(['global', 'central-banks', bankId], GLOBAL.centralBankDetail(bankId!), undefined, {
    enabled: !!bankId,
  });
}

export function useInflation() {
  return useApiQuery(['global', 'inflation'], GLOBAL.inflation);
}

export function useRecessionProbability() {
  return useApiQuery(['global', 'recession-prob'], GLOBAL.recessionProb);
}

export function useCommodities() {
  return useApiQuery(['global', 'commodities'], GLOBAL.commodities);
}

export function useCommodityDetail(symbol?: string) {
  return useApiQuery(['global', 'commodities', symbol], GLOBAL.commodityDetail(symbol!), undefined, {
    enabled: !!symbol,
  });
}

export function useCommodityPrices(symbol?: string) {
  return useApiQuery(['global', 'commodities', symbol, 'prices'], GLOBAL.commodityPrices(symbol!), undefined, {
    enabled: !!symbol,
  });
}

export function useFXRates() {
  return useApiQuery(['global', 'fx', 'rates'], GLOBAL.fxRates);
}

export function useFXHistory(pair?: string) {
  return useApiQuery(['global', 'fx', pair, 'history'], GLOBAL.fxHistory(pair!), undefined, {
    enabled: !!pair,
  });
}

export function useGlobalIndices() {
  return useApiQuery(['global', 'indices'], GLOBAL.globalIndices);
}

// ---------------------------------------------------------------------------
// News & Alerts
// ---------------------------------------------------------------------------

export function useNews(entityId?: string) {
  const path = entityId ? NEWS.byEntity(entityId) : NEWS.latest;
  return useApiQuery(['news', entityId ?? 'latest'], path, undefined, {
    enabled: true,
  });
}

export function useNewsTrending() {
  return useApiQuery(['news', 'trending'], NEWS.trending);
}

export function useAlerts() {
  return useApiQuery(['alerts'], ALERTS.list);
}

export function useAlertHistory() {
  return useApiQuery(['alerts', 'history'], ALERTS.history);
}

export function useAlertRules() {
  return useApiQuery(['alerts', 'rules'], ALERTS.rules);
}

// ---------------------------------------------------------------------------
// FI Intelligence
// ---------------------------------------------------------------------------

export function useYieldCurveBriefing() {
  return useApiQuery(['fi-intel', 'yield-curve-briefing'], FI_INTELLIGENCE.yieldCurveBriefing);
}

export function useCreditBriefing() {
  return useApiQuery(['fi-intel', 'credit-briefing'], FI_INTELLIGENCE.creditBriefing);
}

export function useFIIssuanceToday() {
  return useApiQuery(['fi-intel', 'issuance-today'], FI_INTELLIGENCE.issuanceToday);
}

export function useCrossAssetSignals() {
  return useApiQuery(['fi-intel', 'cross-asset'], FI_INTELLIGENCE.crossAssetSignals);
}

export function useIssuerCreditIntel(entityId: string | undefined) {
  return useApiQuery(['fi-intel', 'issuer-credit', entityId], FI_INTELLIGENCE.issuerCredit(entityId!), undefined, {
    enabled: !!entityId,
  });
}

export function useFIMarketConditions() {
  return useApiQuery(['fi-intel', 'market-conditions'], FI_INTELLIGENCE.marketConditions);
}

export function useFIFlowsAnalysis() {
  return useApiQuery(['fi-intel', 'flows'], FI_INTELLIGENCE.flowsAnalysis);
}

export function useFILiquidityIndex() {
  return useApiQuery(['fi-intel', 'liquidity-index'], FI_INTELLIGENCE.liquidityIndex);
}

export function useFITechnicalLevels() {
  return useApiQuery(['fi-intel', 'technical-levels'], FI_INTELLIGENCE.technicalLevels);
}

// ---------------------------------------------------------------------------
// Research (Pillar 3 Phase 4)
// ---------------------------------------------------------------------------

export function useCompanyPrimer(entityId: string | undefined) {
  return useApiQuery<CompanyPrimer>(['research', 'primers', entityId], RESEARCH.primers.byEntity(entityId!), undefined, {
    enabled: !!entityId,
  });
}

export function useRecentPrimers() {
  return useApiQuery<PrimerListSummary[]>(['research', 'primers', 'recent'], RESEARCH.primers.recent);
}

export function useMorningBriefing() {
  return useApiQuery(['research', 'briefings', 'today'], RESEARCH.briefings.today);
}

export function useBriefingHistory() {
  return useApiQuery(['research', 'briefings', 'history'], RESEARCH.briefings.history);
}

export function useBriefingPreferences() {
  return useApiQuery(['research', 'briefings', 'preferences'], RESEARCH.briefings.preferences);
}

export function useAnomalies() {
  return useApiQuery(['research', 'anomalies', 'active'], RESEARCH.anomalies.active);
}

export function useCriticalAnomalies() {
  return useApiQuery(['research', 'anomalies', 'critical'], RESEARCH.anomalies.critical);
}

export function useEntityAnomalies(entityId: string | undefined) {
  return useApiQuery(['research', 'anomalies', entityId], RESEARCH.anomalies.byEntity(entityId!), undefined, {
    enabled: !!entityId,
  });
}

export function useAnomalyHistory() {
  return useApiQuery(['research', 'anomalies', 'history'], RESEARCH.anomalies.history);
}

export function useResearchThemes() {
  return useApiQuery(['research', 'themes'], RESEARCH.themes.list);
}

export function useResearchTheme(themeId: string | undefined) {
  return useApiQuery(['research', 'themes', themeId], RESEARCH.themes.detail(themeId!), undefined, {
    enabled: !!themeId,
  });
}

export function useResearchNotes(entityId?: string) {
  const path = entityId ? RESEARCH.notes.byEntity(entityId) : RESEARCH.notes.list;
  return useApiQuery(['research', 'notes', entityId ?? 'all'], path);
}

export function useResearchThesis(entityId: string | undefined) {
  return useApiQuery<InvestmentThesis>(['research', 'thesis', entityId], RESEARCH.thesis.byEntity(entityId!), undefined, {
    enabled: !!entityId,
  });
}

// ---------------------------------------------------------------------------
// Macro & Economic Data
// ---------------------------------------------------------------------------

export function useMacroIndicators() {
  return useApiQuery(['macro', 'indicators'], MACRO.indicators);
}

export function useMacroIndicatorDetail(indicatorId: string | undefined) {
  return useApiQuery(['macro', 'indicators', indicatorId], MACRO.indicatorDetail(indicatorId!), undefined, {
    enabled: !!indicatorId,
  });
}

export function useMacroIndicatorHistory(indicatorId: string | undefined) {
  return useApiQuery(['macro', 'indicators', indicatorId, 'history'], MACRO.indicatorHistory(indicatorId!), undefined, {
    enabled: !!indicatorId,
  });
}

export function useMacroGDP() {
  return useApiQuery(['macro', 'gdp'], MACRO.gdp);
}

export function useMacroGDPByCountry(code?: string) {
  return useApiQuery(['macro', 'gdp', code], MACRO.gdpByCountry(code!), undefined, {
    enabled: !!code,
  });
}

export function useMacroPMI() {
  return useApiQuery(['macro', 'pmi'], MACRO.pmi);
}

export function useMacroConsumerConfidence() {
  return useApiQuery(['macro', 'consumer-confidence'], MACRO.consumerConfidence);
}

export function useMacroDashboardData() {
  return useApiQuery(['macro', 'dashboard'], MACRO.dashboard);
}
