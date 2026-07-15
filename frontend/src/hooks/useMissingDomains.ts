// ---------------------------------------------------------------------------
// Missing domain hooks — Phase 0 infrastructure
// Capital Structure, Debt Maturity, Corporate Actions, IPO, Fund Holdings,
// Money Market, Exports
// ---------------------------------------------------------------------------
import { useApiQuery, useApiMutation } from './useApi';
import {
  CAPITAL_STRUCTURE,
  DEBT_MATURITY,
  CORPORATE_ACTIONS,
  IPO,
  FUND_HOLDINGS,
  MONEY_MARKET,
  EXPORTS,
  DEALS,
  BACKTESTING,
  FI_AGENCY,
  CUSTOM_CLASSIFICATIONS,
} from '@/api/endpoints';

// ---------------------------------------------------------------------------
// Capital Structure
// ---------------------------------------------------------------------------

export function useCapitalStructure(entityId: string | undefined) {
  return useApiQuery(['capitalStructure', entityId], CAPITAL_STRUCTURE.overview(entityId!), undefined, {
    enabled: !!entityId,
  });
}

export function useCapitalStructureDebt(entityId: string | undefined) {
  return useApiQuery(['capitalStructure', entityId, 'debt'], CAPITAL_STRUCTURE.debtBreakdown(entityId!), undefined, {
    enabled: !!entityId,
  });
}

export function useCapitalStructureEquity(entityId: string | undefined) {
  return useApiQuery(['capitalStructure', entityId, 'equity'], CAPITAL_STRUCTURE.equityBreakdown(entityId!), undefined, {
    enabled: !!entityId,
  });
}

export function useCapitalStructureHistory(entityId: string | undefined) {
  return useApiQuery(['capitalStructure', entityId, 'history'], CAPITAL_STRUCTURE.history(entityId!), undefined, {
    enabled: !!entityId,
  });
}

// ---------------------------------------------------------------------------
// Debt Maturity
// ---------------------------------------------------------------------------

export function useDebtMaturity(entityId: string | undefined) {
  return useApiQuery(['debtMaturity', entityId], DEBT_MATURITY.profile(entityId!), undefined, {
    enabled: !!entityId,
  });
}

export function useDebtMaturitySchedule(entityId: string | undefined) {
  return useApiQuery(['debtMaturity', entityId, 'schedule'], DEBT_MATURITY.schedule(entityId!), undefined, {
    enabled: !!entityId,
  });
}

export function useRefinancingRisk(entityId: string | undefined) {
  return useApiQuery(['debtMaturity', entityId, 'refinancingRisk'], DEBT_MATURITY.refinancingRisk(entityId!), undefined, {
    enabled: !!entityId,
  });
}

// ---------------------------------------------------------------------------
// Corporate Actions
// ---------------------------------------------------------------------------

export function useCorporateActions(entityId: string | undefined) {
  return useApiQuery(['corporateActions', entityId], CORPORATE_ACTIONS.byEntity(entityId!), undefined, {
    enabled: !!entityId,
  });
}

export function useCorporateActionsCalendar() {
  return useApiQuery(['corporateActions', 'calendar'], CORPORATE_ACTIONS.calendar);
}

export function useCorporateActionsUpcoming() {
  return useApiQuery(['corporateActions', 'upcoming'], CORPORATE_ACTIONS.upcoming);
}

// ---------------------------------------------------------------------------
// IPO
// ---------------------------------------------------------------------------

export function useIpoUpcoming() {
  return useApiQuery(['ipo', 'upcoming'], IPO.upcoming);
}

export function useIpoRecent() {
  return useApiQuery(['ipo', 'recent'], IPO.recent);
}

export function useIpoDetail(ipoId: string | undefined) {
  return useApiQuery(['ipo', ipoId], IPO.detail(ipoId!), undefined, {
    enabled: !!ipoId,
  });
}

export function useIpoPipeline() {
  return useApiQuery(['ipo', 'pipeline'], IPO.pipeline);
}

export function useIpoPerformance() {
  return useApiQuery(['ipo', 'performance'], IPO.performance);
}

export function useIpoCalendar() {
  return useApiQuery(['ipo', 'calendar'], IPO.calendar);
}

// ---------------------------------------------------------------------------
// Fund Holdings
// ---------------------------------------------------------------------------

export function useFundHoldings(fundId: string | undefined) {
  return useApiQuery(['fundHoldings', fundId], FUND_HOLDINGS.byFund(fundId!), undefined, {
    enabled: !!fundId,
  });
}

export function useFundNPort(fundId: string | undefined) {
  return useApiQuery(['fundHoldings', fundId, 'nPort'], FUND_HOLDINGS.nPort(fundId!), undefined, {
    enabled: !!fundId,
  });
}

export function useFundTopHoldings(fundId: string | undefined) {
  return useApiQuery(['fundHoldings', fundId, 'top'], FUND_HOLDINGS.topHoldings(fundId!), undefined, {
    enabled: !!fundId,
  });
}

export function useFundSectorAllocation(fundId: string | undefined) {
  return useApiQuery(['fundHoldings', fundId, 'sectors'], FUND_HOLDINGS.sectorAllocation(fundId!), undefined, {
    enabled: !!fundId,
  });
}

