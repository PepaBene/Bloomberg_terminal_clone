import { Routes, Route } from 'react-router-dom';
import { Suspense, lazy } from 'react';

// Lazy-load all pages
const Home = lazy(() => import('@/pages/home/MorningBrief'));
const CompanyOverview = lazy(() => import('@/pages/company/CompanyOverview'));
const FinancialStatements = lazy(() => import('@/pages/company/FinancialStatements'));
const ValuationDashboard = lazy(() => import('@/pages/company/ValuationDashboard'));
const OwnershipDashboard = lazy(() => import('@/pages/company/OwnershipDashboard'));
const CreditProfile = lazy(() => import('@/pages/company/CreditProfile'));
const CompanyIntelligence = lazy(() => import('@/pages/company/CompanyIntelligence'));
const ESGDashboard = lazy(() => import('@/pages/company/ESGDashboard'));
const GovernanceDashboard = lazy(() => import('@/pages/company/GovernanceDashboard'));
const FilingsView = lazy(() => import('@/pages/company/FilingsView'));
const ComplexStructure = lazy(() => import('@/pages/structure/ComplexStructure'));
const ScreenerDashboard = lazy(() => import('@/pages/screener/ScreenerDashboard'));
const FIScreenerDashboard = lazy(() => import('@/pages/screener/FIScreenerDashboard'));
const SectorView = lazy(() => import('@/pages/sector/SectorView'));
const IndustryDetail = lazy(() => import('@/pages/sector/IndustryDetail'));
const FIDashboard = lazy(() => import('@/pages/fi/FIDashboard'));
const TreasuryDashboard = lazy(() => import('@/pages/fi/TreasuryDashboard'));
const BondDetail = lazy(() => import('@/pages/fi/BondDetail'));
const CreditMarket = lazy(() => import('@/pages/fi/CreditMarket'));
const IssuanceMonitor = lazy(() => import('@/pages/fi/IssuanceMonitor'));
const FIIntelligence = lazy(() => import('@/pages/fi/FIIntelligence'));
const PortfolioList = lazy(() => import('@/pages/portfolio/PortfolioList'));
const PortfolioDetail = lazy(() => import('@/pages/portfolio/PortfolioDetail'));
const PerformancePage = lazy(() => import('@/pages/portfolio/PerformancePage'));
const RiskPage = lazy(() => import('@/pages/portfolio/RiskPage'));
const RiskDashboard = lazy(() => import('@/pages/risk/RiskDashboard'));
const AdviserChat = lazy(() => import('@/pages/adviser/AdviserChat'));
const MacroDashboard = lazy(() => import('@/pages/macro/MacroDashboard'));
const YieldCurveDeepDive = lazy(() => import('@/pages/macro/YieldCurveDeepDive'));
const CentralBankMonitor = lazy(() => import('@/pages/macro/CentralBankMonitor'));
const GlobalDashboard = lazy(() => import('@/pages/global/GlobalDashboard'));
const CountryRisk = lazy(() => import('@/pages/global/CountryRisk'));
const CommodityDashboard = lazy(() => import('@/pages/global/CommodityDashboard'));
const PoliticalMonitor = lazy(() => import('@/pages/global/PoliticalMonitor'));
const WatchlistView = lazy(() => import('@/pages/watchlist/WatchlistView'));
const AlertsView = lazy(() => import('@/pages/alerts/AlertsView'));
const NewsView = lazy(() => import('@/pages/news/NewsView'));
const ResearchHub = lazy(() => import('@/pages/research/ResearchHub'));
const PrimerView = lazy(() => import('@/pages/research/PrimerView'));
const BriefingView = lazy(() => import('@/pages/research/BriefingView'));
const AnomalyView = lazy(() => import('@/pages/research/AnomalyView'));
const SemanticSearch = lazy(() => import('@/pages/research/SemanticSearch'));
const ThesisBuilder = lazy(() => import('@/pages/research/ThesisBuilder'));
const AnalystQA = lazy(() => import('@/pages/research/AnalystQA'));
const ThemesDashboard = lazy(() => import('@/pages/research/ThemesDashboard'));
const ModelBuilder = lazy(() => import('@/pages/research/ModelBuilder'));
const FlowsDashboard = lazy(() => import('@/pages/flows/FlowsDashboard'));
const CustomData = lazy(() => import('@/pages/custom/CustomData'));
const QuantDashboard = lazy(() => import('@/pages/quant/QuantDashboard'));
const DealsView = lazy(() => import('@/pages/deals/DealsView'));
const SmartMoneyPage = lazy(() => import('@/pages/smartmoney/SmartMoneyPage'));
const SmartMoneyFilerDetail = lazy(() => import('@/pages/smartmoney/SmartMoneyFilerDetail'));
const IPOMonitor = lazy(() => import('@/pages/market/IPOMonitor'));
const BacktestDashboard = lazy(() => import('@/pages/quant/BacktestDashboard'));
const CustomIndexBuilder = lazy(() => import('@/pages/quant/CustomIndexBuilder'));
const Settings = lazy(() => import('@/pages/settings/Settings'));
const NotFound = lazy(() => import('@/pages/global/NotFound'));

