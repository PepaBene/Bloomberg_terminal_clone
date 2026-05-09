import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useApiQuery, useApiMutation, useApiUpdate, useApiDelete } from './useApi';
import { PORTFOLIOS, PORTFOLIO_PERFORMANCE, PORTFOLIO_RISK, WATCHLISTS } from '@/api/endpoints';
import api from '@/api/client';

// ---------------------------------------------------------------------------
// Portfolio CRUD
// ---------------------------------------------------------------------------

export function usePortfolios() {
  return useApiQuery(['portfolios'], PORTFOLIOS.list);
}

export function usePortfolio(id: string | undefined) {
  return useApiQuery(['portfolios', id], PORTFOLIOS.detail(id!), undefined, {
    enabled: !!id,
  });
}

export function useCreatePortfolio() {
  return useApiMutation(PORTFOLIOS.create, [['portfolios']]);
}

export function useUpdatePortfolio() {
  return useApiUpdate(PORTFOLIOS.update, [['portfolios']]);
}

export function useDeletePortfolio() {
  return useApiDelete(PORTFOLIOS.delete, [['portfolios']]);
}

export function useClonePortfolio() {
  const queryClient = useQueryClient();
  return useMutation<unknown, Error, { id: string }>({
    mutationFn: ({ id }) => api.post<unknown>(PORTFOLIOS.clone(id), {}),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['portfolios'] });
    },
  });
}

// ---------------------------------------------------------------------------
// Positions & Transactions
// ---------------------------------------------------------------------------

export function usePortfolioPositions(id: string | undefined) {
  return useApiQuery(['portfolios', id, 'positions'], PORTFOLIOS.positions(id!), undefined, {
    enabled: !!id,
  });
}

export function usePortfolioTransactions(id: string | undefined) {
  return useApiQuery(['portfolios', id, 'transactions'], PORTFOLIOS.transactions(id!), undefined, {
    enabled: !!id,
  });
}

export function useAddPosition() {
  const queryClient = useQueryClient();
  return useMutation<unknown, Error, { portfolioId: string; body: unknown }>({
    mutationFn: ({ portfolioId, body }) =>
      api.post<unknown>(PORTFOLIOS.positions(portfolioId), body),
    onSuccess: (_, { portfolioId }) => {
      queryClient.invalidateQueries({ queryKey: ['portfolios', portfolioId, 'positions'] });
      queryClient.invalidateQueries({ queryKey: ['portfolios', portfolioId] });
    },
  });
}

export function useRecordTransaction() {
  const queryClient = useQueryClient();
  return useMutation<unknown, Error, { portfolioId: string; body: unknown }>({
    mutationFn: ({ portfolioId, body }) =>
      api.post<unknown>(PORTFOLIOS.transactions(portfolioId), body),
    onSuccess: (_, { portfolioId }) => {
      queryClient.invalidateQueries({ queryKey: ['portfolios', portfolioId, 'transactions'] });
      queryClient.invalidateQueries({ queryKey: ['portfolios', portfolioId, 'positions'] });
      queryClient.invalidateQueries({ queryKey: ['portfolios', portfolioId, 'nav'] });
    },
  });
}

// ---------------------------------------------------------------------------
// Rebalance / Optimize / What-If / Upload (P4-F-004 — previously unreachable)
// ---------------------------------------------------------------------------

export function useRebalancePortfolio() {
  const queryClient = useQueryClient();
  return useMutation<unknown, Error, { portfolioId: string; body?: unknown }>({
    mutationFn: ({ portfolioId, body }) =>
      api.post<unknown>(PORTFOLIOS.rebalance(portfolioId), body ?? {}),
    onSuccess: (_, { portfolioId }) => {
      queryClient.invalidateQueries({ queryKey: ['portfolios', portfolioId] });
    },
  });
}