// ---------------------------------------------------------------------------
// Money Market
// ---------------------------------------------------------------------------

export function useMoneyMarketRates() {
  return useApiQuery(['moneyMarket', 'rates'], MONEY_MARKET.rates);
}

export function useMoneyMarketSOFR() {
  return useApiQuery(['moneyMarket', 'sofr'], MONEY_MARKET.sofr);
}

export function useMoneyMarketEFFR() {
  return useApiQuery(['moneyMarket', 'effr'], MONEY_MARKET.effr);
}

export function useMoneyMarketRepo() {
  return useApiQuery(['moneyMarket', 'repo'], MONEY_MARKET.repoRates);
}

export function useMoneyMarketTBills() {
  return useApiQuery(['moneyMarket', 'tBills'], MONEY_MARKET.tBills);
}

export function useMoneyMarketHistory(rateType: string) {
  return useApiQuery(['moneyMarket', rateType, 'history'], MONEY_MARKET.history(rateType));
}

// ---------------------------------------------------------------------------
// Exports / Reports
// ---------------------------------------------------------------------------

export function useExportTemplates() {
  return useApiQuery(['exports', 'templates'], EXPORTS.templates);
}

export function useExportTemplate(templateId: string | undefined) {
  return useApiQuery(['exports', 'templates', templateId], EXPORTS.templateDetail(templateId!), undefined, {
    enabled: !!templateId,
  });
}

export function useScheduledReports() {
  return useApiQuery(['exports', 'scheduled'], EXPORTS.scheduledReports);
}

export function useGenerateReport() {
  return useApiMutation(EXPORTS.generateReport, [['exports']]);
}

export function useExportCsv() {
  return useApiMutation(EXPORTS.exportCsv);
}

export function useExportExcel() {
  return useApiMutation(EXPORTS.exportExcel);
}

export function useExportPdf() {
  return useApiMutation(EXPORTS.exportPdf);
}

// ---------------------------------------------------------------------------
// M&A / Deals
// ---------------------------------------------------------------------------

export function useDeals() {
  return useApiQuery(['deals'], DEALS.list);
}

export function useDealDetail(dealId: string | undefined) {
  return useApiQuery(['deals', dealId], DEALS.detail(dealId!), undefined, {
    enabled: !!dealId,
  });
}

export function useDealsPipeline() {
  return useApiQuery(['deals', 'pipeline'], DEALS.pipeline);
}

export function useDealsCompleted() {
  return useApiQuery(['deals', 'completed'], DEALS.completed);
}

export function useDealsRumored() {
  return useApiQuery(['deals', 'rumored'], DEALS.rumored);
}

export function useDealsStatistics() {
  return useApiQuery(['deals', 'statistics'], DEALS.statistics);
}

export function useDealsByEntity(entityId: string | undefined) {
  return useApiQuery(['deals', 'entity', entityId], DEALS.byEntity(entityId!), undefined, {
    enabled: !!entityId,
  });
}

// ---------------------------------------------------------------------------
// Backtesting
// ---------------------------------------------------------------------------

export function useBacktestStrategies() {
  return useApiQuery(['backtest', 'strategies'], BACKTESTING.strategies);
}

export function useBacktestResult(backtestId: string | undefined) {
  return useApiQuery(['backtest', backtestId], BACKTESTING.result(backtestId!), undefined, {
    enabled: !!backtestId,
  });
}

// [P4-F-017 fix] No "list all backtest runs" endpoint exists anywhere in
// src/api/routers/backtesting.py (verified by grep) -- disabled rather than
// firing a request against a path that will never resolve.
export function useBacktestHistory() {
  return useApiQuery(['backtest', 'history'], BACKTESTING.history, undefined, {
    enabled: false,
  });
}

export function useRunBacktest() {
  return useApiMutation(BACKTESTING.run, [['backtest']]);
}

// ---------------------------------------------------------------------------
// FI Agency Bonds
// ---------------------------------------------------------------------------

export function useAgencyBonds() {
  return useApiQuery(['fi', 'agency'], FI_AGENCY.list);
}

export function useAgencyBondDetail(cusip: string | undefined) {
  return useApiQuery(['fi', 'agency', cusip], FI_AGENCY.detail(cusip!), undefined, {
    enabled: !!cusip,
  });
}

export function useAgencyBondSpreads() {
  return useApiQuery(['fi', 'agency', 'spreads'], FI_AGENCY.spreads);
}

export function useAgencyNewIssues() {
  return useApiQuery(['fi', 'agency', 'new-issues'], FI_AGENCY.newIssues);
}

// ---------------------------------------------------------------------------
// Custom Classifications
// ---------------------------------------------------------------------------

export function useCustomClassifications() {
  return useApiQuery(['classifications', 'custom'], CUSTOM_CLASSIFICATIONS.list);
}

export function useCustomClassification(id: string | undefined) {
  return useApiQuery(['classifications', 'custom', id], CUSTOM_CLASSIFICATIONS.detail(id!), undefined, {
    enabled: !!id,
  });
}

export function useCreateClassification() {
  return useApiMutation(CUSTOM_CLASSIFICATIONS.create, [['classifications']]);
}

export function useDeleteClassification() {
  return useApiMutation(CUSTOM_CLASSIFICATIONS.list, [['classifications']]);
}