function LoadingFallback() {
  return (
    <div className="flex items-center justify-center h-full">
      <div className="text-text-secondary font-ui text-sm">Loading...</div>
    </div>
  );
}

export function AppRouter() {
  return (
    <Suspense fallback={<LoadingFallback />}>
      <Routes>
        <Route path="/" element={<Home />} />

        {/* Company */}
        <Route path="/company" element={<CompanyOverview />} />
        <Route path="/company/financials" element={<FinancialStatements />} />
        <Route path="/company/valuation" element={<ValuationDashboard />} />
        <Route path="/company/ownership" element={<OwnershipDashboard />} />
        <Route path="/company/filings" element={<FilingsView />} />
        <Route path="/company/credit" element={<CreditProfile />} />
        <Route path="/company/intelligence" element={<CompanyIntelligence />} />
        <Route path="/company/esg" element={<ESGDashboard />} />
        <Route path="/company/governance" element={<GovernanceDashboard />} />
        <Route path="/company/:entityId/esg" element={<ESGDashboard />} />
        <Route path="/company/:entityId/governance" element={<GovernanceDashboard />} />
        <Route path="/company/complex-structure" element={<ComplexStructure />} />
        <Route path="/company/:entityId/complex-structure" element={<ComplexStructure />} />

        {/* Screener */}
        <Route path="/screener" element={<ScreenerDashboard />} />
        <Route path="/screener/fi" element={<FIScreenerDashboard />} />

        {/* Sector */}
        <Route path="/sector" element={<SectorView />} />
        <Route path="/sector/:gicsCode" element={<IndustryDetail />} />

        {/* Fixed Income */}
        <Route path="/fi" element={<FIDashboard />} />
        <Route path="/fi/treasuries" element={<TreasuryDashboard />} />
        <Route path="/fi/bonds/:cusip" element={<BondDetail />} />
        <Route path="/fi/credit" element={<CreditMarket />} />
        <Route path="/fi/issuance" element={<IssuanceMonitor />} />
        <Route path="/fi/intelligence" element={<FIIntelligence />} />

        {/* Portfolio */}
        <Route path="/portfolio" element={<PortfolioList />} />
        <Route path="/portfolio/:id" element={<PortfolioDetail />} />
        <Route path="/portfolio/:id/performance" element={<PerformancePage />} />
        <Route path="/portfolio/:id/risk" element={<RiskPage />} />

        {/* Risk */}
        <Route path="/risk" element={<RiskDashboard />} />

        {/* Adviser */}
        <Route path="/adviser" element={<AdviserChat />} />

        {/* Macro */}
        <Route path="/macro" element={<MacroDashboard />} />
        <Route path="/macro/yield-curve" element={<YieldCurveDeepDive />} />
        <Route path="/macro/central-banks" element={<CentralBankMonitor />} />

        {/* Global */}
        <Route path="/global" element={<GlobalDashboard />} />
        <Route path="/global/countries" element={<CountryRisk />} />
        <Route path="/global/commodities" element={<CommodityDashboard />} />
        <Route path="/global/political" element={<PoliticalMonitor />} />

        {/* Watchlist & Alerts & News */}
        <Route path="/watchlist" element={<WatchlistView />} />
        <Route path="/alerts" element={<AlertsView />} />
        <Route path="/news" element={<NewsView />} />

        {/* Research */}
        <Route path="/research" element={<ResearchHub />} />
        <Route path="/research/primers" element={<PrimerView />} />
        <Route path="/research/briefings" element={<BriefingView />} />
        <Route path="/research/anomalies" element={<AnomalyView />} />
        <Route path="/research/search" element={<SemanticSearch />} />
        <Route path="/research/thesis" element={<ThesisBuilder />} />
        <Route path="/research/qa" element={<AnalystQA />} />
        <Route path="/research/themes" element={<ThemesDashboard />} />
        <Route path="/research/model-builder" element={<ModelBuilder />} />

        {/* Flows & Custom */}
        <Route path="/flows" element={<FlowsDashboard />} />
        <Route path="/custom" element={<CustomData />} />

        {/* Deals & IPO */}
        <Route path="/deals" element={<DealsView />} />
        <Route path="/market/ipo" element={<IPOMonitor />} />

        {/* Smart Money */}
        <Route path="/smart-money" element={<SmartMoneyPage />} />
        <Route path="/smart-money/:key" element={<SmartMoneyFilerDetail />} />

        {/* Quant */}
        <Route path="/quant" element={<QuantDashboard />} />
        <Route path="/quant/backtest" element={<BacktestDashboard />} />
        <Route path="/quant/index-builder" element={<CustomIndexBuilder />} />

        {/* Settings */}
        <Route path="/settings" element={<Settings />} />

        {/* 404 Catch-all */}
        <Route path="*" element={<NotFound />} />
      </Routes>
    </Suspense>
  );
}