export function useOptimizePortfolio() {
  return useMutation<unknown, Error, { portfolioId: string; body?: unknown }>({
    mutationFn: ({ portfolioId, body }) =>
      api.post<unknown>(PORTFOLIOS.optimize(portfolioId), body ?? {}),
  });
}

export function usePortfolioWhatIf() {
  return useMutation<unknown, Error, { portfolioId: string; body: unknown }>({
    mutationFn: ({ portfolioId, body }) =>
      api.post<unknown>(PORTFOLIOS.whatIf(portfolioId), body),
  });
}

export function usePortfolioUploadPreview() {
  return useApiMutation<unknown, { csv_content: string }>(
    PORTFOLIOS.uploadPreview,
    [],
  );
}

export function usePortfolioUploadCommit() {
  return useApiMutation<unknown, { csv_content: string; portfolio_name: string }>(
    PORTFOLIOS.uploadCommit,
    [['portfolios']],
  );
}

// ---------------------------------------------------------------------------
// NAV & Allocations
// ---------------------------------------------------------------------------

export function usePortfolioNav(id: string | undefined) {
  return useApiQuery(['portfolios', id, 'nav'], PORTFOLIOS.nav(id!), undefined, {
    enabled: !!id,
  });
}

export function usePortfolioNavHistory(id: string | undefined) {
  return useApiQuery(['portfolios', id, 'nav', 'history'], PORTFOLIOS.navHistory(id!), undefined, {
    enabled: !!id,
  });
}

export function usePortfolioSnapshot(id: string | undefined) {
  return useApiQuery(['portfolios', id, 'snapshot'], PORTFOLIOS.snapshot(id!), undefined, {
    enabled: !!id,
  });
}

export function usePortfolioAllocations(id: string | undefined) {
  return useApiQuery(['portfolios', id, 'allocations'], PORTFOLIOS.allocations(id!), undefined, {
    enabled: !!id,
  });
}

export function usePortfolioAllocationsBySector(id: string | undefined) {
  return useApiQuery(['portfolios', id, 'allocations', 'sector'], PORTFOLIOS.allocationsBySector(id!), undefined, {
    enabled: !!id,
  });
}

export function usePortfolioAllocationsByCountry(id: string | undefined) {
  return useApiQuery(['portfolios', id, 'allocations', 'country'], PORTFOLIOS.allocationsByCountry(id!), undefined, {
    enabled: !!id,
  });
}

export function usePortfolioAllocationsByAssetClass(id: string | undefined) {
  return useApiQuery(['portfolios', id, 'allocations', 'asset-class'], PORTFOLIOS.allocationsByAssetClass(id!), undefined, {
    enabled: !!id,
  });
}

export function usePortfolioIncome(id: string | undefined) {
  return useApiQuery(['portfolios', id, 'income'], PORTFOLIOS.income(id!), undefined, {
    enabled: !!id,
  });
}

export function usePortfolioIncomeProjection(id: string | undefined) {
  return useApiQuery(['portfolios', id, 'income', 'projection'], PORTFOLIOS.incomeProjection(id!), undefined, {
    enabled: !!id,
  });
}

export function usePortfolioDividendCalendar(id: string | undefined) {
  return useApiQuery(['portfolios', id, 'dividends', 'calendar'], PORTFOLIOS.dividendCalendar(id!), undefined, {
    enabled: !!id,
  });
}

export function usePortfolioTaxLots(id: string | undefined) {
  return useApiQuery(['portfolios', id, 'tax-lots'], PORTFOLIOS.taxLotAnalysis(id!), undefined, {
    enabled: !!id,
  });
}

// ---------------------------------------------------------------------------
// Performance
// ---------------------------------------------------------------------------

export function usePortfolioPerformance(id: string | undefined) {
  return useApiQuery(['portfolios', id, 'performance'], PORTFOLIO_PERFORMANCE.summary(id!), undefined, {
    enabled: !!id,
  });
}

export function usePortfolioReturns(id: string | undefined) {
  return useApiQuery(['portfolios', id, 'performance', 'returns'], PORTFOLIO_PERFORMANCE.returns(id!), undefined, {
    enabled: !!id,
  });
}

export function usePortfolioCalendarReturns(id: string | undefined) {
  return useApiQuery(['portfolios', id, 'performance', 'calendar'], PORTFOLIO_PERFORMANCE.calendarReturns(id!), undefined, {
    enabled: !!id,
  });
}

export function usePortfolioAttribution(id: string | undefined) {
  return useApiQuery(['portfolios', id, 'attribution'], PORTFOLIO_PERFORMANCE.attribution(id!), undefined, {
    enabled: !!id,
  });
}

export function usePortfolioAttributionBySector(id: string | undefined) {
  return useApiQuery(['portfolios', id, 'attribution', 'sector'], PORTFOLIO_PERFORMANCE.attributionBySector(id!), undefined, {
    enabled: !!id,
  });
}

export function usePortfolioAttributionByFactor(id: string | undefined) {
  return useApiQuery(['portfolios', id, 'attribution', 'factor'], PORTFOLIO_PERFORMANCE.attributionByFactor(id!), undefined, {
    enabled: !!id,
  });
}

export function usePortfolioAttributionByCountry(id: string | undefined) {
  return useApiQuery(['portfolios', id, 'attribution', 'country'], PORTFOLIO_PERFORMANCE.attributionByCountry(id!), undefined, {
    enabled: !!id,
  });
}

export function usePortfolioBenchmark(id: string | undefined) {
  return useApiQuery(['portfolios', id, 'performance', 'benchmark'], PORTFOLIO_PERFORMANCE.benchmark(id!), undefined, {
    enabled: !!id,
  });
}

export function usePortfolioRiskMetrics(id: string | undefined) {
  return useApiQuery(['portfolios', id, 'performance', 'risk-metrics'], PORTFOLIO_PERFORMANCE.riskMetrics(id!), undefined, {
    enabled: !!id,
  });
}

export function usePortfolioDrawdown(id: string | undefined) {
  return useApiQuery(['portfolios', id, 'performance', 'drawdown'], PORTFOLIO_PERFORMANCE.drawdown(id!), undefined, {
    enabled: !!id,
  });
}

export function usePortfolioRollingReturns(id: string | undefined) {
  return useApiQuery(['portfolios', id, 'performance', 'rolling'], PORTFOLIO_PERFORMANCE.rollingReturns(id!), undefined, {
    enabled: !!id,
  });
}

export function usePortfolioAlpha(id: string | undefined) {
  return useApiQuery(['portfolios', id, 'performance', 'alpha'], PORTFOLIO_PERFORMANCE.alpha(id!), undefined, {
    enabled: !!id,
  });
}

export function usePortfolioSharpeHistory(id: string | undefined) {
  return useApiQuery(['portfolios', id, 'performance', 'sharpe'], PORTFOLIO_PERFORMANCE.sharpeHistory(id!), undefined, {
    enabled: !!id,
  });
}

export function usePortfolioTrackingError(id: string | undefined) {
  return useApiQuery(['portfolios', id, 'performance', 'tracking-error'], PORTFOLIO_PERFORMANCE.trackingError(id!), undefined, {
    enabled: !!id,
  });
}

export function usePortfolioInformationRatio(id: string | undefined) {
  return useApiQuery(['portfolios', id, 'performance', 'info-ratio'], PORTFOLIO_PERFORMANCE.informationRatio(id!), undefined, {
    enabled: !!id,
  });
}

export function usePortfolioUpDownCapture(id: string | undefined) {
  return useApiQuery(['portfolios', id, 'performance', 'capture'], PORTFOLIO_PERFORMANCE.upDownCapture(id!), undefined, {
    enabled: !!id,
  });
}

export function usePortfolioHoldingPeriodReturns(id: string | undefined) {
  return useApiQuery(['portfolios', id, 'performance', 'holding-period'], PORTFOLIO_PERFORMANCE.holdingPeriodReturns(id!), undefined, {
    enabled: !!id,
  });
}

// ---------------------------------------------------------------------------
// Risk
// ---------------------------------------------------------------------------

export function usePortfolioRisk(id: string | undefined) {
  return useApiQuery(['portfolios', id, 'risk'], PORTFOLIO_RISK.dashboard(id!), undefined, {
    enabled: !!id,
  });
}

export function usePortfolioVaR(id: string | undefined) {
  return useApiQuery(['portfolios', id, 'risk', 'var'], PORTFOLIO_RISK.var(id!), undefined, {
    enabled: !!id,
  });
}

export function usePortfolioVaRDecomposition(id: string | undefined) {
  return useApiQuery(['portfolios', id, 'risk', 'var', 'decomp'], PORTFOLIO_RISK.varDecomposition(id!), undefined, {
    enabled: !!id,
  });
}

export function usePortfolioVaRBacktest(id: string | undefined) {
  return useApiQuery(['portfolios', id, 'risk', 'var', 'backtest'], PORTFOLIO_RISK.varBacktest(id!), undefined, {
    enabled: !!id,
  });
}

export function usePortfolioCVaR(id: string | undefined) {
  return useApiQuery(['portfolios', id, 'risk', 'cvar'], PORTFOLIO_RISK.cvar(id!), undefined, {
    enabled: !!id,
  });
}

export function usePortfolioConcentration(id: string | undefined) {
  return useApiQuery(['portfolios', id, 'risk', 'concentration'], PORTFOLIO_RISK.concentration(id!), undefined, {
    enabled: !!id,
  });
}

export function usePortfolioRiskFactors(id: string | undefined) {
  return useApiQuery(['portfolios', id, 'risk', 'factors'], PORTFOLIO_RISK.factors(id!), undefined, {
    enabled: !!id,
  });
}

export function usePortfolioFactorExposure(id: string | undefined) {
  return useApiQuery(['portfolios', id, 'risk', 'factor-exposure'], PORTFOLIO_RISK.factorExposure(id!), undefined, {
    enabled: !!id,
  });
}

export function usePortfolioStressHistorical(id: string | undefined) {
  return useApiQuery(['portfolios', id, 'risk', 'stress', 'historical'], PORTFOLIO_RISK.stressHistorical(id!), undefined, {
    enabled: !!id,
  });
}

export function usePortfolioStressHypothetical(id: string | undefined) {
  return useApiQuery(['portfolios', id, 'risk', 'stress', 'hypothetical'], PORTFOLIO_RISK.stressHypothetical(id!), undefined, {
    enabled: !!id,
  });
}

export function usePortfolioCompliance(id: string | undefined) {
  return useApiQuery(['portfolios', id, 'compliance'], PORTFOLIO_RISK.compliance(id!), undefined, {
    enabled: !!id,
  });
}

export function usePortfolioComplianceRules(id: string | undefined) {
  return useApiQuery(['portfolios', id, 'compliance', 'rules'], PORTFOLIO_RISK.complianceRules(id!), undefined, {
    enabled: !!id,
  });
}

export function usePortfolioComplianceHistory(id: string | undefined) {
  return useApiQuery(['portfolios', id, 'compliance', 'history'], PORTFOLIO_RISK.complianceHistory(id!), undefined, {
    enabled: !!id,
  });
}

export function usePortfolioDrift(id: string | undefined) {
  return useApiQuery(['portfolios', id, 'drift'], PORTFOLIO_RISK.drift(id!), undefined, {
    enabled: !!id,
  });
}

export function usePortfolioDriftHistory(id: string | undefined) {
  return useApiQuery(['portfolios', id, 'drift', 'history'], PORTFOLIO_RISK.driftHistory(id!), undefined, {
    enabled: !!id,
  });
}

export function usePortfolioLiquidity(id: string | undefined) {
  return useApiQuery(['portfolios', id, 'risk', 'liquidity'], PORTFOLIO_RISK.liquidity(id!), undefined, {
    enabled: !!id,
  });
}

export function usePortfolioCorrelation(id: string | undefined) {
  return useApiQuery(['portfolios', id, 'risk', 'correlation'], PORTFOLIO_RISK.correlation(id!), undefined, {
    enabled: !!id,
  });
}

export function usePortfolioTailRisk(id: string | undefined) {
  return useApiQuery(['portfolios', id, 'risk', 'tail'], PORTFOLIO_RISK.tailRisk(id!), undefined, {
    enabled: !!id,
  });
}

export function usePortfolioBeta(id: string | undefined) {
  return useApiQuery(['portfolios', id, 'risk', 'beta'], PORTFOLIO_RISK.beta(id!), undefined, {
    enabled: !!id,
  });
}

export function usePortfolioVolatility(id: string | undefined) {
  return useApiQuery(['portfolios', id, 'risk', 'volatility'], PORTFOLIO_RISK.volatility(id!), undefined, {
    enabled: !!id,
  });
}

export function usePortfolioCreditRisk(id: string | undefined) {
  return useApiQuery(['portfolios', id, 'risk', 'credit'], PORTFOLIO_RISK.creditRisk(id!), undefined, {
    enabled: !!id,
  });
}

export function usePortfolioInterestRateRisk(id: string | undefined) {
  return useApiQuery(['portfolios', id, 'risk', 'interest-rate'], PORTFOLIO_RISK.interestRateRisk(id!), undefined, {
    enabled: !!id,
  });
}

export function usePortfolioCurrencyRisk(id: string | undefined) {
  return useApiQuery(['portfolios', id, 'risk', 'currency'], PORTFOLIO_RISK.currencyRisk(id!), undefined, {
    enabled: !!id,
  });
}

export function usePortfolioMarginRequirements(id: string | undefined) {
  return useApiQuery(['portfolios', id, 'risk', 'margin'], PORTFOLIO_RISK.marginRequirements(id!), undefined, {
    enabled: !!id,
  });
}

export function useRiskScenarios() {
  return useApiQuery(['portfolios', 'risk', 'scenarios'], PORTFOLIO_RISK.scenarios);
}

// ---------------------------------------------------------------------------
// Watchlists
// ---------------------------------------------------------------------------

export function useWatchlists() {
  return useApiQuery(['watchlists'], WATCHLISTS.list);
}

export function useWatchlist(id: string | undefined) {
  return useApiQuery(['watchlists', id], WATCHLISTS.detail(id!), undefined, {
    enabled: !!id,
  });
}

export function useCreateWatchlist() {
  return useApiMutation(WATCHLISTS.create, [['watchlists']]);
}

export function useUpdateWatchlist() {
  return useApiUpdate(WATCHLISTS.update, [['watchlists']]);
}

export function useDeleteWatchlist() {
  return useApiDelete(WATCHLISTS.delete, [['watchlists']]);
}

export function useWatchlistAlerts(id: string | undefined) {
  return useApiQuery(['watchlists', id, 'alerts'], WATCHLISTS.alerts(id!), undefined, {
    enabled: !!id,
  });
}

export function useWatchlistDigest(id: string | undefined) {
  return useApiQuery(['watchlists', id, 'digest'], WATCHLISTS.digest(id!), undefined, {
    enabled: !!id,
  });
}

export function useWatchlistPerformance(id: string | undefined) {
  return useApiQuery(['watchlists', id, 'performance'], WATCHLISTS.performance(id!), undefined, {
    enabled: !!id,
  });
}

export function useWatchlistHeatmap(id: string | undefined) {
  return useApiQuery(['watchlists', id, 'heatmap'], WATCHLISTS.heatmap(id!), undefined, {
    enabled: !!id,
  });
}
